"""Shared router configuration for /api/v1 identity routes."""

from fastapi import APIRouter
from fastapi.security import HTTPBearer

API_PREFIX = "/api/v1"
security = HTTPBearer()


def create_api_router(*, tags: list[str]) -> APIRouter:
    return APIRouter(prefix=API_PREFIX, tags=tags)
