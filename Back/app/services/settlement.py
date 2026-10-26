from sqlalchemy import select, delete
from app.core.errors import require
from app.common.text import question_key, normalize_question
from app.models.entities import Faq, FaqSource, KnowledgeUnit, KnowledgeGap, utcnow
from app.repositories.base import Repository
from .access import AccessService
from .identity import iso


class SettlementService:
    def __init__(self, db, settings, infra):
        self.db, self.settings, self.infra = db, settings, infra
        self.repo, self.access = Repository(db), AccessService(db)

    def sources(self, faq):
        return list(self.db.scalars(select(FaqSource).where(FaqSource.faq_id == faq.id)))

    def readable(self, actor, faq, current=True):
        sources = self.sources(faq)
        if not sources:
            return False
        for source in sources:
            unit = self.db.get(KnowledgeUnit, source.unit_id)
            if not unit or unit.deleted_at or unit.status != 'published':
                return False
            if current and unit.current_version != source.version:
                return False
            if not self.access.allowed(actor, unit.id, published=True):
                return False
        return True

    def cache_key(self, faq):
        return 'faq:'+faq.id+':'+str(faq.revision)

    def publish_cache(self, faq):
        value = dict(answer=faq.answer, revision=faq.revision,
                     sources={s.unit_id: s.version for s in self.sources(faq)})
        return self.infra.cache.set(self.cache_key(faq), value)

    def serialize(self, actor, faq):
        allowed = self.readable(actor, faq, current=faq.status == 'published')
        return dict(id=faq.id, question=faq.question if allowed else '相关问题访问受限',
                    answer=faq.answer if allowed else '', unitId=faq.related_unit_id or '',
                    frequency=faq.frequency, status=faq.status,
                    cache=bool(allowed and faq.status == 'published' and faq.cache_enabled
                               and self.infra.cache.get(self.cache_key(faq))),
                    reviewerId=faq.reviewer_id, reviewedAt=iso(faq.reviewed_at),
                    category=faq.category if allowed else '', hits=faq.hit_count)

    def list(self, actor, page, page_size, recommendations=False):
        actor.need('faq.review', 'faq.manage')
        q = select(Faq)
        if recommendations:
            q = q.where(Faq.status == 'pending_review')
        rows, total = self.repo.page(q.order_by(Faq.frequency.desc(), Faq.id), page, page_size)
        return dict(items=[self.serialize(actor, f) for f in rows], total=total)

    def save(self, actor, data, entity_id=None):
        actor.need('faq.manage')
        faq = self.repo.get(Faq, entity_id, lock=True) if entity_id else Faq()
        if not entity_id:
            require(data.get('question') and data.get('answer') and data.get('unit_id'),
                    '请填写问题、答案和来源知识')
            faq.question = data['question']
            faq.question_key = question_key(faq.question)
        else:
            require(self.readable(actor, faq, current=False), '来源知识访问受限或未发布', 403)
        replace_sources = bool(data.get('unit_id') and (not entity_id or data['unit_id'] != faq.related_unit_id))
        if data.get('unit_id'):
            unit = self.repo.get(KnowledgeUnit, data['unit_id'])
            self.access.need(actor, unit.id, published=True)
            faq.related_unit_id = unit.id
        for field in ['question', 'answer', 'category']:
            if data.get(field) is not None:
                require(bool(data[field].strip()), '问题、答案和分类不能为空')
                setattr(faq, field, data[field])
        faq.question_key = question_key(faq.question)
        require(normalize_question(faq.question), '问题不能为空')
        if data.get('status'):
            if data['status'] == 'published':
                actor.need('faq.review')
            faq.status = data['status']
        elif entity_id and faq.status == 'published':
            actor.need('faq.review')
        if not entity_id:
            self.db.add(faq)
        self.db.flush()
        if replace_sources:
            self.db.execute(delete(FaqSource).where(FaqSource.faq_id == faq.id))
            self.db.add(FaqSource(faq_id=faq.id, unit_id=unit.id, version=unit.current_version))
        faq.revision += 1
        faq.cache_enabled = faq.status == 'published'
        self.db.flush()
        if faq.cache_enabled:
            require(self.readable(actor, faq), '来源知识已变更，请重新审核', 409)
            faq.reviewer_id, faq.reviewed_at = actor.user.id, utcnow()
            self.publish_cache(faq)
        self.repo.audit(actor.user.id, 'faq.save', faq.id)
        return self.serialize(actor, faq)

    def review(self, actor, entity_id, action, edited_answer):
        actor.need('faq.review')
        faq = self.repo.get(Faq, entity_id, lock=True)
        require(self.readable(actor, faq, current=False), '来源知识访问受限或未发布', 403)
        faq.status = 'published' if action == 'approve' else 'rejected'
        if action == 'approve' and edited_answer.strip():
            faq.answer = edited_answer.strip()
        require(faq.answer.strip(), '标准答案不能为空')
        for source in self.sources(faq):
            source.version = self.db.get(KnowledgeUnit, source.unit_id).current_version
        faq.cache_enabled = action == 'approve'
        faq.reviewer_id, faq.reviewed_at = actor.user.id, utcnow()
        faq.revision += 1
        self.db.flush()
        if faq.cache_enabled:
            self.publish_cache(faq)
        self.repo.audit(actor.user.id, 'faq.review', faq.id, decision=action)

    def remove(self, actor, ids):
        actor.need('faq.manage')
        for faq in self.repo.all_ids(Faq, ids):
            self.infra.cache.delete(self.cache_key(faq))
            self.db.delete(faq)
            self.repo.audit(actor.user.id, 'faq.delete', faq.id)

    def match(self, actor, question):
        faq = self.db.scalar(select(Faq).where(Faq.question_key == question_key(question),
                                              Faq.status == 'published', Faq.cache_enabled.is_(True)))
        if faq and self.readable(actor, faq):
            return self._answer(faq)
        candidates = list(self.db.scalars(select(Faq).where(Faq.status == 'published', Faq.cache_enabled.is_(True))
                                          .order_by(Faq.hit_count.desc()).limit(100)))
        candidates = [f for f in candidates if self.readable(actor, f)]
        if not candidates:
            return None
        try:
            vectors = self.infra.embedder.encode([question]+[f.question for f in candidates])
        except Exception:
            return None
        scores = [sum(x*y for x, y in zip(vectors[0], vector)) for vector in vectors[1:]]
        i = max(range(len(scores)), key=scores.__getitem__)
        if scores[i] >= self.settings.faq_semantic_threshold:
            return self._answer(candidates[i])
        return None

    def _answer(self, faq):
        cached = self.infra.cache.get(self.cache_key(faq))
        sources = {s.unit_id: s.version for s in self.sources(faq)}
        valid_cache = bool(cached and cached.get('revision') == faq.revision and cached.get('sources') == sources)
        answer = cached['answer'] if valid_cache else faq.answer
        if not valid_cache:
            self.publish_cache(faq)
        faq.hit_count += 1
        return dict(answer=answer, sources=sources, cached=valid_cache)

    def gaps(self, actor, page, page_size):
        actor.need('gaps.manage')
        rows, total = self.repo.page(select(KnowledgeGap).order_by(KnowledgeGap.ask_count.desc(), KnowledgeGap.id), page, page_size)
        return dict(items=[self.gap_dict(r) for r in rows], total=total)

    @staticmethod
    def gap_dict(g):
        return dict(id=g.id, question=g.question_pattern, samples=g.sample_questions_json, count=g.ask_count,
                    lastAskedAt=iso(g.last_asked_at), status=g.status, unitId=g.resolved_unit_id)

    def update_gap(self, actor, entity_id, data):
        actor.need('gaps.manage')
        gap = self.repo.get(KnowledgeGap, entity_id, lock=True)
        if data['status'] == 'resolved':
            require(data.get('unit_id'), '解决缺口前请关联知识单元')
            self.access.need(actor, data['unit_id'])
            gap.resolved_unit_id = data['unit_id']
        gap.status = data['status']
        self.repo.audit(actor.user.id, 'gap.update', gap.id, status=gap.status)
        return self.gap_dict(gap)
