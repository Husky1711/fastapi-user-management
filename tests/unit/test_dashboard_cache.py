"""Unit tests for dashboard cache key helpers."""

from services.dashboard.cache import (
    DASHBOARD_CACHE_PREFIX,
    dashboard_cache_key,
)


def test_dashboard_cache_key_stable() -> None:
    assert dashboard_cache_key("super_admin", "overview") == (
        f"{DASHBOARD_CACHE_PREFIX}:super_admin:overview"
    )
    assert dashboard_cache_key("admin", "overview", "org", 3) == (
        f"{DASHBOARD_CACHE_PREFIX}:admin:overview:org:3"
    )
