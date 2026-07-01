from fastapi import Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from services.core import RateLimitService
from services.auth import AuthService
from utils.database import get_db
from utils.redis_config import RedisClient
from utils.loggers import api_logger
from utils.api_errors import APIHTTPException

security = HTTPBearer()

class RateLimitDependency:
    """Rate limiting dependency for FastAPI endpoints"""
    
    @staticmethod
    def get_user_from_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
    ) -> Optional[int]:
        """Extract user ID from JWT token"""
        try:
            user = AuthService.get_current_user(db, credentials.credentials)
            return user.id if user else None
        except:
            return None
    
    @staticmethod
    def check_rate_limit(endpoint: str, require_auth: bool = True):
        """Create rate limiting dependency"""
        async def rate_limit_check(
            request: Request,
            db: Session = Depends(get_db)
        ):
            # Get IP address
            ip_address = request.client.host if request.client else "unknown"
            
            # Check if Redis is available
            if not RedisClient.test_connection():
                # If Redis is down, allow request but log warning
                api_logger.warning(
                    "Redis unavailable, skipping rate limiting",
                    ip_address=ip_address,
                    endpoint=endpoint,
                    event_type="redis_unavailable"
                )
                return
            
            # Check IP-based rate limits first
            ip_allowed, ip_remaining = RateLimitService.check_ip_rate_limit(ip_address, endpoint)
            
            if not ip_allowed:
                retry_after = RateLimitService.get_retry_after(ip_remaining)
                raise APIHTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for IP. Try again in {retry_after} seconds.",
                    error_code="RATE_LIMIT_EXCEEDED",
                    headers={
                        "X-RateLimit-Limit": str(max(ip_remaining.values()) if ip_remaining else 0),
                        "X-RateLimit-Remaining": str(min(ip_remaining.values()) if ip_remaining else 0),
                        "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                        "Retry-After": str(retry_after)
                    }
                )
            
            # If user is authenticated, check user-specific limits
            if require_auth:
                try:
                    # Try to get credentials from Authorization header
                    auth_header = request.headers.get("Authorization")
                    if auth_header and auth_header.startswith("Bearer "):
                        token = auth_header.split(" ")[1]
                        user = AuthService.get_current_user(db, token)
                        if user:
                            user_allowed, user_remaining = RateLimitService.check_user_rate_limit(user.id, endpoint)
                            
                            if not user_allowed:
                                retry_after = RateLimitService.get_retry_after(user_remaining)
                                raise APIHTTPException(
                                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                    detail=f"Rate limit exceeded for user. Try again in {retry_after} seconds.",
                                    error_code="RATE_LIMIT_EXCEEDED",
                                    headers={
                                        "X-RateLimit-Limit": str(max(user_remaining.values()) if user_remaining else 0),
                                        "X-RateLimit-Remaining": str(min(user_remaining.values()) if user_remaining else 0),
                                        "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                                        "Retry-After": str(retry_after)
                                    }
                                )
                except:
                    # If token is invalid, continue with IP-based limits only
                    pass
        
        return rate_limit_check

# Import time for the dependency
import time
