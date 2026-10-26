from fastapi import APIRouter, Request, Response
from app.core.dependencies import DB, Actor
from app.schemas.requests import Login
from app.services.identity import IdentityService

router = APIRouter(prefix='/auth', tags=['认证'])


@router.post('/login')
def login(body: Login, request: Request, db: DB):
    state = request.app.state
    return IdentityService(db, state.settings, state.infrastructure.cache).login(
        body.username, body.password, request.client.host if request.client else 'local')


@router.get('/me')
def me(request: Request, db: DB, actor: Actor):
    return IdentityService(db, request.app.state.settings).as_dict(actor)


@router.post('/logout', status_code=204)
def logout(actor: Actor):
    actor.login_session.revoked = True
    return Response(status_code=204)
