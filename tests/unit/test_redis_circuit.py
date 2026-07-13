"""Unit tests for Redis circuit breaker."""

from __future__ import annotations

import time

from config.settings import settings
from utils.redis_config import RedisClient


def test_redis_circuit_opens_after_threshold(monkeypatch) -> None:
    RedisClient.reset_circuit()
    RedisClient._instance = None

    monkeypatch.setattr(settings.redis, "circuit_failure_threshold", 2)
    monkeypatch.setattr(settings.redis, "circuit_cooldown_seconds", 60)
    monkeypatch.setattr(settings.redis, "circuit_max_cooldown_seconds", 60)

    class _Boom:
        def ping(self):
            raise ConnectionError("redis down")

    monkeypatch.setattr(
        RedisClient,
        "get_client",
        classmethod(lambda cls: _Boom()),
    )

    assert RedisClient.test_connection() is False
    assert RedisClient.test_connection() is False
    assert RedisClient.circuit_is_open() is True
    # While open — fail fast without further connect attempts
    assert RedisClient.test_connection() is False

    RedisClient.reset_circuit()
    assert RedisClient.circuit_is_open() is False


def test_redis_circuit_recovers_after_cooldown() -> None:
    RedisClient.reset_circuit()
    RedisClient._failures = 5
    RedisClient._open_until = time.monotonic() + 0.05
    assert RedisClient.circuit_is_open() is True
    time.sleep(0.06)
    assert RedisClient.circuit_is_open() is False
    RedisClient.reset_circuit()
