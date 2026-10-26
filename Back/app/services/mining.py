"""Periodic semantic aggregation. No denied/error conversation can become a knowledge gap."""
from collections import defaultdict
from datetime import timedelta
from sqlalchemy import select, text
from app.common.text import question_key
from app.models.entities import QAAccessLog, KnowledgeUnit, Faq, FaqSource, KnowledgeGap, utcnow


class MiningService:
    def __init__(self, db, settings, infrastructure):
        self.db, self.settings, self.infra = db, settings, infrastructure

    def run(self):
        # Serialize periodic/manual miners in PostgreSQL without blocking unrelated requests.
        if self.db.bind.dialect.name == 'postgresql':
            if not self.db.scalar(text('SELECT pg_try_advisory_xact_lock(7823402)')):
                return dict(recommendations=0, gaps=0, busy=True)
        rows = list(self.db.scalars(select(QAAccessLog).where(
            QAAccessLog.outcome.in_(['answered', 'no_hit']),
            QAAccessLog.created_at >= utcnow()-timedelta(days=90)).order_by(QAAccessLog.created_at)))
        groups = defaultdict(list)
        for row in rows:
            if row.normalized_question:
                groups[(row.outcome, row.normalized_question)].append(row)
        prepared = []
        for (outcome, _), logs in groups.items():
            sources = {}
            if outcome == 'answered':
                usable = []
                for entry in logs:
                    if not entry.answer or not entry.source_versions:
                        continue
                    if all((unit := self.db.get(KnowledgeUnit, uid)) and not unit.deleted_at
                           and unit.status == 'published' and unit.current_version == version
                           for uid, version in entry.source_versions.items()):
                        usable.append(entry)
                        sources.update(entry.source_versions)
                logs = usable
                if not logs:
                    continue
            prepared.append(dict(outcome=outcome, logs=logs, sources=sources, question=logs[-1].question))
        # A failed embedding service must not erase exact-frequency groups.
        try:
            vectors = self.infra.embedder.encode([g['question'] for g in prepared]) if len(prepared) > 1 else []
        except Exception:
            vectors = []
        merged = []
        for i, group in enumerate(prepared):
            match = None
            if vectors:
                for anchor_index, candidate in merged:
                    if group['outcome'] == candidate['outcome'] and group['sources'] == candidate['sources']:
                        score = sum(a*b for a, b in zip(vectors[i], vectors[anchor_index]))
                        if score >= self.settings.faq_semantic_threshold:
                            match = candidate
                            break
            if match is not None:
                match['logs'].extend(group['logs'])
            else:
                merged.append((i, group))
        n_faq, n_gap = 0, 0
        for _, group in merged:
            logs = sorted(group['logs'], key=lambda row: row.created_at)
            representative = group['question']
            key = question_key(representative)
            if group['outcome'] == 'no_hit':
                gap = self.db.scalar(select(KnowledgeGap).where(KnowledgeGap.question_key == key))
                if gap is None:
                    gap = KnowledgeGap(question_pattern=representative, question_key=key)
                    self.db.add(gap)
                    n_gap += 1
                gap.sample_questions_json = list(dict.fromkeys(r.question for r in logs))[:20]
                gap.ask_count, gap.last_asked_at = len(logs), logs[-1].created_at
            elif len(logs) >= self.settings.faq_min_frequency:
                faq = self.db.scalar(select(Faq).where(Faq.question_key == key))
                if faq:
                    faq.frequency = len(logs)
                    continue  # Never overwrite a human-reviewed answer or decision during mining.
                sources = group['sources']
                faq = Faq(question=representative, question_key=key, answer=logs[-1].answer,
                    related_unit_id=next(iter(sources)), source_type='auto_mined', status='pending_review',
                    frequency=len(logs), category='自动推荐')
                self.db.add(faq)
                self.db.flush()
                self.db.add_all([FaqSource(faq_id=faq.id, unit_id=uid, version=v) for uid, v in sources.items()])
                n_faq += 1
        self.db.flush()
        return dict(recommendations=n_faq, gaps=n_gap, busy=False)
