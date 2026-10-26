from fastapi import APIRouter, Request
from app.core.dependencies import DB, Actor
from app.schemas.requests import IntegrationInput
from app.services.settings import IntegrationService

router = APIRouter(prefix='/settings', tags=['模型与解析服务配置'])


@router.get('/integrations')
def integrations(request: Request, db: DB, actor: Actor):
    return IntegrationService(db, request.app.state.settings).list(actor)


@router.put('/integrations/{provider}')
def update_integration(provider: str, body: IntegrationInput, request: Request, db: DB, actor: Actor):
    return IntegrationService(db, request.app.state.settings).save(actor, provider, body.model_dump())
