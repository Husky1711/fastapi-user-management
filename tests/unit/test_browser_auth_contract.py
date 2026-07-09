"""Browser auth contract tests (CORS settings, cookies, error codes)."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Isolate from tracked .env before importing settings in tests.
os.environ.setdefault("SECURITY__CORS_ORIGINS", '["*"]')
os.environ.setdefault("AUTH_COOKIE__USE_HTTPONLY_REFRESH", "true")
os.environ.setdefault("AUTH_COOKIE__SECURE", "false")


class TestCorsOriginsSettings(unittest.TestCase):
    def test_wildcard_origin_is_replaced_for_credentialed_cors(self) -> None:
        from config.settings import SecuritySettings

        settings = SecuritySettings(cors_origins=["*"])
        self.assertNotIn("*", settings.cors_origins)
        self.assertIn("http://localhost:5173", settings.cors_origins)


class TestRefreshCookieHelpers(unittest.TestCase):
    def test_set_refresh_cookie_uses_httponly_and_path(self) -> None:
        from starlette.responses import Response

        from utils.cookie_auth import set_refresh_cookie

        response = Response()
        with patch("utils.cookie_auth.settings") as mock_settings:
            mock_settings.auth_cookie.use_httponly_refresh = True
            mock_settings.auth_cookie.name = "refresh_token"
            mock_settings.auth_cookie.path = "/api/v1"
            mock_settings.auth_cookie.secure = False
            mock_settings.auth_cookie.samesite = "lax"
            mock_settings.auth_cookie.domain = None
            mock_settings.jwt.refresh_token_expire_days = 7

            set_refresh_cookie(response, "secret-token")

        cookie_header = response.headers.get("set-cookie", "")
        self.assertIn("refresh_token=secret-token", cookie_header)
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("Path=/api/v1", cookie_header)


class TestErrorPayloadCodes(unittest.TestCase):
    def test_plain_http_exception_maps_status_to_error_code(self) -> None:
        from fastapi import HTTPException

        from utils.api_errors import error_payload

        payload = error_payload(HTTPException(status_code=403, detail="Forbidden"), "req-1", 1.0)
        self.assertEqual(payload["error_code"], "FORBIDDEN")

    def test_api_http_exception_preserves_custom_code(self) -> None:
        from utils.api_errors import APIHTTPException, error_payload

        exc = APIHTTPException(
            status_code=423,
            detail="Locked",
            error_code="ACCOUNT_LOCKED",
        )
        payload = error_payload(exc, "req-2", 2.0)
        self.assertEqual(payload["error_code"], "ACCOUNT_LOCKED")


if __name__ == "__main__":
    unittest.main()
