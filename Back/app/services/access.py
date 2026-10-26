from app.core.errors import require
from app.repositories.access import AccessRepository


class AccessService:
    """Data grants are independent of RBAC; even system admins have no implicit data bypass."""
    def __init__(self, db):
        self.repo = AccessRepository(db)

    def grants(self, unit_id):
        return [dict(type=p.target_type, **({'id': p.target_id} if p.target_id else {}))
                for p in self.repo.grants(unit_id)]

    def condition(self, identity):
        return self.repo.condition(identity)

    def allowed(self, identity, unit_id, published=False):
        return identity.user.status == 'active' and unit_id in self.repo.allowed_ids(identity, [unit_id], published)

    def need(self, identity, unit_id, published=False):
        require(self.allowed(identity, unit_id, published), '你缺少该知识单元的访问权限', 403)

    def partition(self, identity, unit_ids):
        allowed = self.repo.allowed_ids(identity, unit_ids)
        return dict(authorized_unit_ids=[x for x in unit_ids if x in allowed],
                    unauthorized_unit_ids=[x for x in unit_ids if x not in allowed])

    def validate_grants(self, grants):
        normalized, seen = [], set()
        models = self.repo.TARGET_MODELS
        for g in grants:
            kind, target = g['type'], g.get('id') or None
            require(kind in {'global', *models}, '授权实体类型不合法')
            if kind == 'global':
                require(not target, '全局权限不应指定对象 ID')
            else:
                require(target and self.repo.target_exists(kind, target), '授权对象不存在，请重新选择')
            key = (kind, target)
            if key not in seen:
                normalized.append((kind, target))
                seen.add(key)
        return normalized

    def replace(self, unit, grants):
        normalized = self.validate_grants(grants)
        self.repo.replace(unit, normalized)
