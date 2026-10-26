from datetime import timedelta
from sqlalchemy import select, func
from app.models.entities import QAAccessLog, KnowledgeUnit, QALogUnit, utcnow
from app.repositories.base import Repository
from .access import AccessService
from .identity import iso


class DashboardService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def scope(period):
        if period == 'all':
            return []
        days = 7 if period == '7d' else 30
        return [QAAccessLog.created_at >= utcnow()-timedelta(days=days)]

    def metrics(self, actor, period):
        actor.need('dashboard.view')
        count, uv, tokens, avg = self.db.execute(select(func.count(QAAccessLog.id),
            func.count(func.distinct(QAAccessLog.user_id)), func.coalesce(func.sum(QAAccessLog.total_tokens), 0),
            func.coalesce(func.avg(QAAccessLog.response_time_ms), 0)).where(*self.scope(period))).one()
        units = self.db.scalar(select(func.count(KnowledgeUnit.id)).where(KnowledgeUnit.deleted_at.is_(None)))
        return dict(visits=count, uv=uv, tokens=tokens, avgMs=round(float(avg), 2), unitCount=units)

    def questions(self, actor, period):
        actor.need('dashboard.view')
        count = func.count(QAAccessLog.id)
        return [[question, n] for question, n in self.db.execute(select(QAAccessLog.question, count)
            .where(*self.scope(period)).group_by(QAAccessLog.question).order_by(count.desc(), QAAccessLog.question).limit(5))]

    def units(self, actor, period):
        actor.need('dashboard.view')
        count = func.count(QALogUnit.id)
        rows = self.db.execute(select(QALogUnit.unit_id, count).join(QAAccessLog, QALogUnit.log_id == QAAccessLog.id)
            .where(*self.scope(period)).group_by(QALogUnit.unit_id).order_by(count.desc(), QALogUnit.unit_id).limit(5))
        result = []
        for unit_id, n in rows:
            unit = self.db.get(KnowledgeUnit, unit_id)
            title = unit.title if unit and AccessService(self.db).allowed(actor, unit_id) else '未授权或已删除知识'
            result.append(dict(id=unit_id, title=title, count=n))
        return result

    def tokens(self, actor, period):
        actor.need('dashboard.view')
        date = func.date(QAAccessLog.created_at)
        return [dict(date=str(day), visits=n, tokens=tokens)
            for day, n, tokens in self.db.execute(select(date, func.count(), func.sum(QAAccessLog.total_tokens))
                .where(*self.scope(period)).group_by(date).order_by(date))]

    def latency(self, actor, period):
        actor.need('dashboard.view')
        result = []
        for label, low, high in [('< 1 秒', 0, 1000), ('1–2 秒', 1000, 2000),
                                  ('2–3 秒', 2000, 3000), ('≥ 3 秒', 3000, None)]:
            q = select(func.count()).select_from(QAAccessLog).where(*self.scope(period), QAAccessLog.response_time_ms >= low)
            if high is not None:
                q = q.where(QAAccessLog.response_time_ms < high)
            result.append(dict(label=label, min=low, max=high, count=self.db.scalar(q)))
        return result

    def logs(self, actor, page, page_size):
        actor.need('dashboard.view')
        rows, total = Repository(self.db).page(select(QAAccessLog).order_by(QAAccessLog.created_at.desc(), QAAccessLog.id), page, page_size)
        access = AccessService(self.db)
        return dict(items=[dict(id=r.id, userId=r.user_id, question=r.question,
                   unitIds=[uid for uid in r.authorized_unit_ids_json if access.allowed(actor, uid)],
                   tokens=r.total_tokens, ms=r.response_time_ms, date=iso(r.created_at)) for r in rows], total=total)
