"""
Cache Service for Redis-based caching
Handles caching of user profiles, sessions, and permissions
"""

from typing import Optional, Dict, Any
import json
from datetime import timedelta
from utils.redis_config import RedisClient
from utils.loggers import api_logger
from config.settings import settings


class CacheService:
    """Redis-based cache service for user data"""
    
    # Cache TTL constants (in seconds)
    PROFILE_CACHE_TTL = 600  # 10 minutes
    SESSION_CACHE_TTL = 86400  # 24 hours
    PERMISSION_CACHE_TTL = 1800  # 30 minutes
    AUDIT_CACHE_TTL = 300  # 5 minutes
    
    def __init__(self):
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            if RedisClient.test_connection():
                self.redis_client = RedisClient.get_client()
                api_logger.debug("Cache service connected to Redis")
            else:
                api_logger.warning("Redis not available, caching disabled")
        except Exception as e:
            api_logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis_client = None
    
    # ==================== USER PROFILE CACHING ====================
    
    def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user profile from cache"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"user_profile:{user_id}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
        except Exception as e:
            api_logger.error(f"Error getting user profile from cache: {str(e)}")
            return None
    
    def set_user_profile(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """Cache user profile"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"user_profile:{user_id}"
            cache_data = json.dumps(user_data)
            self.redis_client.setex(
                cache_key,
                self.PROFILE_CACHE_TTL,
                cache_data
            )
            api_logger.debug(f"Cached user profile for user_id: {user_id}")
            return True
        except Exception as e:
            api_logger.error(f"Error caching user profile: {str(e)}")
            return False
    
    def invalidate_user_profile(self, user_id: int) -> bool:
        """Invalidate user profile cache"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"user_profile:{user_id}"
            self.redis_client.delete(cache_key)
            api_logger.debug(f"Invalidated user profile cache for user_id: {user_id}")
            return True
        except Exception as e:
            api_logger.error(f"Error invalidating user profile cache: {str(e)}")
            return False
    
    # ==================== SESSION CACHING ====================
    
    def get_user_sessions(self, user_id: int) -> Optional[list]:
        """Get user sessions from cache"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"user_sessions:{user_id}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
        except Exception as e:
            api_logger.error(f"Error getting sessions from cache: {str(e)}")
            return None
    
    def set_user_sessions(self, user_id: int, sessions: list) -> bool:
        """Cache user sessions"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"user_sessions:{user_id}"
            cache_data = json.dumps(sessions)
            self.redis_client.setex(
                cache_key,
                self.SESSION_CACHE_TTL,
                cache_data
            )
            api_logger.debug(f"Cached sessions for user_id: {user_id}")
            return True
        except Exception as e:
            api_logger.error(f"Error caching sessions: {str(e)}")
            return False
    
    def invalidate_user_sessions(self, user_id: int) -> bool:
        """Invalidate user sessions cache"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"user_sessions:{user_id}"
            self.redis_client.delete(cache_key)
            api_logger.debug(f"Invalidated sessions cache for user_id: {user_id}")
            return True
        except Exception as e:
            api_logger.error(f"Error invalidating sessions cache: {str(e)}")
            return False
    
    # ==================== PERMISSION CACHING ====================
    
    def get_user_permissions(self, user_id: int) -> Optional[list]:
        """Get user permissions from cache"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"user_permissions:{user_id}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
        except Exception as e:
            api_logger.error(f"Error getting permissions from cache: {str(e)}")
            return None
    
    def set_user_permissions(self, user_id: int, permissions: list) -> bool:
        """Cache user permissions"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"user_permissions:{user_id}"
            cache_data = json.dumps(permissions)
            self.redis_client.setex(
                cache_key,
                self.PERMISSION_CACHE_TTL,
                cache_data
            )
            api_logger.debug(f"Cached permissions for user_id: {user_id}")
            return True
        except Exception as e:
            api_logger.error(f"Error caching permissions: {str(e)}")
            return False
    
    def invalidate_user_permissions(self, user_id: int) -> bool:
        """Invalidate user permissions cache"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"user_permissions:{user_id}"
            self.redis_client.delete(cache_key)
            api_logger.debug(f"Invalidated permissions cache for user_id: {user_id}")
            return True
        except Exception as e:
            api_logger.error(f"Error invalidating permissions cache: {str(e)}")
            return False
    
    # ==================== AUDIT LOG CACHING ====================
    
    def get_audit_logs(self, user_id: int, limit: int = 50) -> Optional[list]:
        """Get audit logs from cache"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"audit_logs:{user_id}:{limit}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
        except Exception as e:
            api_logger.error(f"Error getting audit logs from cache: {str(e)}")
            return None
    
    def set_audit_logs(self, user_id: int, logs: list, limit: int = 50) -> bool:
        """Cache audit logs"""
        if not self.redis_client:
            return False
        
        try:
            cache_key = f"audit_logs:{user_id}:{limit}"
            cache_data = json.dumps(logs)
            self.redis_client.setex(
                cache_key,
                self.AUDIT_CACHE_TTL,
                cache_data
            )
            api_logger.debug(f"Cached audit logs for user_id: {user_id}")
            return True
        except Exception as e:
            api_logger.error(f"Error caching audit logs: {str(e)}")
            return False
    
    def invalidate_audit_logs(self, user_id: int) -> bool:
        """Invalidate audit logs cache"""
        if not self.redis_client:
            return False
        
        try:
            # Invalidate all audit log caches for this user
            pattern = f"audit_logs:{user_id}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                api_logger.debug(f"Invalidated audit logs cache for user_id: {user_id}")
            return True
        except Exception as e:
            api_logger.error(f"Error invalidating audit logs cache: {str(e)}")
            return False
    
    # ==================== CACHE INVALIDATION ====================
    
    def invalidate_all_user_cache(self, user_id: int) -> bool:
        """Invalidate all cache entries for a user"""
        if not self.redis_client:
            return False
        
        try:
            # Try to get keys with wildcards
            audit_pattern = f"audit_logs:{user_id}:*"
            audit_keys = self.redis_client.keys(audit_pattern)
            
            # List of specific keys to delete
            keys_to_delete = [
                f"user_profile:{user_id}",
                f"user_sessions:{user_id}",
                f"user_permissions:{user_id}"
            ]
            
            # Add audit log keys if found
            if audit_keys:
                keys_to_delete.extend(audit_keys)
            
            # Delete all keys
            cleared_keys = 0
            if keys_to_delete:
                # Delete in batches to avoid issues
                deleted = self.redis_client.delete(*keys_to_delete)
                cleared_keys = deleted if deleted else 0
            
            api_logger.info(
                f"Invalidated all cache for user_id: {user_id}",
                user_id=user_id,
                keys_cleared=cleared_keys,
                event_type="cache_invalidation"
            )
            return True
        except Exception as e:
            api_logger.error(f"Error invalidating all user cache: {str(e)}")
            return False
    
    def clear_all_cache(self) -> bool:
        """Clear all cache (use with caution)"""
        if not self.redis_client:
            return False
        
        try:
            # This would be dangerous in production, but useful for testing
            if not settings.app.env == "development":
                api_logger.warning("Attempted to clear all cache in non-development environment")
                return False
            
            self.redis_client.flushdb()
            api_logger.info("Cleared all cache")
            return True
        except Exception as e:
            api_logger.error(f"Error clearing all cache: {str(e)}")
            return False
    
    # ==================== GENERIC CACHE METHODS ====================
    
    def get_cache(self, cache_key: str) -> Optional[Any]:
        """Get generic cache entry"""
        if not self.redis_client:
            return None
        
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            api_logger.error(f"Error getting cache: {str(e)}")
            return None
    
    def set_cache(self, cache_key: str, data: Any, ttl: int = 300) -> bool:
        """Set generic cache entry"""
        if not self.redis_client:
            return False
        
        try:
            cache_data = json.dumps(data)
            self.redis_client.setex(cache_key, ttl, cache_data)
            return True
        except Exception as e:
            api_logger.error(f"Error setting cache: {str(e)}")
            return False


# Global cache service instance
cache_service = CacheService()

