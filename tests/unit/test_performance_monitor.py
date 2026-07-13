"""Smoke test for performance monitor psutil wiring."""

from utils.performance_monitor import performance_monitor


def test_get_system_metrics_includes_psutil_fields() -> None:
    metrics = performance_monitor.get_system_metrics()
    assert metrics.get("psutil_available") is True
    assert "process_rss_bytes" in metrics
    assert "host_memory_percent" in metrics
