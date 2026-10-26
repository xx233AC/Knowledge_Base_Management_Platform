import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from app.core.config import get_settings
from app.core.database import build_database
from app.core.errors import BusinessError
from app.core.worker_runtime import WorkerRuntime
from app.integrations.infrastructure import Infrastructure
from app.routers import auth, organization, knowledge, ai, dashboard, settlement, settings as settings_router

log = logging.getLogger(__name__)


def create_app(settings=None, *, session_factory=None, infrastructure=None):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.worker_runtime = None
        try:
            if settings.worker_auto_start:
                async with WorkerRuntime(settings) as worker:
                    app.state.worker_runtime = worker
                    yield
            else:
                yield
        finally:
            if hasattr(app.state, 'engine'):
                app.state.engine.dispose()

    app = FastAPI(title=settings.app_name, version='0.1.0', openapi_url='/api/openapi.json', lifespan=lifespan)
    app.state.settings = settings
    if session_factory is None:
        engine, session_factory = build_database(settings.database_url)
        app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.infrastructure = infrastructure or Infrastructure.from_settings(settings)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
                       allow_headers=['Authorization', 'Content-Type', 'Accept'])

    @app.exception_handler(BusinessError)
    async def business_error(request: Request, exc: BusinessError):
        return JSONResponse({'detail': exc.detail}, status_code=exc.status)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        return JSONResponse({'detail': '数据存在重复或仍被其他记录引用，请检查后重试'}, status_code=409)

    @app.exception_handler(OperationalError)
    async def database_unavailable(request: Request, exc: OperationalError):
        return JSONResponse({'detail': '数据库不可用，请检查 SSH 隧道、凭据和数据库迁移'}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Never echo submitted passwords/API keys, even on a validation error.
        fields = ', '.join('.'.join(str(x) for x in e['loc'][1:]) for e in exc.errors())
        return JSONResponse({'detail': '请求参数不合法：'+fields}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        log.error('Request failed: %s %s (%s)', request.method, request.url.path, type(exc).__name__)
        return JSONResponse({'detail': '服务暂时不可用，请稍后重试'}, status_code=500)

    @app.get('/health', tags=['健康检查'])
    def health():
        return {'status': 'ok', 'service': 'knowledge-base-backend'}

    @app.get('/ready', tags=['健康检查'])
    def ready():
        state = {}
        checks = {'postgresql': lambda: session_factory().connection(),
                  'redis': app.state.infrastructure.cache.ready,
                  'minio': app.state.infrastructure.storage.ready,
                  'milvus': app.state.infrastructure.vectors.ready}
        for name, check in checks.items():
            try:
                if name == 'postgresql':
                    with session_factory() as db:
                        db.execute(text('SELECT 1'))
                    state[name] = True
                else:
                    state[name] = bool(check())
            except Exception:
                state[name] = False
        return JSONResponse({'ready': all(state.values()), 'services': state},
                            status_code=200 if all(state.values()) else 503)

    for router in [auth.router, organization.router, knowledge.router, ai.router,
                   dashboard.router, settlement.router, settings_router.router]:
        app.include_router(router, prefix='/api')
    return app
