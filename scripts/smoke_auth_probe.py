#!/usr/bin/env python3
"""Run auth smoke flow with verbose prints (for CI diagnosis)."""

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
    from fastapi.testclient import TestClient
    from scripts.ci_bootstrap_db import main as bootstrap_main

    print(
        "settings:",
        f"login_limit={settings.rate_limit.endpoint_limits.get('login')}",
        f"ip_limits={settings.rate_limit.enable_ip_limits}",
        f"httponly={settings.auth_cookie.use_httponly_refresh}",
        f"legacy_json={settings.auth_cookie.legacy_json_refresh}",
    )

    bootstrap_main()

    from main import app

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/login",
            json={"username": "testuser", "password": "user123"},
        )
        print("login", login.status_code, login.text[:300])
        if login.status_code != 200:
            return 1
        tokens = login.json()

        profile = client.get(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        print("profile", profile.status_code, profile.text[:200])
        if profile.status_code != 200:
            return 1

        client.cookies.clear()
        refresh = client.post(
            "/api/v1/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        print("refresh", refresh.status_code, refresh.text[:300])
        if refresh.status_code != 200:
            return 1
        refreshed = refresh.json()
        rotated = refreshed.get("refresh_token")
        print("rotated_token_present", bool(rotated))
        if not rotated:
            print("refresh body missing refresh_token", refreshed)
            return 1

        client.cookies.clear()
        logout = client.post(
            "/api/v1/logout",
            json={"refresh_token": rotated},
        )
        print("logout", logout.status_code, logout.text[:200])
        return 0 if logout.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
