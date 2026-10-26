from sqlalchemy import select
from app.core.errors import require
from app.core.security import hash_password
from app.models.entities import Role, RolePermission, User, UserRole, Department
from .identity import ALL_PERMISSIONS


def seed_admin(db, password):
    _validate_seed_input(db, password)
    dept = _create_default_department(db)
    roles = _create_default_roles(db)
    user = _create_admin_user(db, password, dept)
    db.add(UserRole(user_id=user.id, role_id=roles['system_admin'].id))
    return user


def _validate_seed_input(db, password):
    """校验系统初始化入参。

    参数:
        db: 数据库会话，用于检查是否已存在用户。
        password: 初始管理员明文密码。

    输出:
        None；校验不通过时抛出业务异常。
    """
    require(len(password) >= 12, '初始管理员密码至少 12 位')
    require(not db.scalar(select(User.id).limit(1)), '数据库已有用户，禁止覆盖初始化', 409)


def _create_default_department(db):
    """创建初始部门。

    参数:
        db: 数据库会话。

    输出:
        Department: 已持久化并刷新的默认「团队」部门对象。
    """
    dept = Department(name='团队', sort_order=0)
    db.add(dept)
    db.flush()
    return dept


def _create_default_roles(db):
    """按预置定义批量创建初始角色及其权限项。

    参数:
        db: 数据库会话。

    输出:
        dict: 角色编码到 Role 对象的映射。
    """
    definitions = [
        ('system_admin', '系统管理员', ALL_PERMISSIONS),
        ('knowledge_admin', '知识管理员', ALL_PERMISSIONS - {'org.users.manage', 'org.roles.manage', 'org.departments.manage'}),
        ('member', '普通用户', {'knowledge.read', 'ai.access'}),
    ]
    roles = {}
    for code, name, permissions in definitions:
        role = Role(role_code=code, role_name=name, description='初始角色，可在组织管理中调整')
        db.add(role)
        db.flush()
        roles[code] = role
        for permission in sorted(permissions):
            db.add(RolePermission(role_id=role.id, permission_code=permission,
                                  permission_type='menu' if permission == 'dashboard.view' else 'operation'))
    return roles


def _create_admin_user(db, password, dept):
    """创建系统管理员账号。

    参数:
        db: 数据库会话。
        password: 初始管理员明文密码。
        dept: 管理员所属部门对象。

    输出:
        User: 已持久化并刷新的管理员用户对象。
    """
    user = User(username='admin', display_name='系统管理员', department_id=dept.id, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    return user
