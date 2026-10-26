from uuid import UUID
from fastapi import APIRouter, Request, Query, Response
from app.core.dependencies import DB, Actor
from app.schemas.requests import FaqInput, FaqReview, GapInput, Ids
from app.services.settlement import SettlementService

router = APIRouter(prefix='/settlement', tags=['知识沉淀'])


@router.post('/mine')
def mine(request: Request, db: DB, actor: Actor):
    from app.services.mining import MiningService
    actor.need('faq.review')
    return MiningService(db, request.app.state.settings, request.app.state.infrastructure).run()


def service(request, db):
    return SettlementService(db, request.app.state.settings, request.app.state.infrastructure)


@router.get('/faqs')
def faqs(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return service(request, db).list(actor, page, page_size)


@router.get('/faqs/recommendations')
def recommendations(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return service(request, db).list(actor, page, page_size, recommendations=True)


@router.post('/faqs')
def create_faq(body: FaqInput, request: Request, db: DB, actor: Actor):
    return service(request, db).save(actor, body.model_dump(exclude_unset=True))


@router.put('/faqs/{entity_id}')
def update_faq(entity_id: UUID, body: FaqInput, request: Request, db: DB, actor: Actor):
    return service(request, db).save(actor, body.model_dump(exclude_unset=True), str(entity_id))


@router.post('/faqs/{entity_id}/review', status_code=204)
def review_faq(entity_id: UUID, body: FaqReview, request: Request, db: DB, actor: Actor):
    service(request, db).review(actor, str(entity_id), body.action, body.edited_answer)
    return Response(status_code=204)


@router.delete('/faqs', status_code=204)
def delete_faqs(body: Ids, request: Request, db: DB, actor: Actor):
    service(request, db).remove(actor, body.ids)
    return Response(status_code=204)


@router.get('/knowledge-gaps')
def gaps(request: Request, db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return service(request, db).gaps(actor, page, page_size)


@router.put('/knowledge-gaps/{entity_id}')
def update_gap(entity_id: UUID, body: GapInput, request: Request, db: DB, actor: Actor):
    return service(request, db).update_gap(actor, str(entity_id), body.model_dump(exclude_unset=True))
