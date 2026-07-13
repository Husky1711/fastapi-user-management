#!/usr/bin/env python3
"""
Performance monitoring utility — in-process timers + optional psutil system samples.

Prefer ``GET /metrics`` (Prometheus) for production scraping; this module is for
local diagnostics and optional background sampling.
"""

import time
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass
from collections import defaultdict, deque
from utils.loggers import api_logger

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""

    name: str
    value: float
    timestamp: float
    unit: str
    tags: Dict[str, str]


class PerformanceMonitor:
    """Monitor application performance metrics"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        self.active_timers: Dict[str, float] = {}
        self.system_metrics_enabled = True
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        self._process = psutil.Process() if psutil is not None else None

    def start_timer(self, operation: str) -> None:
        """Start timing an operation"""
        self.active_timers[operation] = time.time()

    def end_timer(self, operation: str, tags: Optional[Dict[str, str]] = None) -> float:
        """End timing an operation and record the metric"""
        if operation not in self.active_timers:
            return 0.0

        duration_ms = (time.time() - self.active_timers[operation]) * 1000
        del self.active_timers[operation]

        metric = PerformanceMetric(
            name=f"{operation}_duration",
            value=duration_ms,
            timestamp=time.time(),
            unit="ms",
            tags=tags or {},
        )

        self.record_metric(metric)
        return duration_ms

    def record_metric(self, metric: PerformanceMetric) -> None:
        """Record a performance metric"""
        self.metrics_history[metric.name].append(metric)

        if "duration" in metric.name and metric.value > 1000:
            api_logger.slow_request(
                method=metric.tags.get("method", "unknown"),
                endpoint=metric.tags.get("endpoint", "unknown"),
                duration_ms=metric.value,
                threshold_ms=1000,
                ip_address=metric.tags.get("ip_address", "unknown"),
                user_id=int(metric.tags.get("user_id"))
                if metric.tags.get("user_id")
                else None,
                correlation_id=metric.tags.get("correlation_id"),
            )

    def get_metric_stats(
        self, metric_name: str, time_window_minutes: int = 60
    ) -> Dict[str, float]:
        """Get statistics for a metric over a time window"""
        if metric_name not in self.metrics_history:
            return {}

        cutoff_time = time.time() - (time_window_minutes * 60)
        recent_metrics = [
            m
            for m in self.metrics_history[metric_name]
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {}

        values = [m.value for m in recent_metrics]

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p50": sorted(values)[len(values) // 2],
            "p95": sorted(values)[int(len(values) * 0.95)],
            "p99": sorted(values)[int(len(values) * 0.99)],
        }

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current process/host metrics via psutil when available."""
        try:
            base: Dict[str, Any] = {
                "timestamp": time.time(),
                "monitoring_active": self.monitoring_thread is not None
                and self.monitoring_thread.is_alive(),
                "active_timers": len(self.active_timers),
                "metrics_count": sum(len(d) for d in self.metrics_history.values()),
                "psutil_available": psutil is not None,
            }
            if psutil is None or self._process is None:
                return base

            with self._process.oneshot():
                mem = self._process.memory_info()
                base.update(
                    {
                        "process_cpu_percent": self._process.cpu_percent(interval=None),
                        "process_rss_bytes": mem.rss,
                        "process_vms_bytes": mem.vms,
                        "process_num_threads": self._process.num_threads(),
                        "host_cpu_percent": psutil.cpu_percent(interval=None),
                        "host_memory_percent": psutil.virtual_memory().percent,
                    }
                )
            return base
        except Exception as e:
            api_logger.error(f"Failed to get system metrics: {e}")
            return {"error": str(e), "psutil_available": psutil is not None}

    def start_system_monitoring(self, interval_seconds: int = 60) -> None:
        """Start monitoring system metrics"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return

        self.stop_monitoring.clear()
        self.monitoring_thread = threading.Thread(
            target=self._monitor_system_metrics,
            args=(interval_seconds,),
            daemon=True,
        )
        self.monitoring_thread.start()

    def stop_system_monitoring(self) -> None:
        """Stop monitoring system metrics"""
        self.stop_monitoring.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)

    def _monitor_system_metrics(self, interval_seconds: int) -> None:
        """Monitor system metrics in background thread"""
        while not self.stop_monitoring.wait(interval_seconds):
            try:
                metrics = self.get_system_metrics()
                api_logger.info(
                    f"Performance monitoring active: {metrics.get('monitoring_active')}",
                    active_timers=metrics.get("active_timers"),
                    metrics_count=metrics.get("metrics_count"),
                    process_cpu_percent=metrics.get("process_cpu_percent"),
                    process_rss_bytes=metrics.get("process_rss_bytes"),
                    host_memory_percent=metrics.get("host_memory_percent"),
                    event_type="monitoring_status",
                )
            except Exception as e:
                api_logger.error(f"Error in system monitoring: {e}")

    def get_performance_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get performance summary for the last time window"""
        summary: Dict[str, Any] = {
            "time_window_minutes": time_window_minutes,
            "timestamp": time.time(),
            "metrics": {},
        }

        for metric_name in (
            "api_request_duration",
            "database_query_duration",
            "auth_login_duration",
            "auth_signup_duration",
        ):
            stats = self.get_metric_stats(metric_name, time_window_minutes)
            if stats:
                summary["metrics"][metric_name] = stats

        summary["system"] = self.get_system_metrics()
        return summary

    def log_performance_summary(self, time_window_minutes: int = 60) -> None:
        """Log performance summary"""
        summary = self.get_performance_summary(time_window_minutes)
        api_logger.info(
            f"Performance summary for last {time_window_minutes} minutes",
            performance_summary=summary,
            event_type="performance_summary",
        )


performance_monitor = PerformanceMonitor()


def start_timer(operation: str) -> None:
    performance_monitor.start_timer(operation)


def end_timer(operation: str, tags: Optional[Dict[str, str]] = None) -> float:
    return performance_monitor.end_timer(operation, tags)


def record_custom_metric(
    name: str,
    value: float,
    unit: str = "count",
    tags: Optional[Dict[str, str]] = None,
) -> None:
    performance_monitor.record_metric(
        PerformanceMetric(
            name=name,
            value=value,
            timestamp=time.time(),
            unit=unit,
            tags=tags or {},
        )
    )


def get_performance_stats(
    metric_name: str, time_window_minutes: int = 60
) -> Dict[str, float]:
    return performance_monitor.get_metric_stats(metric_name, time_window_minutes)
