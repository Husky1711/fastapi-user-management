import time
from typing import Optional

import redis

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
    """Redis client singleton with circuit breaker.

    After consecutive connection failures, skips further connect/ping attempts for a
    cooldown window (exponential backoff, capped) so callers fail fast under Redis outage.
    """

    _instance: Optional[redis.Redis] = None
    _failures: int = 0
    _open_until: float = 0.0
    _last_error: Optional[str] = None

    @classmethod
    def reset_circuit(cls) -> None:
        """Reset breaker state (tests / recovery hooks)."""
        cls._failures = 0
        cls._open_until = 0.0
        cls._last_error = None

    @classmethod
    def circuit_is_open(cls) -> bool:
        return time.monotonic() < cls._open_until

    @classmethod
    def _cooldown_seconds(cls) -> float:
        base = float(settings.redis.circuit_cooldown_seconds)
        # Failures beyond threshold escalate: 1x, 2x, 4x, ...
        open_count = max(0, cls._failures - settings.redis.circuit_failure_threshold + 1)
        delay = base * (2 ** max(0, open_count - 1))
        return min(delay, float(settings.redis.circuit_max_cooldown_seconds))

    @classmethod
    def _record_success(cls) -> None:
        cls._failures = 0
        cls._open_until = 0.0
        cls._last_error = None

    @classmethod
    def _record_failure(cls, error: Exception) -> None:
        cls._failures += 1
        cls._last_error = str(error)
        cls._instance = None
        if cls._failures >= settings.redis.circuit_failure_threshold:
            cooldown = cls._cooldown_seconds()
            cls._open_until = time.monotonic() + cooldown
            api_logger.warning(
                "Redis circuit opened",
                failures=cls._failures,
                cooldown_seconds=round(cooldown, 2),
                error=str(error),
                event_type="redis_circuit_open",
            )

    @classmethod
    def get_client(cls) -> redis.Redis:
        """Get Redis client instance (raises if circuit is open)."""
        if cls.circuit_is_open():
            raise redis.ConnectionError(
                f"Redis circuit open until cooldown ends "
                f"(last_error={cls._last_error!r})"
            )
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=RedisConfig.REDIS_HOST,
                port=RedisConfig.REDIS_PORT,
                db=RedisConfig.REDIS_DB,
                password=RedisConfig.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=settings.redis.socket_connect_timeout,
                socket_timeout=settings.redis.socket_timeout,
                retry_on_timeout=settings.redis.retry_on_timeout,
            )
        return cls._instance

    @classmethod
    def test_connection(cls) -> bool:
        """Test Redis connection (honors open circuit — no connect storms)."""
        if cls.circuit_is_open():
            return False
        try:
            client = cls.get_client()
            client.ping()
            cls._record_success()
            return True
        except Exception as e:
            cls._record_failure(e)
            # Avoid log spam while approaching / in open state more than once per open.
            if cls._failures <= settings.redis.circuit_failure_threshold:
                api_logger.error(
                    f"Redis connection failed: {e}",
                    error=str(e),
                    host=RedisConfig.REDIS_HOST,
                    port=RedisConfig.REDIS_PORT,
                    failures=cls._failures,
                    event_type="redis_connection_failed",
                )
            return False
