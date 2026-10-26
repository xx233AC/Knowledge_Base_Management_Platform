import logging
import re
from sqlalchemy import select, or_
from app.models.entities import KnowledgeUnit, Chunk
from .access import AccessService

log = logging.getLogger(__name__)


def query_terms(question):
    terms = []
    for term in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]{2,}', question.lower()):
        if re.fullmatch(r'[\u4e00-\u9fff]+', term):
            terms.extend(term[i:i+2] for i in range(len(term)-1)
                         if term[i:i+2] not in {'如何', '什么', '怎么', '请问', '可以', '需要'})
        else:
            terms.append(term)
    return list(dict.fromkeys(terms))[:32]


class RetrievalService:
    def __init__(self, db, settings, infra):
        self.db, self.settings, self.infra = db, settings, infra

    def search(self, actor, question):
        actor.need('ai.access')
        available = select(KnowledgeUnit.id).where(KnowledgeUnit.deleted_at.is_(None), KnowledgeUnit.status == 'published')
        if self.db.scalar(available.limit(1)) is None:
            return dict(chunks=[], denied=False, degraded=False, recalledIds=[], unauthorizedIds=[])
        terms = query_terms(question)
        raw_keywords = []
        if terms:
            q = select(Chunk).join(KnowledgeUnit, Chunk.unit_id == KnowledgeUnit.id).where(
                KnowledgeUnit.deleted_at.is_(None), KnowledgeUnit.status == 'published',
                Chunk.version == KnowledgeUnit.current_version,
                or_(*[or_(Chunk.content.icontains(t, autoescape=True), KnowledgeUnit.title.icontains(t, autoescape=True)) for t in terms]))
            raw_keywords = list(self.db.scalars(q.order_by(KnowledgeUnit.updated_at.desc(), Chunk.ordinal).limit(100)))
            raw_keywords.sort(key=lambda c: -sum(t in c.content.lower() for t in terms))
        scores, candidates = {}, {}
        for rank, chunk in enumerate(raw_keywords):
            candidates[chunk.id] = chunk
            scores[chunk.id] = 1/(60+rank+1)
        degraded = False
        try:
            vector = self.infra.embedder.encode([question])[0]
            hits = self.infra.vectors.search(vector, self.settings.retrieval_top_k*4)
            for rank, hit in enumerate(hits):
                if hit['score'] < self.settings.retrieval_min_score:
                    continue
                chunk = self.db.get(Chunk, hit['chunk_id'])
                if not chunk or chunk.unit_id != hit['unit_id'] or chunk.version != hit['version']:
                    continue
                unit = self.db.get(KnowledgeUnit, chunk.unit_id)
                if not unit or unit.deleted_at or unit.status != 'published' or unit.current_version != chunk.version:
                    continue
                candidates[chunk.id] = chunk
                scores[chunk.id] = scores.get(chunk.id, 0)+1/(60+rank+1)
        except Exception as exc:
            # Explicit degraded flag distinguishes keyword recall from successfully executed vector search.
            log.warning('向量检索降级（%s）：%s', type(exc).__name__, exc)
            degraded = True
        access = AccessService(self.db)
        result, denied, unauthorized = [], False, []
        for chunk_id in sorted(scores, key=scores.get, reverse=True):
            chunk = candidates[chunk_id]
            if not access.allowed(actor, chunk.unit_id, published=True):
                denied = True
                unauthorized.append(chunk.unit_id)
                continue
            unit = self.db.get(KnowledgeUnit, chunk.unit_id)
            result.append(dict(chunkId=chunk.id, unitId=unit.id, version=chunk.version,
                code=unit.unit_code, title=unit.title, content=chunk.content, score=scores[chunk.id],
                location=chunk.heading or ('第 '+str(chunk.page)+' 页' if chunk.page else '片段 '+str(chunk.ordinal+1))))
        return dict(chunks=result[:self.settings.retrieval_top_k], denied=denied, degraded=degraded,
                    recalledIds=list(dict.fromkeys(c.unit_id for c in candidates.values())),
                    unauthorizedIds=list(dict.fromkeys(unauthorized)))
