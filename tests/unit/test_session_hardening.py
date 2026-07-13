"""Unit tests for session hardening helpers and refresh reuse detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from utils.jwt_config import hash_token
from utils.request_ip import get_client_ip


def test_get_client_ip_prefers_forwarded_for() -> None:
    request = MagicMock()
    request.headers = {"x-forwarded-for": "203.0.113.10, 10.0.0.1"}
    request.client.host = "127.0.0.1"
    assert get_client_ip(request) == "203.0.113.10"


def test_get_client_ip_falls_back_to_client_host() -> None:
    request = MagicMock()
    request.headers = {}
    request.client.host = "192.0.2.5"
    assert get_client_ip(request) == "192.0.2.5"


def test_hash_token_is_stable() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
