#!/usr/bin/env python3
"""ADR-002 browser auth checklist: httpOnly cookie, CORS credentials, cookie refresh."""

from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Browser-auth mode (must be set before Settings is imported).
os.environ.setdefault("AUTH_COOKIE__USE_HTTPONLY_REFRESH", "true")
os.environ.setdefault("AUTH_COOKIE__LEGACY_JSON_REFRESH", "true")
os.environ.setdefault("AUTH_COOKIE__SECURE", "false")
os.environ.setdefault("SECURITY__CORS_ORIGINS", '["http://localhost:5173"]')
os.environ.setdefault("RATE_LIMIT__ENABLE_IP_LIMITS", "false")
os.environ.setdefault("RATE_LIMIT__ENABLE_USER_LIMITS", "false")

ORIGIN = os.getenv("CHECKLIST_ORIGIN", "http://localhost:5173")
CHECKLIST_USER = os.getenv("CHECKLIST_USER", "testuser")
CHECKLIST_PASSWORD = os.getenv("CHECKLIST_PASSWORD", "user123")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    from config.settings import settings
    from fastapi.testclient import TestClient

    if not os.getenv("GITHUB_ACTIONS"):
        from scripts.ci_bootstrap_db import main as bootstrap_main

        bootstrap_main()

    print(
        "checklist settings:",
        f"httponly={settings.auth_cookie.use_httponly_refresh}",
        f"legacy_json={settings.auth_cookie.legacy_json_refresh}",
        f"secure={settings.auth_cookie.secure}",
        f"cors={settings.security.cors_origins}",
    )

    from main import app

    with TestClient(app) as client:
        preflight = client.options(
            "/api/v1/login",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        _assert(
            preflight.headers.get("access-control-allow-credentials") == "true",
            f"CORS credentials missing on preflight: {preflight.headers}",
        )
        _assert(
            preflight.headers.get("access-control-allow-origin") == ORIGIN,
            f"CORS origin mismatch: {preflight.headers.get('access-control-allow-origin')}",
        )
        print("PASS cors_preflight")

        login = client.post(
            "/api/v1/login",
            json={"username": CHECKLIST_USER, "password": CHECKLIST_PASSWORD},
            headers={"Origin": ORIGIN},
        )
        _assert(login.status_code == 200, f"login failed: {login.status_code} {login.text}")
        set_cookie = login.headers.get("set-cookie", "")
        _assert("refresh_token" in set_cookie, f"Set-Cookie missing refresh_token: {set_cookie}")
        _assert("httponly" in set_cookie.lower(), f"Set-Cookie not HttpOnly: {set_cookie}")
        _assert(
            login.headers.get("access-control-allow-credentials") == "true",
            "login missing Access-Control-Allow-Credentials",
        )
        print("PASS login_set_cookie")

        refresh = client.post(
            "/api/v1/refresh",
            headers={"Origin": ORIGIN},
        )
        _assert(refresh.status_code == 200, f"refresh failed: {refresh.status_code} {refresh.text}")
        _assert(refresh.json().get("access_token"), f"refresh missing access_token: {refresh.json()}")
        rotated = refresh.headers.get("set-cookie", "")
        _assert("refresh_token" in rotated, f"refresh missing rotated Set-Cookie: {rotated}")
        print("PASS cookie_refresh")

        logout = client.post(
            "/api/v1/logout",
            headers={"Origin": ORIGIN},
        )
        _assert(logout.status_code == 200, f"logout failed: {logout.status_code} {logout.text}")
        cleared = logout.headers.get("set-cookie", "")
        _assert("refresh_token" in cleared.lower(), f"logout missing cookie clear: {cleared}")
        print("PASS logout_clear_cookie")

    print("summary: adr002_auth_checklist passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("FAIL adr002_auth_checklist", exc)
        raise
