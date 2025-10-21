import time
from typing import Dict, Tuple, Optional
from utils.redis_config import RedisClient, RedisConfig
from config.settings import settings
from utils.loggers import api_logger

class RateLimitService:
    """Redis-based rate limiting service"""
    
    @staticmethod
    def _get_key_prefix(endpoint: str, identifier: str) -> str:
        """Generate Redis key prefix"""
        return f"rate_limit:{endpoint}:{identifier}"
    
    @staticmethod
    def _get_time_windows() -> Dict[str, int]:
        """Get time windows for rate limiting"""
        return {
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }
    
    @staticmethod
    def check_rate_limit(
        endpoint: str, 
        identifier: str, 
        limits: Dict[str, int]
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is within rate limits
        
        Args:
            endpoint: API endpoint name
            identifier: User ID or IP address
            limits: Rate limits for different time windows
            
        Returns:
            Tuple of (is_allowed, remaining_counts)
        """
        try:
            client = RedisClient.get_client()
            current_time = int(time.time())
            
            remaining_counts = {}
            is_allowed = True
            
            for window_name, limit in limits.items():
                window_seconds = RateLimitService._get_time_windows()[window_name]
                key = f"{RateLimitService._get_key_prefix(endpoint, identifier)}:{window_name}"
                
                # Use sliding window counter
                pipe = client.pipeline()
                
                # Remove expired entries
                pipe.zremrangebyscore(key, 0, current_time - window_seconds)
                
                # Count current requests
                pipe.zcard(key)
                
                # Add current request
                pipe.zadd(key, {str(current_time): current_time})
                
                # Set expiration
                pipe.expire(key, window_seconds)
                
                results = pipe.execute()
                current_count = results[1]
                
                if current_count >= limit:
                    is_allowed = False
                
                remaining_counts[window_name] = max(0, limit - current_count)
            
            return is_allowed, remaining_counts
            
        except Exception as e:
            api_logger.error(
                f"Rate limiting error: {e}",
                error=str(e),
                endpoint=endpoint,
                identifier=identifier,
                event_type="rate_limit_error"
            )
            # Use centralized fail-open setting
            if settings.rate_limit.fail_open:
                # Fallback: Allow request if Redis is down (fail open)
                remaining_counts = {window: limit for window, limit in limits.items()}
                return True, remaining_counts
            else:
                # Fail closed for security
                return False, {}
    
    @staticmethod
    def get_rate_limit_info(
        endpoint: str, 
        identifier: str, 
        limits: Dict[str, int]
    ) -> Dict[str, int]:
        """Get current rate limit information without incrementing"""
        try:
            client = RedisClient.get_client()
            current_time = int(time.time())
            
            remaining_counts = {}
            
            for window_name, limit in limits.items():
                window_seconds = RateLimitService._get_time_windows()[window_name]
                key = f"{RateLimitService._get_key_prefix(endpoint, identifier)}:{window_name}"
                
                # Remove expired entries and count
                pipe = client.pipeline()
                pipe.zremrangebyscore(key, 0, current_time - window_seconds)
                pipe.zcard(key)
                
                results = pipe.execute()
                current_count = results[1]
                
                remaining_counts[window_name] = max(0, limit - current_count)
            
            return remaining_counts
            
        except Exception as e:
            api_logger.error(
                f"Rate limit info error: {e}",
                error=str(e),
                endpoint=endpoint,
                identifier=identifier,
                event_type="rate_limit_info_error"
            )
            return {}
    
    @staticmethod
    def check_user_rate_limit(user_id: int, endpoint: str) -> Tuple[bool, Dict[str, int]]:
        """Check rate limit for authenticated user"""
        if endpoint not in RedisConfig.ENDPOINT_LIMITS:
            return True, {}
        
        limits = RedisConfig.ENDPOINT_LIMITS[endpoint]
        return RateLimitService.check_rate_limit(endpoint, f"user:{user_id}", limits)
    
    @staticmethod
    def check_ip_rate_limit(ip_address: str, endpoint: str) -> Tuple[bool, Dict[str, int]]:
        """Check rate limit for IP address"""
        # Check global IP limits first
        global_allowed, global_remaining = RateLimitService.check_rate_limit(
            "global_ip", ip_address, RedisConfig.GLOBAL_IP_LIMITS
        )
        
        if not global_allowed:
            return False, global_remaining
        
        # Check endpoint-specific limits
        if endpoint not in RedisConfig.ENDPOINT_LIMITS:
            return True, global_remaining
        
        limits = RedisConfig.ENDPOINT_LIMITS[endpoint]
        endpoint_allowed, endpoint_remaining = RateLimitService.check_rate_limit(
            endpoint, ip_address, limits
        )
        
        return endpoint_allowed, endpoint_remaining
    
    @staticmethod
    def get_retry_after(remaining_counts: Dict[str, int]) -> int:
        """Calculate retry after seconds"""
        if not remaining_counts:
            return 60
        
        # Find the window with the lowest remaining count
        min_window = min(remaining_counts.keys(), key=lambda x: remaining_counts[x])
        
        if remaining_counts[min_window] <= 0:
            # Return the window duration
            windows = RateLimitService._get_time_windows()
            return windows.get(min_window, 60)
        
        return 0
