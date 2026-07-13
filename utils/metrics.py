"""In-process Prometheus-style metrics (no external client required)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Dict, Tuple


class AppMetrics:
    """Process-local counters and latency buckets for /metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.http_requests_total: Dict[Tuple[str, str, str], int] = defaultdict(int)
        self.http_request_duration_seconds_sum: Dict[Tuple[str, str], float] = defaultdict(float)
        self.http_request_duration_seconds_count: Dict[Tuple[str, str], int] = defaultdict(int)
        self.auth_failures_total = 0
        self.auth_lockouts_total = 0
        self.rate_limit_hits_total = 0
        self.refresh_reuse_total = 0

    def observe_request(
        self, method: str, path: str, status_code: int, duration_seconds: float
    ) -> None:
        # Collapse high-cardinality IDs: /api/v1/users/12 -> /api/v1/users/{id}
        normalized = _normalize_path(path)
        key = (method.upper(), normalized, str(status_code))
        dur_key = (method.upper(), normalized)
        with self._lock:
            self.http_requests_total[key] += 1
            self.http_request_duration_seconds_sum[dur_key] += duration_seconds
            self.http_request_duration_seconds_count[dur_key] += 1

    def inc_auth_failure(self) -> None:
        with self._lock:
            self.auth_failures_total += 1

    def inc_auth_lockout(self) -> None:
        with self._lock:
            self.auth_lockouts_total += 1

    def inc_rate_limit(self) -> None:
        with self._lock:
            self.rate_limit_hits_total += 1

    def inc_refresh_reuse(self) -> None:
        with self._lock:
            self.refresh_reuse_total += 1

    def render_prometheus(self) -> str:
        lines = [
            "# HELP app_uptime_seconds Process uptime in seconds",
            "# TYPE app_uptime_seconds gauge",
            f"app_uptime_seconds {time.time() - self.start_time:.3f}",
            "# HELP http_requests_total Total HTTP requests",
            "# TYPE http_requests_total counter",
        ]
        with self._lock:
            for (method, path, code), count in sorted(self.http_requests_total.items()):
                lines.append(
                    f'http_requests_total{{method="{method}",path="{path}",status="{code}"}} {count}'
                )
            lines.append("# HELP http_request_duration_seconds_sum Sum of request durations")
            lines.append("# TYPE http_request_duration_seconds_sum counter")
            for (method, path), total in sorted(self.http_request_duration_seconds_sum.items()):
                lines.append(
                    f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total:.6f}'
                )
            lines.append(
                "# HELP http_request_duration_seconds_count Count of observed request durations"
            )
            lines.append("# TYPE http_request_duration_seconds_count counter")
            for (method, path), count in sorted(
                self.http_request_duration_seconds_count.items()
            ):
                lines.append(
                    f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count}'
                )
            lines.extend(
                [
                    "# HELP auth_failures_total Failed authentication attempts",
                    "# TYPE auth_failures_total counter",
                    f"auth_failures_total {self.auth_failures_total}",
                    "# HELP auth_lockouts_total Account lockouts triggered",
                    "# TYPE auth_lockouts_total counter",
                    f"auth_lockouts_total {self.auth_lockouts_total}",
                    "# HELP rate_limit_hits_total Rate-limit rejections",
                    "# TYPE rate_limit_hits_total counter",
                    f"rate_limit_hits_total {self.rate_limit_hits_total}",
                    "# HELP refresh_token_reuse_total Detected refresh token reuse events",
                    "# TYPE refresh_token_reuse_total counter",
                    f"refresh_token_reuse_total {self.refresh_reuse_total}",
                ]
            )
        return "\n".join(lines) + "\n"


def _normalize_path(path: str) -> str:
    parts = path.split("/")
    out = []
    for part in parts:
        if part.isdigit():
            out.append("{id}")
        else:
            out.append(part)
    return "/".join(out) or "/"


metrics = AppMetrics()
