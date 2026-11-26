"""
Configuration Package
Centralized configuration management for the FastAPI application
"""

from .settings import settings, Settings

# Export the main settings instance
__all__ = ["settings", "Settings"]
