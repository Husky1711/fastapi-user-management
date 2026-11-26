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
from app.core.middleware import RequestContextMiddleware
from app.infra.database import create_engine, ping_database
from app.infra.redis import create_redis, ping_redis

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    engine = create_engine(settings.database)
    redis = create_redis(settings.redis)
    app.state.engine = engine
    app.state.redis = redis
    if app.state.health_checks is None:
        app.state.health_checks = {
            "database": partial(ping_database, engine),
            "redis": partial(ping_redis, redis),
        }
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
    health_checks: Mapping[str, health.HealthCheck] | None = None,
) -> FastAPI:
    """Build the app. Fails fast if production settings are unsafe.

    `health_checks` replaces the default database/Redis readiness checks (used by tests).
    """
    settings = settings or get_settings()
    settings.ensure_safe_for_production()
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
    app.state.health_checks = health_checks

    register_exception_handlers(app)

    if settings.cors.allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors.allow_origins,
            allow_credentials=settings.cors.allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    # Added last so it is the outermost layer: every response, including CORS preflights
    # and unhandled errors, gets a request id and security headers.
    app.add_middleware(RequestContextMiddleware, enable_hsts=settings.is_production)

    app.include_router(health.router)
    app.include_router(api_router)
    return app
