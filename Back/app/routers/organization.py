from uuid import UUID
from fastapi import APIRouter, Request, Query, Response
from app.core.dependencies import DB, Actor
from app.models.entities import User, Role, Department
from app.schemas.requests import UserInput, RoleInput, DepartmentInput, RolePermissions, Password, Ids
from app.services.organization import OrganizationService
from app.services.identity import ALL_PERMISSIONS

router = APIRouter(prefix='/org', tags=['组织与操作权限'])


def service(request, db):
    return OrganizationService(db, request.app.state.settings)


@router.get('/users')
def users(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return service(request, db).list(actor, User, page, page_size)


@router.post('/users')
def create_user(body: UserInput, request: Request, db: DB, actor: Actor):
    return service(request, db).save_user(actor, body.model_dump(exclude_unset=True))


@router.put('/users/{entity_id}')
def update_user(entity_id: UUID, body: UserInput, request: Request, db: DB, actor: Actor):
    return service(request, db).save_user(actor, body.model_dump(exclude_unset=True), str(entity_id))


@router.post('/users/{entity_id}/reset-password', status_code=204)
def reset_password(entity_id: UUID, body: Password, request: Request, db: DB, actor: Actor):
    service(request, db).reset_password(actor, str(entity_id), body.password)
    return Response(status_code=204)


@router.delete('/users', status_code=204)
def delete_users(body: Ids, request: Request, db: DB, actor: Actor):
    service(request, db).remove(actor, User, body.ids)
    return Response(status_code=204)


@router.get('/roles')
def roles(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return service(request, db).list(actor, Role, page, page_size)


@router.post('/roles')
def create_role(body: RoleInput, request: Request, db: DB, actor: Actor):
    return service(request, db).save_role(actor, body.model_dump(exclude_unset=True))


@router.put('/roles/{entity_id}')
def update_role(entity_id: UUID, body: RoleInput, request: Request, db: DB, actor: Actor):
    return service(request, db).save_role(actor, body.model_dump(exclude_unset=True), str(entity_id))


@router.post('/roles/{entity_id}/permissions')
def permissions(entity_id: UUID, body: RolePermissions, request: Request, db: DB, actor: Actor):
    return service(request, db).set_permissions(actor, str(entity_id), body.permissions)


@router.delete('/roles', status_code=204)
def delete_roles(body: Ids, request: Request, db: DB, actor: Actor):
    service(request, db).remove(actor, Role, body.ids)
    return Response(status_code=204)


@router.get('/permissions')
def permission_catalog(actor: Actor):
    actor.need('org.roles.manage')
    return sorted(ALL_PERMISSIONS)


@router.get('/departments')
def departments(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return service(request, db).list(actor, Department, page, page_size)


@router.post('/departments')
def create_department(body: DepartmentInput, request: Request, db: DB, actor: Actor):
    return service(request, db).save_department(actor, body.model_dump(exclude_unset=True))


@router.put('/departments/{entity_id}')
def update_department(entity_id: UUID, body: DepartmentInput, request: Request, db: DB, actor: Actor):
    return service(request, db).save_department(actor, body.model_dump(exclude_unset=True), str(entity_id))


@router.delete('/departments', status_code=204)
def delete_departments(body: Ids, request: Request, db: DB, actor: Actor):
    service(request, db).remove(actor, Department, body.ids)
    return Response(status_code=204)
