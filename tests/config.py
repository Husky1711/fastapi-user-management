"""
Shared test configuration values.
"""

from __future__ import annotations

import os

DEFAULT_API_BASE_URL = "https://fastapi-user-management-364e.onrender.com"


def _detect_base_url() -> str:
    """Resolve the API base URL for integration/e2e tests."""
    env_url = (
        os.getenv("TEST_API_BASE_URL")
        or os.getenv("RENDER_API_URL")
        or os.getenv("API_BASE_URL")
    )
    base_url = env_url or DEFAULT_API_BASE_URL
    return base_url.rstrip("/")


API_BASE_URL = _detect_base_url()

