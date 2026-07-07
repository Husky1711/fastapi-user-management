#!/usr/bin/env python3
"""
Enhanced Logout Service
Handles user logout with Redis cache cleanup
"""

from sqlalchemy.orm import Session
from typing import Optional, List
from .refresh_token_service import RefreshTokenService
from utils.redis_config import RedisClient
from utils.loggers import auth_logger, security_logger
from models.user_model import User
import time

class LogoutService:
    """Enhanced logout service with Redis cache cleanup"""
    
    @staticmethod
    def logout_user(
        db: Session, 
        refresh_token: str, 
        user_id: Optional[int] = None
    ) -> bool:
        """
        Logout user with comprehensive cleanup
        
        Args:
            db: Database session
            refresh_token: Refresh token to revoke
            user_id: Optional user ID for additional cleanup
            
        Returns:
            bool: Success status
        """
        try:
            # Revoke the refresh token in database
            success = RefreshTokenService.revoke_token(db, refresh_token)
            
            if not success:
                return False
            
            # If user_id is provided, perform additional cleanup
            if user_id:
                LogoutService._clear_user_redis_cache(user_id)
                LogoutService._clear_user_rate_limits(user_id)
            
            auth_logger.info(
                f"User logout successful",
                user_id=user_id,
                event_type="logout_success"
            )
            
            return True
            
        except Exception as e:
            auth_logger.error(
                f"Logout error: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="logout_error"
            )
            return False
    
    @staticmethod
    def logout_all_user_sessions(
        db: Session, 
        user_id: int
    ) -> int:
        """
        Logout user from all sessions with Redis cleanup
        
        Args:
            db: Database session
            user_id: User ID to logout
            
        Returns:
            int: Number of sessions revoked
        """
        try:
            # Revoke all refresh tokens for the user
            revoked_count = RefreshTokenService.revoke_all_user_tokens(db, user_id)
            
            # Clear all Redis cache for the user
            LogoutService._clear_user_redis_cache(user_id)
            LogoutService._clear_user_rate_limits(user_id)
            
            from services.sessions import UserSessionService

            UserSessionService.deactivate_user_sessions(
                db, user_id, reason="logout_all"
            )
            
            security_logger.info(
                f"All user sessions revoked",
                user_id=user_id,
                sessions_revoked=revoked_count,
                event_type="logout_all_sessions"
            )
            
            return revoked_count
            
        except Exception as e:
            security_logger.error(
                f"Logout all sessions error: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="logout_all_sessions_error"
            )
            return 0
    
    @staticmethod
    def _clear_user_redis_cache(user_id: int):
        """Clear user-specific Redis cache"""
        try:
            if not RedisClient.test_connection():
                return
            
            client = RedisClient.get_client()
            
            # Pattern for user-specific cache keys
            user_cache_patterns = [
                f"user:{user_id}:*",           # User data cache
                f"user_session:{user_id}:*",   # Session cache
                f"user_profile:{user_id}:*",    # Profile cache
                f"user_permissions:{user_id}:*", # Permissions cache
            ]
            
            cleared_keys = 0
            for pattern in user_cache_patterns:
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
                    cleared_keys += len(keys)
            
            if cleared_keys > 0:
                auth_logger.info(
                    f"Cleared user Redis cache",
                    user_id=user_id,
                    keys_cleared=cleared_keys,
                    event_type="redis_cache_clear"
                )
                
        except Exception as e:
            auth_logger.error(
                f"Redis cache clear error: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="redis_cache_clear_error"
            )
    
    @staticmethod
    def _clear_user_rate_limits(user_id: int):
        """Clear user-specific rate limiting data"""
        try:
            if not RedisClient.test_connection():
                return
            
            client = RedisClient.get_client()
            
            # Pattern for user rate limiting keys
            rate_limit_pattern = f"rate_limit:*:user:{user_id}:*"
            
            keys = client.keys(rate_limit_pattern)
            if keys:
                client.delete(*keys)
                
                auth_logger.info(
                    f"Cleared user rate limits",
                    user_id=user_id,
                    rate_limit_keys_cleared=len(keys),
                    event_type="rate_limit_clear"
                )
                
        except Exception as e:
            auth_logger.error(
                f"Rate limit clear error: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="rate_limit_clear_error"
            )
    
    @staticmethod
    def get_user_from_refresh_token(db: Session, refresh_token: str) -> Optional[User]:
        """Get user from refresh token before logout"""
        try:
            return RefreshTokenService.verify_refresh_token(db, refresh_token)
        except:
            return None
    
    @staticmethod
    def cleanup_expired_sessions(db: Session) -> int:
        """Cleanup expired sessions and their Redis data"""
        try:
            # Clean expired tokens from database
            expired_count = RefreshTokenService.cleanup_expired_tokens(db)
            
            if expired_count > 0:
                auth_logger.info(
                    f"Cleaned up expired sessions",
                    expired_sessions=expired_count,
                    event_type="session_cleanup"
                )
            
            return expired_count
            
        except Exception as e:
            auth_logger.error(
                f"Session cleanup error: {str(e)}",
                error=str(e),
                event_type="session_cleanup_error"
            )
            return 0
