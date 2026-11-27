"""Application factory.

Run with:  uvicorn app.main:create_app --factory
"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from functools import partial
from typing import Any

from fastapi import APIRouter, FastAPI

from app import __version__
from app.api import health
from app.api.v1 import build_api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
    ErrorBoundaryMiddleware,
    ProblemCORSMiddleware,
    RequestContextMiddleware,
)
from app.core.security import start_password_hashing, stop_password_hashing
from app.infra.database import create_engine, create_session_factory, ping_database
from app.infra.redis import create_redis, ping_redis
from app.schemas.errors import COMMON_ERROR_RESPONSES, PROBLEM_SCHEMAS
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
    app.state.session_factory = create_session_factory(engine)
    app.state.redis = redis
    start_password_hashing(settings.auth.password_hash_workers)
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
        await asyncio.to_thread(stop_password_hashing)  # lets in-flight hashes finish
        log.info("shutdown")


def _add_problem_schemas(app: FastAPI) -> None:
    """Register the error schemas that the routes' error responses refer to."""
    generate = app.openapi

    # Any: an OpenAPI document is arbitrary JSON.
    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = generate()  # also caches it on app.openapi_schema
            schema.setdefault("components", {}).setdefault("schemas", {}).update(PROBLEM_SCHEMAS)
        return app.openapi_schema or {}

    # FastAPI's documented way to customise the schema is to replace this method.
    app.openapi = openapi  # type: ignore[method-assign]


def create_app(
    settings: Settings | None = None,
    *,
    health_checks: Mapping[str, HealthCheck] | None = None,
    api_routers: Sequence[APIRouter] = (),
) -> FastAPI:
    """Build the app. Fails fast if settings are unsafe for a staging or production environment.

    `health_checks` replaces the default database/Redis readiness checks, and `api_routers`
    adds routers under `/api/v1` (both used by tests).
    """
    settings = settings or get_settings()
    settings.ensure_safe()
    configure_logging(settings.log.level, queue_size=settings.log.queue_size)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
        responses=COMMON_ERROR_RESPONSES,
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
            ProblemCORSMiddleware,
            allow_origins=list(settings.cors.allow_origins),
            allow_credentials=settings.cors.allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    app.add_middleware(RequestContextMiddleware, enable_hsts=settings.is_strict)

    app.include_router(health.router)
    app.include_router(build_api_router(*api_routers))
    _add_problem_schemas(app)
    return app
