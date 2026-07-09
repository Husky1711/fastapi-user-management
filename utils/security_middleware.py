#!/usr/bin/env python3
"""
Security Middleware for FastAPI
Production-ready security middleware including CORS, HTTPS redirect, and security headers
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import time
import uuid
from typing import Callable
from config.settings import settings
from utils.loggers import security_logger, api_logger

DOCS_PATH_PREFIXES = ("/docs", "/redoc", "/openapi.json")


def _is_docs_path(path: str) -> bool:
    return path == "/openapi.json" or path.startswith(DOCS_PATH_PREFIXES[:2])


def _content_security_policy(path: str) -> str:
    """Swagger UI and ReDoc load assets from cdn.jsdelivr.net — strict CSP breaks /docs."""
    if _is_docs_path(path) and not settings.is_production():
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Add HSTS header for HTTPS
        if settings.security.enable_https_redirect:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Add Content Security Policy
        response.headers["Content-Security-Policy"] = _content_security_policy(
            request.url.path
        )
        
        return response

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID for tracing"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(round(process_time, 4))
        
        # Log request
        api_logger.info(
            f"{request.method} {request.url.path}",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time=round(process_time, 4),
            request_id=request_id,
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown"),
            event_type="api_request"
        )
        
        return response

class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log security-related events"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        # Log suspicious patterns
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        path = request.url.path
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "admin", "login", "wp-admin", "phpmyadmin", 
            "sql", "union", "select", "drop", "delete",
            "script", "alert", "javascript", "eval"
        ]
        
        is_suspicious = any(pattern in path.lower() for pattern in suspicious_patterns)
        
        if is_suspicious:
            security_logger.warning(
                f"Suspicious request pattern detected: {path}",
                client_ip=client_ip,
                user_agent=user_agent,
                path=path,
                method=request.method,
                event_type="suspicious_request"
            )
        
        response = await call_next(request)
        
        # Log failed requests
        if response.status_code >= 400:
            security_logger.warning(
                f"Failed request: {response.status_code}",
                client_ip=client_ip,
                user_agent=user_agent,
                path=path,
                method=request.method,
                status_code=response.status_code,
                event_type="failed_request"
            )
        
        return response

def setup_security_middleware(app: FastAPI) -> None:
    """Setup all security middleware for the FastAPI application"""
    
    # Add request ID middleware first
    app.add_middleware(RequestIDMiddleware)
    
    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Add security logging middleware
    app.add_middleware(SecurityLoggingMiddleware)
    
    # Add HTTPS redirect middleware (only in production)
    if settings.security.enable_https_redirect and settings.app.environment == "production":
        app.add_middleware(HTTPSRedirectMiddleware)
        security_logger.info("HTTPS redirect middleware enabled", event_type="middleware_setup")
    
    # Add CORS middleware (explicit origins + credentials for browser SPA)
    if settings.security.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.security.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
        )
    
    security_logger.info(
        "Security middleware setup completed",
        cors_origins=settings.security.cors_origins,
        https_redirect=settings.security.enable_https_redirect,
        environment=settings.app.environment,
        event_type="middleware_setup"
    )

def setup_error_handlers(app: FastAPI) -> None:
    """Setup custom error handlers"""
    
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
    from utils.api_errors import APIHTTPException, error_payload
    import traceback
    
    @app.exception_handler(APIHTTPException)
    async def api_http_exception_handler(request: Request, exc: APIHTTPException):
        """Handle structured API exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")

        security_logger.error(
            f"API Exception: {exc.detail}",
            status_code=exc.status_code,
            error_code=exc.error_code,
            path=request.url.path,
            method=request.method,
            request_id=request_id,
            event_type="api_exception",
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc, request_id, time.time()),
            headers=exc.headers,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with proper logging"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        security_logger.error(
            f"HTTP Exception: {exc.detail}",
            status_code=exc.status_code,
            path=request.url.path,
            method=request.method,
            request_id=request_id,
            event_type="http_exception"
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc, request_id, time.time()),
            headers=exc.headers,
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors with proper logging"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        security_logger.warning(
            f"Validation Error: {str(exc.errors())}",
            path=request.url.path,
            method=request.method,
            request_id=request_id,
            errors=str(exc.errors()),
            event_type="validation_error"
        )

        field_errors = {
            ".".join(str(part) for part in error.get("loc", ()) if part != "body"): str(
                error.get("msg", "")
            )
            for error in exc.errors()
        }
        
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "error_code": "VALIDATION_ERROR",
                "fields": field_errors,
                "status_code": 422,
                "correlation_id": request_id,
                "timestamp": time.time(),
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions with proper logging"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        security_logger.error(
            f"Unhandled Exception: {str(exc)}",
            path=request.url.path,
            method=request.method,
            request_id=request_id,
            error=str(exc),
            traceback=traceback.format_exc(),
            event_type="unhandled_exception"
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "status_code": 500,
                "request_id": request_id,
                "timestamp": time.time()
            }
        )

# Export the main setup function
__all__ = ["setup_security_middleware", "setup_error_handlers"]
