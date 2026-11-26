import redis
from typing import Optional
from config.settings import settings
from utils.loggers import api_logger

class RedisConfig:
    """Redis configuration for rate limiting"""
    
    # Get Redis settings from centralized configuration
    REDIS_HOST = settings.redis.host
    REDIS_PORT = settings.redis.port
    REDIS_DB = settings.redis.db
    REDIS_PASSWORD = settings.redis.password
    
    # Rate limiting settings
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX_REQUESTS = 100  # per window
    
    # Get endpoint limits from centralized configuration
    ENDPOINT_LIMITS = settings.rate_limit.endpoint_limits
    
    # Get global IP limits from centralized configuration
    GLOBAL_IP_LIMITS = settings.rate_limit.global_ip_limits

class RedisClient:
    """Redis client singleton"""
    _instance: Optional[redis.Redis] = None
    
    @classmethod
    def get_client(cls) -> redis.Redis:
        """Get Redis client instance"""
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=RedisConfig.REDIS_HOST,
                port=RedisConfig.REDIS_PORT,
                db=RedisConfig.REDIS_DB,
                password=RedisConfig.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=settings.redis.socket_connect_timeout,
                socket_timeout=settings.redis.socket_timeout,
                retry_on_timeout=settings.redis.retry_on_timeout
            )
        return cls._instance
    
    @classmethod
    def test_connection(cls) -> bool:
        """Test Redis connection"""
        try:
            client = cls.get_client()
            client.ping()
            return True
        except Exception as e:
            api_logger.error(
                f"Redis connection failed: {e}",
                error=str(e),
                host=RedisConfig.REDIS_HOST,
                port=RedisConfig.REDIS_PORT,
                event_type="redis_connection_failed"
            )
            return False
