from typing import Literal
from fastapi import APIRouter, Query
from app.core.dependencies import DB, Actor
from app.services.dashboard import DashboardService

router = APIRouter(prefix='/dashboard', tags=['数据看板'])
Period = Literal['7d', '30d', 'all']


@router.get('/metrics')
def metrics(db: DB, actor: Actor, period: Period = '7d'):
    return DashboardService(db).metrics(actor, period)


@router.get('/rankings/questions')
def questions(db: DB, actor: Actor, period: Period = '7d'):
    return DashboardService(db).questions(actor, period)


@router.get('/rankings/units')
def units(db: DB, actor: Actor, period: Period = '7d'):
    return DashboardService(db).units(actor, period)


@router.get('/stats/tokens')
def tokens(db: DB, actor: Actor, period: Period = '7d'):
    return DashboardService(db).tokens(actor, period)


@router.get('/stats/latency')
def latency(db: DB, actor: Actor, period: Period = '7d'):
    return DashboardService(db).latency(actor, period)


@router.get('/logs')
def logs(db: DB, actor: Actor, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
    return DashboardService(db).logs(actor, page, page_size)
