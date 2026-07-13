#!/usr/bin/env python3
"""
FastAPI User Management System - Production Ready Main Application
Enterprise-grade user management with comprehensive security and monitoring
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from contextlib import asynccontextmanager
import asyncio
import os
import time
from typing import Dict, Any
from sqlalchemy import text

# Import routers
from routes.auth import router as auth_router
from routes.sessions import router as sessions_router
from routes.users import router as users_router
from routes.profile import router as profile_router
from routes.production_endpoints import router as production_router
from routes.audit import router as audit_router
from routes.retention import router as retention_router
from routes.integration import router as integration_router
from routes.auth_2fa import router as auth_2fa_router
from routes.organizations import router as organizations_router
from routes.invitations import router as invitations_router
from routes.compliance import router as compliance_router

# Import utilities
from utils.loggers import app_logger, security_logger
from utils.security_middleware import setup_security_middleware, setup_error_handlers
from utils.redis_config import RedisClient
from utils.database import engine
from config.settings import settings


def _allow_db_startup_fail_open() -> bool:
    """True only for automated test runners — never in production."""
    if settings.is_production():
        return False
    env = (settings.app.environment or "").lower()
    if env in {"test", "testing"}:
        return True
    return bool(
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("TESTING")
        or os.getenv("GITHUB_ACTIONS")
    )


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    settings.validate_production_config()

    app_logger.info(
        "FastAPI User Management System starting up",
        version=settings.app.version,
        environment=settings.app.environment,
        debug_mode=settings.app.debug,
        event_type="app_startup"
    )
    
    # Test database connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        app_logger.info("Database connection successful", event_type="db_startup")
    except Exception as e:
        app_logger.error(
            f"Database connection failed: {str(e)}",
            error=str(e),
            event_type="db_startup_error"
        )
        # Fail-open only for automated tests — never in production (or staging-like).
        # CI/pytest may hit transient pool errors across many TestClient lifespans.
        if not _allow_db_startup_fail_open():
            raise
    
    # Test Redis connection
    if RedisClient.test_connection():
        app_logger.info("Redis connection successful", event_type="redis_startup")
    else:
        app_logger.warning("Redis connection failed - rate limiting may not work", event_type="redis_startup_warning")
    
    # Log security configuration
    security_logger.info(
        "Security configuration loaded",
        cors_enabled=settings.security.enable_cors,
        https_redirect=settings.security.enable_https_redirect,
        max_login_attempts=settings.security.max_login_attempts,
        lockout_duration=settings.security.lockout_duration_minutes,
        event_type="security_config"
    )

    retention_task = None
    if settings.app.enable_retention_job:

        async def _retention_loop() -> None:
            from utils.database import SessionLocal
            from services.core.retention_service import RetentionService

            interval = settings.app.retention_interval_minutes * 60
            while True:
                await asyncio.sleep(interval)
                db = SessionLocal()
                try:
                    RetentionService.run_all(db)
                except Exception as exc:
                    app_logger.error(
                        f"Retention job failed: {exc}",
                        error=str(exc),
                        event_type="retention_job_error",
                    )
                finally:
                    db.close()

        retention_task = asyncio.create_task(_retention_loop())
        app_logger.info(
            "Retention background job enabled",
            interval_minutes=settings.app.retention_interval_minutes,
            event_type="retention_job_started",
        )
    
    yield

    if retention_task is not None:
        retention_task.cancel()
        try:
            await retention_task
        except asyncio.CancelledError:
            pass
    
    # Shutdown
    app_logger.info("FastAPI User Management System shutting down", event_type="app_shutdown")

# Create FastAPI application
_root_path = os.getenv("FASTAPI_ROOT_PATH", "")
app = FastAPI(
    title=settings.app.name,
    description=settings.app.description,
    version=settings.app.version,
    debug=settings.app.debug,
    root_path=_root_path,
    docs_url="/docs" if settings.app.environment != "production" else None,
    redoc_url="/redoc" if settings.app.environment != "production" else None,
    openapi_url="/openapi.json" if settings.app.environment != "production" else None,
    lifespan=lifespan
)

# Setup security middleware
setup_security_middleware(app)

# Optional OpenTelemetry (OTEL__ENABLED=true + requirements-otel.txt)
from utils.otel import setup_otel

setup_otel(app)

# Setup error handlers
setup_error_handlers(app)

# Include routers
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(users_router)
app.include_router(profile_router)
app.include_router(invitations_router)
if settings.is_development() and settings.security.allow_debug_auth:
    from routes.debug import router as debug_router

    app.include_router(debug_router)
app.include_router(production_router)  # sessions_admin, permissions, groups, api_keys, password
app.include_router(audit_router)
app.include_router(retention_router)
app.include_router(integration_router)
app.include_router(auth_2fa_router)
app.include_router(organizations_router)
app.include_router(compliance_router)

# Include dashboard router
from routes.dashboard import router as dashboard_router
app.include_router(dashboard_router)

# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.app.version,
        "environment": settings.app.environment
    }

@app.get("/api/v1/health", tags=["Health"])
async def api_health_check() -> Dict[str, Any]:
    """API versioned health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.app.version,
        "environment": settings.app.environment,
        "api_version": "v1"
    }

