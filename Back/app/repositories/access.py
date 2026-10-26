from sqlalchemy import select, delete, or_, and_
from app.models.entities import KnowledgeUnit, UnitPermission, User, Department, Role


class AccessRepository:
    TARGET_MODELS = {'department': Department, 'role': Role, 'user': User}

    def __init__(self, db):
        self.db = db

    def grants(self, unit_id):
        return list(self.db.scalars(select(UnitPermission).where(UnitPermission.unit_id == unit_id)))

    @staticmethod
    def condition(identity):
        user, roles = identity.user, [r.id for r in identity.roles]
        clauses = [UnitPermission.target_type == 'global',
                   and_(UnitPermission.target_type == 'user', UnitPermission.target_id == user.id)]
        if user.department_id:
            clauses.append(and_(UnitPermission.target_type == 'department', UnitPermission.target_id == user.department_id))
        if roles:
            clauses.append(and_(UnitPermission.target_type == 'role', UnitPermission.target_id.in_(roles)))
        return select(UnitPermission.id).where(UnitPermission.unit_id == KnowledgeUnit.id, or_(*clauses)).exists()

    def allowed_ids(self, identity, unit_ids, published=False):
        q = select(KnowledgeUnit.id).where(KnowledgeUnit.id.in_(unit_ids),
            KnowledgeUnit.deleted_at.is_(None), self.condition(identity))
        if published:
            q = q.where(KnowledgeUnit.status == 'published')
        return set(self.db.scalars(q))

    def target_exists(self, kind, target):
        return self.db.get(self.TARGET_MODELS[kind], target) is not None

    def replace(self, unit, normalized):
        self.db.execute(delete(UnitPermission).where(UnitPermission.unit_id == unit.id))
        for kind, target in normalized:
            fields = {kind+'_id': target} if kind != 'global' else {}
            self.db.add(UnitPermission(unit_id=unit.id, target_type=kind, target_id=target, **fields))
        unit.acl_version += 1
        self.db.flush()
