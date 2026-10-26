import json
import re
import time
from sqlalchemy import select
from app.common.assets import asset_url
from app.core.errors import require, BusinessError
from app.models.entities import (ChatSession, ChatMessage, QAAccessLog, QALogUnit, KnowledgeUnit,
                                User, AuthSession, Attachment, utcnow)
from app.repositories.base import Repository
from app.common.text import normalize_question
from app.integrations.llm import LLMGateway
from .identity import IdentityService, iso
from .access import AccessService
from .retrieval import RetrievalService
from .settlement import SettlementService
from .settings import IntegrationService


def sse(kind, **data):
    return 'event: '+kind+'\ndata: '+json.dumps(dict(type=kind, **data), ensure_ascii=False)+'\n\n'


SMALLTALK = {'你好', '您好', '哈喽', 'hi', 'hello', 'hey', '在吗', '在不在', '谢谢', '谢了', '感谢',
             '再见', '拜拜', '晚安', '早上好', '下午好', '晚上好', '辛苦了'}


def is_smalltalk(text):
    """Greetings must not trigger retrieval: bge-m3 scores them as high as real questions."""
    return re.sub(r'[\s\W_]+', '', text.lower()) in SMALLTALK


class ChatService:
    def __init__(self, db, settings, infra):
        self.db, self.settings, self.infra = db, settings, infra

    def message_dict(self, actor, message):
        access = AccessService(self.db)
        safe = True
        for unit_id, version in message.source_versions.items():
            unit = self.db.get(KnowledgeUnit, unit_id)
            if not unit or unit.current_version != version or not access.allowed(actor, unit_id, published=True):
                safe = False
                break
        return dict(id=message.id, role=message.role,
                    text=message.content if safe else '相关知识的权限或版本已变更，此条回答暂不可查看。',
                    citations=message.citations if safe else [], denied=message.denied or not safe,
                    cached=message.cached, interrupted=message.interrupted)

    def session_dict(self, actor, session):
        messages = list(self.db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id)
                                        .order_by(ChatMessage.created_at, ChatMessage.id)))
        return dict(id=session.id, userId=session.user_id, title=session.title, updatedAt=iso(session.updated_at),
                    messages=[self.message_dict(actor, m) for m in messages])

    def list(self, actor, page, page_size):
        actor.need('ai.access')
        rows, total = Repository(self.db).page(select(ChatSession).where(ChatSession.user_id == actor.user.id,
            ChatSession.deleted_at.is_(None)).order_by(ChatSession.updated_at.desc(), ChatSession.id), page, page_size)
        return dict(items=[self.session_dict(actor, s) for s in rows], total=total)

    def remove(self, actor, ids):
        actor.need('ai.access')
        sessions = Repository(self.db).all_ids(ChatSession, ids)
        require(all(s.user_id == actor.user.id for s in sessions), '会话不存在', 404)
        for s in sessions:
            s.deleted_at = utcnow()

    def prepare(self, actor, question, session_id):
        actor.need('ai.access')
        require(normalize_question(question), '问题不能为空')
        if session_id:
            session = self.db.get(ChatSession, session_id)
            require(session and session.user_id == actor.user.id and not session.deleted_at, '会话不存在', 404)
        else:
            session = ChatSession(user_id=actor.user.id, title=question[:100])
            self.db.add(session)
            self.db.flush()
        raw_history = list(self.db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id)
                                          .order_by(ChatMessage.created_at, ChatMessage.id)))
        history = []
        for message in raw_history:
            item = self.message_dict(actor, message)
            if not item['denied'] and not item['interrupted']:
                item['_sources'] = message.source_versions
                history.append(item)
        history = history[-10:]
        smalltalk = is_smalltalk(question)
        faq = None if smalltalk else SettlementService(self.db, self.settings, self.infra).match(actor, question)
        sources, citations, chunks = {}, [], []
        images = []
        denied, degraded = False, False
        recalled, unauthorized = [], []
        if smalltalk:
            config = None
        elif faq:
            sources = faq['sources']
            recalled = list(sources)
            for uid in sources:
                u = self.db.get(KnowledgeUnit, uid)
                citations.append(dict(unitId=u.id, code=u.unit_code, title=u.title, location='已审核 FAQ'))
            config = None
        else:
            result = RetrievalService(self.db, self.settings, self.infra).search(actor, question)
            chunks, denied, degraded = result['chunks'][:6], result['denied'], result['degraded']
            recalled, unauthorized = result['recalledIds'], result['unauthorizedIds']
            for chunk in chunks:
                sources[chunk['unitId']] = chunk['version']
                if not any(c['unitId'] == chunk['unitId'] for c in citations):
                    citations.append({k: chunk[k] for k in ['unitId', 'code', 'title', 'location']})
            config = IntegrationService(self.db, self.settings).effective('llm') if chunks else None
            if chunks:
                require(config['enabled'] and config['base_url'] and config['model'],
                        '已检索到授权知识，尚未配置大模型；请由管理员填写 LLM 配置后生成回答', 503)
                # Exact history sent to the model is part of the answer's provenance, too.
                for message in history:
                    for uid, version in message['_sources'].items():
                        require(uid not in sources or sources[uid] == version,
                                '历史知识版本已变化，请新建会话', 409)
                        if uid not in sources:
                            unit = self.db.get(KnowledgeUnit, uid)
                            sources[uid] = version
                            citations.append(dict(unitId=uid, code=unit.unit_code, title=unit.title, location='前文引用'))
                recalled = list(dict.fromkeys(recalled+list(sources)))
            images = self._answer_images(chunks, set(sources), config) if chunks else []
            if not chunks and degraded and not denied:
                # Do not turn a vector/model outage into fabricated knowledge gaps.
                raise BusinessError(503, '向量检索暂不可用，请检查本地模型、Milvus 和 SSH 隧道')
        user_message = ChatMessage(session_id=session.id, role='user', content=question)
        self.db.add(user_message)
        session.updated_at = utcnow()
        self.db.flush()
        return dict(user_id=actor.user.id, token_version=actor.user.token_version,
                    login_id=actor.login_session.id, session_id=session.id, question=question,
                    sources=sources, citations=citations, chunks=chunks, denied=denied,
                    degraded=degraded, recalled=recalled, unauthorized=unauthorized,
                    faq=faq, config=config, history=history, images=images, smalltalk=smalltalk,
                    started=time.monotonic())

    def _answer_images(self, chunks, allowed_units, config):
        """Attach a bounded set of figures cited by the retrieved chunks."""
        limit = int(self.settings.llm_answer_max_images or 0)
        if limit <= 0 or not config or not config.get('vision_enabled'):
            return []
        max_bytes = self.settings.llm_answer_image_max_bytes
        ids = []
        for chunk in chunks:
            for attachment_id in re.findall(r'/api/knowledge/assets/([0-9a-fA-F-]{36})',
                                            chunk.get('content') or ''):
                if attachment_id not in ids:
                    ids.append(attachment_id)
        images = []
        for attachment_id in ids[:limit]:
            a = self.db.get(Attachment, attachment_id)
            if not a or a.unit_id not in allowed_units or a.size > max_bytes:
                continue
            try:
                data = self.infra.storage.get(a.object_key)
            except Exception:
                continue  # Figure context is optional; the text answer still stands.
            images.append({'mime': a.mime_type, 'data': data, 'url': asset_url(self.settings, a.id)})
        return images

    @staticmethod
    def still_allowed(factory, settings, plan):
        with factory() as db:
            user = db.get(User, plan['user_id'])
            login = db.get(AuthSession, plan['login_id'])
            session = db.get(ChatSession, plan['session_id'])
            if (not user or user.status != 'active' or user.token_version != plan['token_version'] or
                    not login or login.revoked or iso(login.expires_at) <= iso(utcnow()) or
                    not session or session.deleted_at):
                return False
            identity = IdentityService(db, settings).identity(user)
            if 'ai.access' not in identity.permissions:
                return False
            access = AccessService(db)
            return all((u := db.get(KnowledgeUnit, uid)) and u.current_version == version and
                       access.allowed(identity, uid, published=True) for uid, version in plan['sources'].items())

    @staticmethod
    def stream(factory, settings, plan):
        answer, interrupted = '', True
        usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        try:
            if not ChatService.still_allowed(factory, settings, plan):
                raise BusinessError(403, '会话或知识访问权限已变更，请重新提问')
            yield sse('session', sessionId=plan['session_id'])
            yield sse('cache', hit=bool(plan['faq'] and plan['faq']['cached']))
            yield sse('citations', citations=plan['citations'])
            if plan['denied']:
                yield sse('denied', message='部分相关知识未获授权，无法用于回答。')
            if plan.get('smalltalk'):
                output = [dict(type='delta', text='你好！我是团队知识助手，可以问我已授权文档里的内容。')]
            elif plan['faq']:
                output = [dict(type='delta', text=plan['faq']['answer'])]
            elif not plan['chunks']:
                text = '相关知识访问权限不足，请联系知识管理员授权。' if plan['denied'] else '当前没有找到可用知识，已记录该问题供知识管理员补充。'
                output = [dict(type='delta', text=text)]
            else:
                output = LLMGateway(plan['config']).stream(plan['question'], plan['chunks'],
                    [m for m in plan['history'] if not m['denied'] and not m.get('interrupted')],
                    images=plan.get('images'))
            for event in output:
                if not ChatService.still_allowed(factory, settings, plan):
                    raise BusinessError(403, '会话或知识访问权限已变更，回答已停止')
                if event['type'] == 'usage':
                    for k in usage:
                        usage[k] = max(0, int(event['usage'].get(k, 0)))
                else:
                    answer += event['text']
                    yield sse('delta', text=event['text'])
            if plan['chunks'] and not answer.strip():
                raise BusinessError(502, '大模型未返回有效回答')
            if plan.get('images'):
                section = ['', '', '---', '', '**回答所依据的图片**', '']
                section += ['![文档插图 %d](%s)' % (i, image['url'])
                            for i, image in enumerate(plan['images'], 1)]
                text = '\n'.join(section)
                answer += text
                yield sse('delta', text=text)
            interrupted = False
        except GeneratorExit:
            raise
        except Exception as exc:
            message = exc.detail if isinstance(exc, BusinessError) else '回答生成失败，请稍后重试'
            yield sse('error', message=message)
        finally:
            ms = int((time.monotonic()-plan['started'])*1000)
            with factory.begin() as db:
                db.add(ChatMessage(session_id=plan['session_id'], role='assistant', content=answer,
                    citations=plan['citations'], source_versions=plan['sources'], denied=plan['denied'],
                    cached=bool(plan['faq'] and plan['faq']['cached']), interrupted=interrupted))
                outcome = ('smalltalk' if plan.get('smalltalk') else 'interrupted' if interrupted else
                           'denied' if plan['denied'] and not plan['sources'] else
                           'answered' if plan['sources'] else 'no_hit')
                log = QAAccessLog(session_id=plan['session_id'], user_id=plan['user_id'], question=plan['question'],
                    normalized_question=normalize_question(plan['question']), answer=answer,
                    recalled_unit_ids_json=plan['recalled'], authorized_unit_ids_json=list(plan['sources']),
                    unauthorized_unit_ids_json=plan['unauthorized'], source_versions=plan['sources'],
                    prompt_tokens=usage['prompt_tokens'], completion_tokens=usage['completion_tokens'],
                    total_tokens=usage['total_tokens'], response_time_ms=ms,
                    cached=bool(plan['faq'] and plan['faq']['cached']), outcome=outcome)
                db.add(log)
                db.flush()
                db.add_all([QALogUnit(log_id=log.id, unit_id=uid) for uid in plan['sources']])
        if not interrupted:
            yield sse('done', tokens=usage['total_tokens'], ms=ms)
