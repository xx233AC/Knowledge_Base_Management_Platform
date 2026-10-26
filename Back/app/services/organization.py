from sqlalchemy import select, delete, text
from app.core.errors import require
from app.core.security import hash_password
from app.models.entities import User, Role, Department, UserRole, RolePermission, UnitPermission
from app.repositories.base import Repository
from .identity import IdentityService, ALL_PERMISSIONS


class OrganizationService:
    def __init__(self, db, settings):
        self.db, self.repo = db, Repository(db)
        self.identity = IdentityService(db, settings)

    def admin_lock(self):
        if self.db.bind.dialect.name == 'postgresql':
            self.db.execute(text('SELECT pg_advisory_xact_lock(7823401)'))

    def protect_admin(self):
        self.db.flush()
        for user in self.db.scalars(select(User).where(User.status == 'active')):
            identity = self.identity.identity(user)
            if {'org.users.manage', 'org.roles.manage'} <= identity.permissions:
                return
        require(False, '必须保留至少一位可管理用户与角色的启用管理员', 409)

    def save_user(self, actor, data, entity_id=None):
        actor.need('org.users.manage')
        self.admin_lock()
        user = self.repo.get(User, entity_id, lock=True) if entity_id else User()
        if not entity_id:
            require(data.get('username') and data.get('password') and data.get('display_name'), '请填写用户名、姓名和密码')
        if data.get('username') is not None:
            other = self.db.scalar(select(User.id).where(User.username == data['username']))
            require(not other or other == entity_id, '用户名已存在', 409)
            user.username = data['username']
        for field in ['display_name', 'status']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])
        if 'department_id' in data:
            target = data['department_id'] or None
            require(not target or self.db.get(Department, target), '所属部门不存在')
            led = list(self.db.scalars(select(Department).where(Department.leader_id == user.id))) if user.id else []
            for d in led:
                if d.id != target:
                    d.leader_id = None
            user.department_id = target
        if user.status == 'disabled' and user.id:
            for d in self.db.scalars(select(Department).where(Department.leader_id == user.id)):
                d.leader_id = None
        if data.get('password'):
            user.password_hash = hash_password(data['password'])
            user.token_version = (user.token_version or 0) + 1
        if not entity_id:
            self.db.add(user)
        self.db.flush()
        if data.get('role_ids') is not None:
            ids = list(dict.fromkeys(data['role_ids']))
            self.repo.all_ids(Role, ids)
            self.db.execute(delete(UserRole).where(UserRole.user_id == user.id))
            self.db.add_all([UserRole(user_id=user.id, role_id=x) for x in ids])
        self.protect_admin()
        self.repo.audit(actor.user.id, 'user.save', user.id)
        return self.identity.user_dict(user)

    def reset_password(self, actor, entity_id, password):
        actor.need('org.users.manage')
        user = self.repo.get(User, entity_id, lock=True)
        user.password_hash = hash_password(password)
        user.token_version += 1
        self.repo.audit(actor.user.id, 'user.reset_password', user.id)

    def save_role(self, actor, data, entity_id=None):
        actor.need('org.roles.manage')
        self.admin_lock()
        role = self.repo.get(Role, entity_id, lock=True) if entity_id else Role()
        if not entity_id:
            require(data.get('name') and data.get('code'), '请填写角色名称和编码')
        if data.get('code'):
            other = self.db.scalar(select(Role.id).where(Role.role_code == data['code']))
            require(not other or other == entity_id, '角色编码已存在', 409)
        for key, attr in [('name', 'role_name'), ('code', 'role_code'), ('description', 'description')]:
            if data.get(key) is not None:
                setattr(role, attr, data[key])
        if not entity_id:
            self.db.add(role)
        self.db.flush()
        if data.get('permissions') is not None:
            self.set_permissions(actor, role.id, data['permissions'])
        self.protect_admin()
        self.repo.audit(actor.user.id, 'role.save', role.id)
        return self.identity.role_dict(role)

    def set_permissions(self, actor, role_id, permissions):
        actor.need('org.roles.manage')
        self.admin_lock()
        role = self.repo.get(Role, role_id, lock=True)
        require(set(permissions) <= ALL_PERMISSIONS, '包含未知操作权限')
        self.db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for p in sorted(set(permissions)):
            self.db.add(RolePermission(role_id=role_id, permission_code=p,
                                      permission_type='menu' if p == 'dashboard.view' else 'operation'))
        self.protect_admin()
        self.repo.audit(actor.user.id, 'role.permissions', role_id, permissions=sorted(set(permissions)))
        return self.identity.role_dict(role)

    def save_department(self, actor, data, entity_id=None):
        actor.need('org.departments.manage')
        self.admin_lock()
        dept = self.repo.get(Department, entity_id, lock=True) if entity_id else Department(name=data.get('name'))
        if not entity_id:
            require(data.get('name'), '请填写部门名称')
            self.db.add(dept)
            self.db.flush()
        if data.get('name') is not None:
            dept.name = data['name']
        if 'parent_id' in data:
            parent = data['parent_id'] or None
            seen = {dept.id}
            cursor = parent
            while cursor:
                require(cursor not in seen, '上级部门不能形成循环', 409)
                seen.add(cursor)
                cursor = self.repo.get(Department, cursor).parent_id
            dept.parent_id = parent
        if 'leader_id' in data:
            leader_id = data['leader_id'] or None
            leader = self.repo.get(User, leader_id) if leader_id else None
            require(not leader or (leader.department_id == dept.id and leader.status == 'active'),
                    '负责人必须是本部门的启用成员')
            dept.leader_id = leader_id
        if data.get('sort') is not None:
            dept.sort_order = data['sort']
        self.db.flush()
        self.repo.audit(actor.user.id, 'department.save', dept.id)
        return self.identity.department_dict(dept)

    def remove(self, actor, model, ids):
        actor.need({User: 'org.users.manage', Role: 'org.roles.manage', Department: 'org.departments.manage'}[model])
        self.admin_lock()
        rows = self.repo.all_ids(model, ids)
        for row in rows:
            if model is User:
                require(row.id != actor.user.id, '不能删除当前登录账号', 409)
            if model is Role:
                require(not self.db.scalar(select(UserRole.id).where(UserRole.role_id == row.id)), '角色已分配给用户', 409)
                require(not self.db.scalar(select(UnitPermission.id).where(UnitPermission.role_id == row.id)),
                        '角色仍被知识授权引用', 409)
            if model is Department:
                require(not self.db.scalar(select(Department.id).where(Department.parent_id == row.id)), '部门存在下级', 409)
                require(not self.db.scalar(select(User.id).where(User.department_id == row.id)), '部门仍有成员', 409)
            self.db.delete(row)
            self.repo.audit(actor.user.id, 'org.delete', row.id, table=model.__tablename__)
        self.protect_admin()

    def list(self, actor, model, page, page_size):
        codes = {User: ['org.users.manage', 'knowledge.permissions', 'org.departments.manage'],
                 Role: ['org.roles.manage', 'org.users.manage', 'knowledge.permissions'],
                 Department: ['org.departments.manage', 'org.users.manage', 'knowledge.permissions']}
        actor.need(*codes[model])
        rows, total = self.repo.page(select(model).order_by(model.created_at, model.id), page, page_size)
        serializer = {User: self.identity.user_dict, Role: self.identity.role_dict,
                      Department: self.identity.department_dict}[model]
        items = [serializer(r) for r in rows]
        result = dict(items=items, total=total)
        if model is Department:
            all_depts = list(self.db.scalars(select(Department).order_by(Department.sort_order, Department.id)))
            def branch(parent=None):
                return [dict(**self.identity.department_dict(d), children=branch(d.id))
                        for d in all_depts if d.parent_id == parent]
            result['tree'] = branch()
        return result