@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with system status"""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.app.version,
        "environment": settings.app.environment,
        "services": {}
    }
    
    # Check database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["services"]["database"] = {"status": "healthy", "type": "mysql"}
    except Exception as e:
        app_logger.error(
            f"Detailed health DB check failed: {e}",
            error=str(e),
            event_type="health_detailed_db_error",
        )
        db_payload: Dict[str, Any] = {"status": "unhealthy", "type": "mysql"}
        if settings.app.environment != "production":
            db_payload["error"] = str(e)
        else:
            db_payload["error"] = "database unhealthy"
        health_status["services"]["database"] = db_payload
        health_status["status"] = "degraded"
    
    # Check Redis
    if RedisClient.test_connection():
        health_status["services"]["redis"] = {"status": "healthy", "type": "redis"}
    else:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": "Connection failed",
        }
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/health/ready", tags=["Health"])
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes readiness probe — database only (Redis optional for traffic)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "timestamp": time.time()}
    except Exception as e:
        app_logger.error(
            f"Readiness DB check failed: {e}",
            error=str(e),
            event_type="health_ready_db_error",
        )
        reason = (
            "database unavailable"
            if settings.app.environment == "production"
            else str(e)
        )
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": reason},
        )


@app.get("/health/ready-full", tags=["Health"])
async def readiness_check_full() -> Dict[str, Any]:
    """Stricter readiness: database + Redis (rate limiting / sessions)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        app_logger.error(
            f"Full readiness DB check failed: {e}",
            error=str(e),
            event_type="health_ready_full_db_error",
        )
        reason = (
            "database unavailable"
            if settings.app.environment == "production"
            else str(e)
        )
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": reason},
        )

    if not RedisClient.test_connection():
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "Redis unavailable"},
        )

    return {"status": "ready", "timestamp": time.time()}

@app.get("/health/live", tags=["Health"])
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe endpoint"""
    return {"status": "alive", "timestamp": time.time()}


@app.get("/metrics", tags=["Observability"])
async def prometheus_metrics():
    """Prometheus text exposition of in-process app metrics."""
    from utils.metrics import metrics

    return PlainTextResponse(
        metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )

# Dev-only smoke endpoint (not registered in production)
if settings.app.environment == "development":

    @app.get("/hello", tags=["Health"])
    async def hello_world() -> Dict[str, Any]:
        """Legacy hello world — development only."""
        return {"message": "Hello World", "status": "healthy"}

# Root endpoint
@app.get("/", tags=["Root"])
async def root(request: Request):
    """Root endpoint with API information (browsers in dev are sent to Swagger UI)."""
    if settings.app.environment == "development" and "text/html" in request.headers.get(
        "accept", ""
    ):
        return RedirectResponse(url="/docs")

    return {
        "message": f"Welcome to {settings.app.name}",
        "version": settings.app.version,
        "description": settings.app.description,
        "environment": settings.app.environment,
        "api_version": "v1",
        "api_base_url": "/api/v1",
        "docs_url": "/docs" if settings.app.environment != "production" else "disabled",
        "health_check": "/health",
        "api_health_check": "/api/v1/health",
        "readiness": "/health/ready",
        "readiness_full": "/health/ready-full",
    }

if __name__ == "__main__":
    # Prefer K8s/Compose replicas with --workers 1 (see docs/DEPLOYMENT_TOPOLOGY.md).
    # Multi-worker here is a single-VM convenience only — watch DB pool × workers.
    uvicorn.run(
        "main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.reload and settings.app.environment == "development",
        log_level=settings.logging.level.lower(),
        access_log=True,
        workers=1 if settings.app.environment == "development" else 4,
        loop="asyncio",
        http="httptools" if settings.app.environment == "production" else "auto"
    )
