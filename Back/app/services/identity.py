from dataclasses import dataclass
from datetime import timedelta, timezone
from uuid import UUID
from app.core.errors import BusinessError, require
from app.core.security import verify_password, hash_password, issue_token, decode_token
from app.models.entities import User, AuthSession, Department, utcnow
from app.repositories.identity import IdentityRepository

ALL_PERMISSIONS = frozenset({
    'dashboard.view', 'org.users.manage', 'org.roles.manage', 'org.departments.manage',
    'knowledge.read', 'knowledge.create', 'knowledge.update', 'knowledge.delete',
    'knowledge.import', 'knowledge.permissions', 'ai.access', 'faq.review', 'faq.manage', 'gaps.manage',
})
DUMMY_HASH = hash_password('invalid-user-timing-placeholder')


def iso(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


@dataclass
class Identity:
    user: User
    roles: list
    permissions: set
    login_session: AuthSession | None = None

    def need(self, *codes):
        require(any(p in self.permissions for p in codes), '你没有执行此操作的权限', 403)


class IdentityService:
    def __init__(self, db, settings, cache=None):
        self.db, self.settings, self.cache = db, settings, cache
        self.repo = IdentityRepository(db)

    def user_dict(self, user):
        roles = self.repo.role_ids(user.id)
        return dict(id=user.id, username=user.username, displayName=user.display_name,
                    departmentId=user.department_id or '', roleIds=roles, status=user.status,
                    createdAt=iso(user.created_at))

    def role_dict(self, role):
        permissions = sorted(self.repo.permissions([role.id]))
        return dict(id=role.id, name=role.role_name, code=role.role_code,
                    description=role.description, permissions=permissions)

    @staticmethod
    def department_dict(dept):
        return dict(id=dept.id, name=dept.name, parentId=dept.parent_id or '',
                    leaderId=dept.leader_id or '', sort=dept.sort_order)

    def identity(self, user, login_session=None):
        roles = self.repo.user_roles(user.id)
        permissions = self.repo.permissions([r.id for r in roles])
        return Identity(user, roles, permissions, login_session)

    def as_dict(self, identity):
        dept = self.db.get(Department, identity.user.department_id) if identity.user.department_id else None
        return dict(user=self.user_dict(identity.user), roles=[self.role_dict(r) for r in identity.roles],
                    permissions=sorted(identity.permissions),
                    department=self.department_dict(dept) if dept else None)

    def login(self, username, password, source='local'):
        if self.cache:
            from app.common.text import question_key
            key = 'login:'+question_key(source+':'+username)
            require(self.cache.rate_limit(key, 10, 60), '登录尝试过于频繁，请稍后重试', 429)
        user = self.repo.user_by_name(username)
        valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
        require(user is not None and valid and user.status == 'active', '用户名或密码错误，或账号已停用', 401)
        login_session = AuthSession(user_id=user.id, expires_at=utcnow()+timedelta(seconds=self.settings.jwt_ttl_seconds))
        self.db.add(login_session)
        self.db.flush()
        identity = self.identity(user, login_session)
        result = self.as_dict(identity)
        result['user_info'] = result.pop('user')
        result.update(access_token=issue_token(self.settings, user, login_session),
                      token_type='bearer', expires_in=self.settings.jwt_ttl_seconds)
        return result

    def resolve(self, token):
        claims = decode_token(self.settings, token)
        try:
            UUID(claims['sub'])
            UUID(claims['jti'])
        except (TypeError, ValueError, AttributeError) as exc:
            raise BusinessError(401, '登录令牌无效') from exc
        user = self.db.get(User, claims['sub'])
        login = self.db.get(AuthSession, claims['jti'])
        require(user and user.status == 'active' and user.token_version == claims['ver']
                and login and login.user_id == user.id and not login.revoked
                and iso(login.expires_at) > iso(utcnow()), '登录已失效，请重新登录', 401)
        return self.identity(user, login)
