"""Export live MySQL schema (DDL only) to a .sql file.

Usage (from repo root):
  python scripts/export_schema_sql.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text

from config.settings import settings

OUT = ROOT / "docs" / "schema" / "fastapi_users_schema_latest.sql"


def main() -> None:
    url = settings.get_database_url()
    parsed = urlparse(url)
    db_name = (parsed.path or "").lstrip("/").split("?")[0]
    engine = create_engine(url)

    with engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        tables = [
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT TABLE_NAME
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = :db AND TABLE_TYPE = 'BASE TABLE'
                    ORDER BY TABLE_NAME
                    """
                ),
                {"db": db_name},
            )
        ]

        lines: list[str] = [
            "-- =============================================================================",
            "-- FastAPI User Management — latest database schema (DDL only)",
            f"-- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"-- Database: {db_name}",
            f"-- Alembic revision: {revision}",
            "-- Source: live MySQL via SHOW CREATE TABLE (no data)",
            "-- =============================================================================",
            "",
            "SET NAMES utf8mb4;",
            "SET FOREIGN_KEY_CHECKS = 0;",
            "",
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            f"USE `{db_name}`;",
            "",
        ]

        for table in tables:
            row = conn.execute(text(f"SHOW CREATE TABLE `{table}`")).one()
            # row[0]=table name, row[1]=Create Table
            create_sql = row[1].rstrip(";")
            lines.append(f"-- ---------------------------------------------------------------------------")
            lines.append(f"-- Table: `{table}`")
            lines.append(f"-- ---------------------------------------------------------------------------")
            lines.append(f"DROP TABLE IF EXISTS `{table}`;")
            lines.append(f"{create_sql};")
            lines.append("")

        # Views if any
        views = [
            r[0]
            for r in conn.execute(
                text(
                    """
                    SELECT TABLE_NAME
                    FROM information_schema.VIEWS
                    WHERE TABLE_SCHEMA = :db
                    ORDER BY TABLE_NAME
                    """
                ),
                {"db": db_name},
            )
        ]
        for view in views:
            row = conn.execute(text(f"SHOW CREATE VIEW `{view}`")).one()
            create_sql = row[1].rstrip(";")
            lines.append(f"-- View: `{view}`")
            lines.append(f"DROP VIEW IF EXISTS `{view}`;")
            lines.append(f"{create_sql};")
            lines.append("")

        lines.append("SET FOREIGN_KEY_CHECKS = 1;")
        lines.append("")
        lines.append("-- End of schema dump")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({len(tables)} tables, revision={revision})")


if __name__ == "__main__":
    main()
