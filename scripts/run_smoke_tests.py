#!/usr/bin/env python3
"""Run smoke tests with parent conftest/plugins excluded."""

from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

if os.getenv("GITHUB_ACTIONS"):
    os.environ.setdefault("RATE_LIMIT__ENABLE_IP_LIMITS", "false")
    os.environ.setdefault("RATE_LIMIT__ENABLE_USER_LIMITS", "false")
    os.environ.setdefault("AUTH_COOKIE__USE_HTTPONLY_REFRESH", "false")
    os.environ.setdefault("AUTH_COOKIE__LEGACY_JSON_REFRESH", "true")


def main() -> int:
    from config.settings import settings

    print(
        "smoke settings:",
        f"ip_limits={settings.rate_limit.enable_ip_limits}",
        f"httponly={settings.auth_cookie.use_httponly_refresh}",
        f"db={settings.get_database_url()}",
    )

    import pytest

    return pytest.main(
        [
            "--confcutdir=tests/smoke",
            "tests/smoke/test_auth_smoke.py::test_login_refresh_logout",
            "-v",
            "--tb=long",
            "--capture=no",
            "-p",
            "no:locust",
            "-p",
            "no:faker",
            "-p",
            "no:cov",
            "-p",
            "no:html",
            "-p",
            "no:metadata",
            "-p",
            "no:xdist",
            "-p",
            "no:anyio",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
