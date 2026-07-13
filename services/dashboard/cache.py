"""Shared Redis cache helpers for dashboard endpoints.

Keys: ``dashboard:v1:{scope}:{name}`` (optional ``:org:{id}``).
Default TTL: 60 seconds. Invalidate after user/org mutations.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, TypeVar

from utils.loggers import api_logger

DASHBOARD_CACHE_PREFIX = "dashboard:v1"
DASHBOARD_CACHE_TTL_SECONDS = 60

T = TypeVar("T")


def dashboard_cache_key(*parts: Any) -> str:
    """Build a stable dashboard cache key from path parts."""
    cleaned = [str(p).strip(":") for p in parts if p is not None and str(p) != ""]
    return ":".join([DASHBOARD_CACHE_PREFIX, *cleaned])


def get_dashboard_cache(key: str) -> Optional[Any]:
    try:
        from services.core import cache_service

        return cache_service.get_cache(key)
    except Exception as exc:
        api_logger.warning(
            f"Dashboard cache get failed: {exc}",
            cache_key=key,
            error=str(exc),
            event_type="dashboard_cache_get_error",
        )
        return None


def set_dashboard_cache(
    key: str,
    data: Any,
    ttl: int = DASHBOARD_CACHE_TTL_SECONDS,
) -> bool:
    try:
        from services.core import cache_service

        return bool(cache_service.set_cache(key, data, ttl=ttl))
    except Exception as exc:
        api_logger.warning(
            f"Dashboard cache set failed: {exc}",
            cache_key=key,
            error=str(exc),
            event_type="dashboard_cache_set_error",
        )
        return False


def cached_dashboard(key: str, builder: Callable[[], T], ttl: int = DASHBOARD_CACHE_TTL_SECONDS) -> T:
    """Return cached value or compute, store, and return."""
    hit = get_dashboard_cache(key)
    if hit is not None:
        return hit  # type: ignore[return-value]
    result = builder()
    set_dashboard_cache(key, result, ttl=ttl)
    return result


def invalidate_dashboard_caches(*, organization_id: Optional[int] = None) -> None:
    """Drop super-admin dashboard keys (and org-scoped keys when provided)."""
    try:
        from services.core import cache_service

        client = getattr(cache_service, "redis_client", None)
        if not client:
            return

        patterns = [f"{DASHBOARD_CACHE_PREFIX}:super_admin:*"]
        if organization_id is not None:
            patterns.append(f"{DASHBOARD_CACHE_PREFIX}:*:org:{organization_id}:*")
            patterns.append(f"{DASHBOARD_CACHE_PREFIX}:*:org:{organization_id}")

        deleted = 0
        for pattern in patterns:
            keys = list(client.scan_iter(match=pattern, count=100))
            if keys:
                deleted += int(client.delete(*keys) or 0)

        # Legacy key from early extract
        if client.delete("super_admin:overview"):
            deleted += 1

        if deleted:
            api_logger.info(
                "Dashboard caches invalidated",
                keys_cleared=deleted,
                organization_id=organization_id,
                event_type="dashboard_cache_invalidation",
            )
    except Exception as exc:
        api_logger.warning(
            f"Dashboard cache invalidation failed: {exc}",
            error=str(exc),
            organization_id=organization_id,
            event_type="dashboard_cache_invalidation_error",
        )
