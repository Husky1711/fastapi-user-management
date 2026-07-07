#!/usr/bin/env python3
"""Legacy migration: add manager_id column.

Superseded by Alembic baseline revision ``20260708_baseline``. Kept for reference
on databases that were created before Alembic was introduced.
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import text

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.database import get_db  # noqa: E402


def add_manager_id_column() -> bool:
    db = next(get_db())
    try:
        result = db.execute(text("DESCRIBE users"))
        existing_columns = [row[0] for row in result]

        if "manager_id" not in existing_columns:
            print("Adding manager_id column to users...")
            db.execute(
                text(
                    "ALTER TABLE users ADD COLUMN manager_id INT NULL, "
                    "ADD INDEX idx_users_manager_id (manager_id), "
                    "ADD CONSTRAINT fk_users_manager_id "
                    "FOREIGN KEY (manager_id) REFERENCES users(id)"
                )
            )
            db.commit()
            print("Added manager_id column.")
        else:
            print("manager_id column already exists.")

        return True
    except Exception as exc:
        print(f"Migration failed: {exc}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(0 if add_manager_id_column() else 1)
