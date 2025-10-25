#!/usr/bin/env python3
"""
Auto Refresh Token Middleware
Middleware to handle automatic token refresh in FastAPI
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Optional, Dict, Any
import asyncio
import time
from datetime import datetime, timedelta
from utils.loggers import auth_logger
from config.settings import settings

class AutoRefreshMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic token refresh"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.refresh_cache: Dict[str, Dict[str, Any]] = {}
        self.refresh_lock = asyncio.Lock()
    
    async def dispatch(self, request: Request, call_next):
        """Process request and handle token refresh"""
        
        # Only process requests with Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return await call_next(request)
        
        token = auth_header.split(" ")[1]
        
        # Check if token needs refresh
        if await self._needs_refresh(token):
            try:
                # Attempt to refresh token
                new_token = await self._refresh_token(token)
                if new_token:
                    # Update Authorization header
                    request.headers["Authorization"] = f"Bearer {new_token}"
                    
                    auth_logger.info(
                        f"Token auto-refreshed for request to {request.url.path}",
                        path=request.url.path,
                        method=request.method,
                        event_type="auto_refresh_middleware"
                    )
            except Exception as e:
                auth_logger.error(
                    f"Auto refresh failed: {str(e)}",
                    path=request.url.path,
                    error=str(e),
                    event_type="auto_refresh_middleware_error"
                )
                # Continue with original token - let the endpoint handle auth failure
        
        # Process the request
        response = await call_next(request)
        
        # Add refresh hint header if token is close to expiry
        if await self._is_token_close_to_expiry(token):
            response.headers["X-Token-Refresh-Soon"] = "true"
        
        return response
    
    async def _needs_refresh(self, token: str) -> bool:
        """Check if token needs refresh"""
        try:
            # Decode token to check expiry
            from utils.jwt_config import verify_token
            payload = verify_token(token)
            
            if not payload:
                return False
            
            exp_timestamp = payload.get("exp")
            if not exp_timestamp:
                return False
            
            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            time_until_expiry = (exp_datetime - datetime.utcnow()).total_seconds()
            
            # Refresh if token expires in less than 1 minute
            return time_until_expiry < 60
            
        except Exception:
            return False
    
    async def _is_token_close_to_expiry(self, token: str) -> bool:
        """Check if token is close to expiry (for hint header)"""
        try:
            from utils.jwt_config import verify_token
            payload = verify_token(token)
            
            if not payload:
                return False
            
            exp_timestamp = payload.get("exp")
            if not exp_timestamp:
                return False
            
            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            time_until_expiry = (exp_datetime - datetime.utcnow()).total_seconds()
            
            # Close to expiry if less than 2 minutes
            return time_until_expiry < 120
            
        except Exception:
            return False
    
    async def _refresh_token(self, token: str) -> Optional[str]:
        """Attempt to refresh the token"""
        async with self.refresh_lock:
            # Check cache first
            cache_key = f"refresh_{hash(token)}"
            if cache_key in self.refresh_cache:
                cached_data = self.refresh_cache[cache_key]
                if time.time() - cached_data["timestamp"] < 30:  # Cache for 30 seconds
                    return cached_data["new_token"]
            
            try:
                # Extract refresh token from request context
                # This would need to be passed through request state
                refresh_token = getattr(request.state, 'refresh_token', None)
                
                if not refresh_token:
                    return None
                
                # Call refresh service
                from services.auth import AuthService
                from utils.database import get_db
                
                # This is a simplified version - in real implementation,
                # you'd need to handle database sessions properly
                new_access_token, new_refresh_token = AuthService.refresh_access_token(
                    db=None,  # Would need proper DB session
                    refresh_token=refresh_token,
                    device_info="Auto-refresh middleware",
                    ip_address="127.0.0.1",
                    user_agent="Auto-refresh"
                )
                
                # Cache the result
                self.refresh_cache[cache_key] = {
                    "new_token": new_access_token,
                    "timestamp": time.time()
                }
                
                return new_access_token
                
            except Exception as e:
                auth_logger.error(
                    f"Token refresh failed: {str(e)}",
                    error=str(e),
                    event_type="token_refresh_failed"
                )
                return None

# Alternative: Background Refresh Service
class BackgroundRefreshService:
    """Background service for proactive token refresh"""
    
    def __init__(self):
        self.refresh_tasks: Dict[str, asyncio.Task] = {}
        self.refresh_intervals: Dict[str, int] = {}
    
    async def start_user_refresh(self, user_id: int, refresh_token: str):
        """Start background refresh for a user"""
        task_id = f"user_{user_id}"
        
        if task_id in self.refresh_tasks:
            await self.stop_user_refresh(user_id)
        
        # Start background task
        task = asyncio.create_task(self._user_refresh_loop(user_id, refresh_token))
        self.refresh_tasks[task_id] = task
        
        auth_logger.info(
            f"Started background refresh for user {user_id}",
            user_id=user_id,
            event_type="background_refresh_started"
        )
    
    async def _user_refresh_loop(self, user_id: int, refresh_token: str):
        """Background loop for user token refresh"""
        try:
            while True:
                # Wait for refresh interval (4 minutes for 5-minute tokens)
                await asyncio.sleep(240)
                
                try:
                    # Attempt refresh
                    from services.auth import AuthService
                    from utils.database import get_db
                    
                    new_access_token, new_refresh_token = AuthService.refresh_access_token(
                        db=None,  # Would need proper DB session
                        refresh_token=refresh_token,
                        device_info="Background refresh service",
                        ip_address="127.0.0.1",
                        user_agent="Background refresh"
                    )
                    
                    refresh_token = new_refresh_token  # Update for next iteration
                    
                    auth_logger.info(
                        f"Background refresh successful for user {user_id}",
                        user_id=user_id,
                        event_type="background_refresh_success"
                    )
                    
                except Exception as e:
                    auth_logger.error(
                        f"Background refresh failed for user {user_id}: {str(e)}",
                        user_id=user_id,
                        error=str(e),
                        event_type="background_refresh_failed"
                    )
                    break
                    
        except asyncio.CancelledError:
            auth_logger.info(
                f"Background refresh cancelled for user {user_id}",
                user_id=user_id,
                event_type="background_refresh_cancelled"
            )
    
    async def stop_user_refresh(self, user_id: int):
        """Stop background refresh for a user"""
        task_id = f"user_{user_id}"
        
        if task_id in self.refresh_tasks:
            task = self.refresh_tasks[task_id]
            task.cancel()
            del self.refresh_tasks[task_id]
            
            auth_logger.info(
                f"Stopped background refresh for user {user_id}",
                user_id=user_id,
                event_type="background_refresh_stopped"
            )

# Global instances
background_refresh_service = BackgroundRefreshService()
