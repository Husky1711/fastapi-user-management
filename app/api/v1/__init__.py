"""Version 1 of the public API. Feature routers are added here from roadmap step 3 on."""

from fastapi import APIRouter

from app.schemas.errors import API_ERROR_RESPONSES

api_router = APIRouter(prefix="/api/v1", responses=API_ERROR_RESPONSES)
