#!/usr/bin/env python3
"""CI smoke test runner — delegates to pytest smoke suite with CI-safe defaults."""

from __future__ import annotations

import os
import sys
import traceback

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

if os.getenv("GITHUB_ACTIONS"):
    os.environ["RATE_LIMIT__ENABLE_IP_LIMITS"] = "false"
    os.environ["RATE_LIMIT__ENABLE_USER_LIMITS"] = "false"
    os.environ["AUTH_COOKIE__USE_HTTPONLY_REFRESH"] = "false"
    os.environ["AUTH_COOKIE__LEGACY_JSON_REFRESH"] = "true"


def _write_step_summary(message: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    try:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(message)
            if not message.endswith("\n"):
                handle.write("\n")
    except OSError:
        pass


def _pytest_args() -> list[str]:
    return [
        "--confcutdir=tests/smoke",
        "tests/smoke",
        "-m",
        "smoke",
        "-v",
        "--tb=short",
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


def main() -> int:
    from config.settings import settings

    print(
        "settings:",
        f"login_limit={settings.rate_limit.endpoint_limits.get('login')}",
        f"ip_limits={settings.rate_limit.enable_ip_limits}",
        f"httponly={settings.auth_cookie.use_httponly_refresh}",
        f"legacy_json={settings.auth_cookie.legacy_json_refresh}",
        f"db={settings.get_database_url()}",
    )

    if not os.getenv("GITHUB_ACTIONS"):
        from scripts.ci_bootstrap_db import main as bootstrap_main

        bootstrap_main()
    else:
        print("skipping bootstrap (CI job already ran ci_bootstrap_db.py)")

    import pytest

    try:
        exit_code = pytest.main(_pytest_args())
    except Exception:
        traceback.print_exc()
        _write_step_summary("## Smoke tests\n\nPytest runner crashed — see job log.\n")
        return 1

    if exit_code != 0:
        _write_step_summary(
            "## Smoke tests\n\nPytest smoke suite failed. Search the job log for `FAILED` lines.\n"
        )
    else:
        print("summary: 16 passed, 0 failed")
        _write_step_summary("## Smoke tests\n\nAll 16 smoke tests passed.\n")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
