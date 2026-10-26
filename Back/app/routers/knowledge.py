import hmac
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Request, Query, Response, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from urllib.parse import quote
from app.common.assets import asset_signature
from app.core.dependencies import DB, Actor
from app.core.errors import require
from app.models.entities import User, Attachment
from app.repositories.base import Repository
from app.schemas.requests import UnitInput, Grants, PermissionCheck, Ids
from app.services.knowledge import KnowledgeService
from app.services.imports import ImportService
from app.services.access import AccessService
from app.services.identity import IdentityService

router = APIRouter(prefix='/knowledge', tags=['知识与导入'])


def knowledge(request, db):
    return KnowledgeService(db, request.app.state.settings)


def imports(request, db):
    return ImportService(db, request.app.state.settings, request.app.state.infrastructure)


@router.get('/units')
def units(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1),
          page_size: int = Query(100, ge=1, le=100), title: str = Query('', max_length=300),
          category: str = Query('', max_length=100), status: str = Query('', pattern='^(draft|published)?$')):
    return knowledge(request, db).list(actor, page, page_size, title, category, status)


@router.post('/units')
def create_unit(body: UnitInput, request: Request, db: DB, actor: Actor):
    return knowledge(request, db).save(actor, body.model_dump(exclude_unset=True))


@router.get('/units/{entity_id}')
def get_unit(entity_id: UUID, request: Request, db: DB, actor: Actor):
    return knowledge(request, db).get(actor, str(entity_id))


@router.put('/units/{entity_id}')
def update_unit(entity_id: UUID, body: UnitInput, request: Request, db: DB, actor: Actor):
    return knowledge(request, db).save(actor, body.model_dump(exclude_unset=True), str(entity_id))


@router.post('/units/{entity_id}/permissions')
def set_permissions(entity_id: UUID, body: Grants, request: Request, db: DB, actor: Actor):
    return knowledge(request, db).set_permissions(actor, str(entity_id), [g.model_dump() for g in body.permissions])


@router.delete('/units', status_code=204)
def delete_units(body: Ids, request: Request, db: DB, actor: Actor):
    knowledge(request, db).remove(actor, body.ids)
    return Response(status_code=204)


@router.post('/units/{entity_id}/reindex')
def reindex_unit(entity_id: UUID, request: Request, db: DB, actor: Actor):
    return knowledge(request, db).reindex(actor, str(entity_id))


@router.post('/check-permissions')
def check_permissions(body: PermissionCheck, request: Request, db: DB, actor: Actor):
    actor.need('ai.access', 'knowledge.permissions')
    if body.user_id != actor.user.id:
        actor.need('knowledge.permissions')
        user = Repository(db).get(User, body.user_id)
        require(user.status == 'active', '目标用户已停用')
        actor = IdentityService(db, request.app.state.settings).identity(user)
    return AccessService(db).partition(actor, body.unit_ids)


@router.post('/import')
def upload(request: Request, db: DB, actor: Actor,
           files: Annotated[list[UploadFile], File()],
           relative_paths: Annotated[list[str] | None, Form()] = None):
    return imports(request, db).upload(actor, files, relative_paths or [])


@router.get('/import/jobs')
def jobs(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return imports(request, db).list(actor, page, page_size)


@router.get('/import/jobs/{entity_id}')
def job(entity_id: UUID, request: Request, db: DB, actor: Actor):
    return imports(request, db).get(actor, str(entity_id))


@router.post('/import/jobs/{entity_id}/cancel', status_code=204)
def cancel_job(entity_id: UUID, request: Request, db: DB, actor: Actor):
    imports(request, db).cancel(actor, str(entity_id))
    return Response(status_code=204)


@router.post('/import/jobs/{entity_id}/retry')
def retry_job(entity_id: UUID, request: Request, db: DB, actor: Actor):
    return imports(request, db).retry(actor, str(entity_id))


@router.get('/attachments/{entity_id}/download')
def download(entity_id: UUID, request: Request, db: DB, actor: Actor):
    actor.need('knowledge.read')
    a = Repository(db).get(Attachment, str(entity_id))
    require(a.unit_id, '附件尚未关联知识', 403)
    AccessService(db).need(actor, a.unit_id)
    return StreamingResponse(request.app.state.infrastructure.storage.stream(a.object_key),
        media_type='application/octet-stream', headers={
            'Content-Disposition': "attachment; filename*=UTF-8''"+quote(a.file_name),
            'X-Content-Type-Options': 'nosniff'})


@router.get('/assets/{entity_id}')
def asset(entity_id: UUID, sig: str, request: Request, db: DB):
    """Signed capability URL used by <img> tags, which cannot send an Authorization header."""
    expected = asset_signature(request.app.state.settings, str(entity_id))
    require(hmac.compare_digest(sig, expected), '资源地址无效', 403)
    a = Repository(db).get(Attachment, str(entity_id))
    return StreamingResponse(request.app.state.infrastructure.storage.stream(a.object_key),
        media_type=a.mime_type, headers={'Cache-Control': 'private, max-age=86400',
                                         'X-Content-Type-Options': 'nosniff'})
