"""
Create MySQL schema in the local Codespaces database from SQLAlchemy models.

Usage:
    python scripts/bootstrap_local_db.py

Requires DB__URL (see .env.codespaces.example) or docker-compose MySQL running.
"""

from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from models.user_model import (  # noqa: F401, E402 — register models with Base
    ApiKey,
    AuditLog,
    LoginAttempt,
    Organization,
    PasswordHistory,
    RefreshToken,
    User,
    UserGroup,
    UserGroupMembership,
    UserPermission,
    UserSession,
)
from utils.database import Base, engine


def main() -> None:
    print("Creating database schema from SQLAlchemy models...")
    Base.metadata.create_all(bind=engine)
    print("Schema created successfully.")


if __name__ == "__main__":
    main()
