"""
Apply Alembic migrations for local MySQL (Codespaces).

Usage:
    python scripts/bootstrap_local_db.py

Fresh database: runs ``alembic upgrade head``.
Existing database (tables from legacy create_all): stamps head, then upgrades.
"""

from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

from utils.database import engine  # noqa: E402


def _has_alembic_version_table() -> bool:
    inspector = inspect(engine)
    return inspector.has_table("alembic_version")


def _has_application_tables() -> bool:
    inspector = inspect(engine)
    return inspector.has_table("users")


def main() -> None:
    alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))

    if _has_application_tables() and not _has_alembic_version_table():
        print(
            "Existing schema detected without alembic_version; stamping head "
            "(legacy create_all database)."
        )
        command.stamp(alembic_cfg, "head")

    print("Running Alembic migrations...")
    command.upgrade(alembic_cfg, "head")
    print("Database schema is at Alembic head.")


if __name__ == "__main__":
    main()
