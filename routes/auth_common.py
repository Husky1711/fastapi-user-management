"""Shared router configuration for /api/v1 identity routes.

Versioning policy: docs/API_VERSIONING.md — path-versioned ``/api/v1``;
breaking changes require ``/api/v2`` plus a documented deprecation window.
"""

from fastapi import APIRouter

from dependencies.auth import bearer_scheme

API_PREFIX = "/api/v1"
# Backward-compatible alias used by identity routers.
security = bearer_scheme


def create_api_router(*, tags: list[str]) -> APIRouter:
    return APIRouter(prefix=API_PREFIX, tags=tags)
