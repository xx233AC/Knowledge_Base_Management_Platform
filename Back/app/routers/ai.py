from fastapi import APIRouter, Request, Query, Response
from fastapi.responses import StreamingResponse
from app.core.dependencies import DB, Actor
from app.schemas.requests import ChatInput, Ids
from app.services.chat import ChatService
from app.services.retrieval import RetrievalService

router = APIRouter(prefix='/ai', tags=['鉴权检索与问答'])


def service(request, db):
    state = request.app.state
    return ChatService(db, state.settings, state.infrastructure)


@router.get('/sessions')
def sessions(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return service(request, db).list(actor, page, page_size)


@router.delete('/sessions', status_code=204)
def delete_sessions(body: Ids, request: Request, db: DB, actor: Actor):
    service(request, db).remove(actor, body.ids)
    return Response(status_code=204)


@router.post('/search')
def search(body: ChatInput, request: Request, db: DB, actor: Actor):
    state = request.app.state
    result = RetrievalService(db, state.settings, state.infrastructure).search(actor, body.question)
    return {k: result[k] for k in ['chunks', 'denied', 'degraded']}


@router.post('/chat/stream')
def chat(body: ChatInput, request: Request, db: DB, actor: Actor):
    state = request.app.state
    plan = service(request, db).prepare(actor, body.question.strip(), body.session_id)
    db.commit()  # Durable user message/session must exist before the first SSE byte.
    return StreamingResponse(ChatService.stream(state.session_factory, state.settings, plan),
        media_type='text/event-stream', headers={'Cache-Control': 'no-cache, no-transform',
                                                'X-Accel-Buffering': 'no'})
