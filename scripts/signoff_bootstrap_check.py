#!/usr/bin/env python3
"""HTTP sign-off for E2E #7 bootstrap: cookie survives login → refresh (reload simulation)."""

from __future__ import annotations

import json
import os
import sys

import httpx

APP_URL = os.getenv("APP_URL", "http://127.0.0.1:5173").rstrip("/")
USER = os.getenv("CHECKLIST_USER", "testuser")
PASSWORD = os.getenv("CHECKLIST_PASSWORD", "user123")


def main() -> int:
    with httpx.Client(base_url=APP_URL, timeout=30.0, follow_redirects=True) as client:
        login = client.post(
            "/api/v1/login",
            json={"username": USER, "password": PASSWORD},
        )
        if login.status_code != 200:
            print(f"FAIL login {login.status_code} {login.text}")
            return 1
        print("PASS login")

        refresh = client.post("/api/v1/refresh")
        if refresh.status_code != 200:
            print(f"FAIL refresh {refresh.status_code} {refresh.text}")
            return 1
        body = refresh.json()
        if not body.get("access_token"):
            print(f"FAIL refresh missing access_token: {body}")
            return 1
        print("PASS cookie_refresh")

        reload_refresh = client.post("/api/v1/refresh")
        if reload_refresh.status_code != 200:
            print(f"FAIL reload_refresh {reload_refresh.status_code} {reload_refresh.text}")
            return 1
        token = reload_refresh.json().get("access_token")
        if not token:
            print(f"FAIL reload_refresh missing access_token: {reload_refresh.json()}")
            return 1
        print("PASS reload_bootstrap_refresh")

        profile = client.get(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        if profile.status_code != 200:
            print(f"FAIL profile {profile.status_code} {profile.text}")
            return 1
        username = profile.json().get("username")
        if username != USER:
            print(f"FAIL profile user {username!r} expected {USER!r}: {json.dumps(profile.json())}")
            return 1
        print("PASS profile_after_bootstrap")

    print("summary: signoff_bootstrap_check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
