from sqlalchemy import select, func
from app.core.errors import BusinessError, require
from app.models.entities import AuditEvent


class Repository:
    def __init__(self, db):
        self.db = db

    def get(self, model, entity_id, *, lock=False):
        statement = select(model).where(model.id == entity_id)
        if lock:
            statement = statement.with_for_update()
        result = self.db.scalar(statement)
        if result is None:
            raise BusinessError(404, "记录不存在")
        return result

    def all_ids(self, model, ids):
        require(len(ids) == len(set(ids)), "存在重复 ID")
        rows = list(self.db.scalars(select(model).where(model.id.in_(ids))))
        require(len(rows) == len(ids), "部分记录不存在", 404)
        return rows

    def page(self, statement, page=1, page_size=100):
        total = self.db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
        rows = list(self.db.scalars(statement.offset((page - 1) * page_size).limit(page_size)))
        return rows, total

    def audit(self, user_id, action, entity_id=None, **details):
        self.db.add(AuditEvent(actor_id=user_id, action=action, entity_id=entity_id, detail_json=details))
