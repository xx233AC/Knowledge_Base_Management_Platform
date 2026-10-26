from sqlalchemy import select
from app.models.entities import User, Role, UserRole, RolePermission
from .base import Repository


class IdentityRepository(Repository):
    def user_by_name(self, username):
        return self.db.scalar(select(User).where(User.username == username))

    def role_ids(self, user_id):
        return list(self.db.scalars(select(UserRole.role_id).where(UserRole.user_id == user_id)))

    def user_roles(self, user_id):
        return list(self.db.scalars(select(Role).join(UserRole, UserRole.role_id == Role.id)
                                   .where(UserRole.user_id == user_id)))

    def permissions(self, role_ids):
        return set(self.db.scalars(select(RolePermission.permission_code).where(RolePermission.role_id.in_(role_ids))))
