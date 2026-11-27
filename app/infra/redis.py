"""Redis client (async)."""

import inspect

from redis.asyncio import Redis

from app.core.config import RedisSettings


def create_redis(settings: RedisSettings) -> Redis:
    return Redis.from_url(
        settings.url.get_secret_value(),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )


async def ping_redis(client: Redis) -> None:
    # redis-py types ping() as "awaitable or bool" because the same stub serves the sync client.
    result = client.ping()
    if inspect.isawaitable(result):
        await result
