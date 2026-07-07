#!/usr/bin/env python3
"""
FastAPI User Management System - Production Ready Main Application
Enterprise-grade user management with comprehensive security and monitoring
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from contextlib import asynccontextmanager
import os
import time
from typing import Dict, Any
from sqlalchemy import text

# Import routers
from routes.login import router as login_router
from routes.production_endpoints import router as production_router
from routes.auth_2fa import router as auth_2fa_router
from routes.organizations import router as organizations_router

# Import utilities
from utils.loggers import app_logger, security_logger
from utils.security_middleware import setup_security_middleware, setup_error_handlers
from utils.redis_config import RedisClient
from utils.database import engine
from config.settings import settings

# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
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
    
    yield
    
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

# Setup error handlers
setup_error_handlers(app)

# Include routers
app.include_router(login_router)
app.include_router(production_router)
app.include_router(auth_2fa_router)
app.include_router(organizations_router)

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
        health_status["services"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check Redis
    if RedisClient.test_connection():
        health_status["services"]["redis"] = {"status": "healthy", "type": "redis"}
    else:
        health_status["services"]["redis"] = {"status": "unhealthy", "error": "Connection failed"}
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/health/ready", tags=["Health"])
async def readiness_check() -> Dict[str, Any]:
    """Kubernetes readiness probe endpoint"""
    try:
        # Check if all critical services are ready
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        if not RedisClient.test_connection():
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "Redis unavailable"}
            )
        
        return {"status": "ready", "timestamp": time.time()}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": str(e)}
        )

@app.get("/health/live", tags=["Health"])
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe endpoint"""
    return {"status": "alive", "timestamp": time.time()}

# Legacy health check endpoint for backward compatibility
@app.get("/hello", tags=["Health"])
async def hello_world() -> Dict[str, Any]:
    """Legacy hello world endpoint"""
    app_logger.info("Hello world endpoint accessed", endpoint="/hello")
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
        "api_health_check": "/api/v1/health"
    }

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    start_time = time.time()
    
    # Get request ID from state (set by RequestIDMiddleware)
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log request (this will be handled by RequestIDMiddleware, but keeping for reference)
    app_logger.info(
        f"Request processed: {request.method} {request.url.path}",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        process_time=round(process_time, 4),
        request_id=request_id,
        client_ip=request.client.host if request.client else "unknown",
        event_type="request_processed"
    )
    
    return response

# Application startup event (deprecated in favor of lifespan)
@app.on_event("startup")
async def startup_event():
    """Application startup event (deprecated - use lifespan instead)"""
    app_logger.warning("Using deprecated startup event - consider using lifespan", event_type="deprecated_event")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event (deprecated - use lifespan instead)"""
    app_logger.warning("Using deprecated shutdown event - consider using lifespan", event_type="deprecated_event")

if __name__ == "__main__":
    # Production-ready server configuration
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