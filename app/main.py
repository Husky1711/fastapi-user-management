"""Application factory.

Run with:  uvicorn app.main:create_app --factory
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import health
from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import ErrorBoundaryMiddleware, RequestContextMiddleware
from app.infra.database import create_engine, ping_database
from app.infra.redis import create_redis, ping_redis
from app.services.health import HealthCheck, ReadinessProbe

log = get_logger(__name__)


def _readiness_probe(settings: Settings, checks: Mapping[str, HealthCheck]) -> ReadinessProbe:
    return ReadinessProbe(
        checks,
        limit_seconds=settings.health.check_timeout_seconds,
        cache_seconds=settings.health.cache_seconds,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    engine = create_engine(settings.database)
    redis = create_redis(settings.redis)
    app.state.engine = engine
    app.state.redis = redis
    # Rebuilt on every start, so the checks always point at this lifespan's live resources.
    injected: Mapping[str, HealthCheck] | None = app.state.injected_health_checks
    checks = (
        injected
        if injected is not None
        else {"database": partial(ping_database, engine), "redis": partial(ping_redis, redis)}
    )
    app.state.readiness = _readiness_probe(settings, checks)
    log.info("startup", environment=settings.environment, version=__version__)
    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()
        log.info("shutdown")


def create_app(
    settings: Settings | None = None,
    *,
    health_checks: Mapping[str, HealthCheck] | None = None,
) -> FastAPI:
    """Build the app. Fails fast if settings are unsafe for a staging or production environment.

    `health_checks` replaces the default database/Redis readiness checks (used by tests).
    """
    settings = settings or get_settings()
    settings.ensure_safe()
    configure_logging(settings.log.level)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.injected_health_checks = health_checks
    # Until the lifespan has started (or if it never runs), there is nothing to check: the
    # probe has no checks and therefore reports not ready.
    app.state.readiness = _readiness_probe(settings, health_checks or {})

    register_exception_handlers(app)

    # Middleware added first runs innermost. Order, outside → in:
    # RequestContext (request id, headers, log) → CORS → ErrorBoundary (500s) → app
    app.add_middleware(ErrorBoundaryMiddleware)
    if settings.cors.allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors.allow_origins),
            allow_credentials=settings.cors.allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    app.add_middleware(RequestContextMiddleware, enable_hsts=settings.is_strict)

    app.include_router(health.router)
    app.include_router(api_router)
    return app
