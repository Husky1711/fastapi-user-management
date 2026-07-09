"""Unit tests for refresh-token cookie/body resolution."""

from __future__ import annotations

from unittest.mock import MagicMock

from utils.cookie_auth import resolve_refresh_token


def test_resolve_refresh_token_prefers_body_in_legacy_mode() -> None:
    request = MagicMock()
    request.cookies = {"refresh_token": "stale-cookie-token"}

    assert (
        resolve_refresh_token(request, "explicit-body-token")
        == "explicit-body-token"
    )


def test_resolve_refresh_token_uses_cookie_when_body_missing() -> None:
    request = MagicMock()
    request.cookies = {"refresh_token": "cookie-only-token"}

    assert resolve_refresh_token(request, None) == "cookie-only-token"
