#!/usr/bin/env python3
"""Verify CI bootstrap seed data required by smoke tests."""

from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

REQUIRED_USERS = (
    "testadmin",
    "testuser",
    "testorgadmin",
    "testuser_org2",
    "test_super_admin",
)


def main() -> int:
    from config.settings import settings
    from models.user_model import ApiKey, User, UserGroup
    from utils.database import SessionLocal

    print("database_url", settings.get_database_url())
    db = SessionLocal()
    errors: list[str] = []
    try:
        for username in REQUIRED_USERS:
            if db.query(User).filter(User.username == username).one_or_none() is None:
                errors.append(f"missing user: {username}")

        group = (
            db.query(UserGroup)
            .filter(UserGroup.name == "CI Org2 Group", UserGroup.organization_id == 2)
            .one_or_none()
        )
        if group is None:
            errors.append("missing group: CI Org2 Group (org 2)")

        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.key_name == "CI Org2 API Key", ApiKey.organization_id == 2)
            .one_or_none()
        )
        if api_key is None:
            errors.append("missing api key: CI Org2 API Key (org 2)")

        if errors:
            for err in errors:
                print("SEED ERROR:", err)
            return 1

        print(
            "seed ok:",
            f"users={len(REQUIRED_USERS)}",
            f"org2_group_id={group.id}",
            f"org2_api_key_id={api_key.id}",
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
