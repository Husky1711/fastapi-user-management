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
    import pytest

    return pytest.main(
        [
            "--confcutdir=tests/smoke",
            "tests/smoke",
            "-m",
            "smoke",
            "-v",
            "--tb=long",
            "--capture=no",
            "--maxfail=5",
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
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
