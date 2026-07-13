"""
Alembic rollback smoke: downgrade one revision from head, then upgrade back.

Marks DB §4.7.4 / readiness 10.7 — full pairwise matrix is expensive; this
guards that the latest revision's downgrade path is callable.
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from config.settings import settings

pytestmark = pytest.mark.integration


def _alembic_cfg() -> Config:
    return Config("alembic.ini")


def _current_revision(url: str) -> str | None:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            return context.get_current_revision()
    finally:
        engine.dispose()


@pytest.mark.integration
def test_latest_revision_downgrade_then_upgrade():
    url = settings.get_database_url()
    assert "sqlite" not in url.lower(), "Downgrade smoke expects MySQL/Postgres CI DB"

    cfg = _alembic_cfg()
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    assert head, "No Alembic head revision found"

    before = _current_revision(url)
    assert before == head, f"DB must be at head before test (got {before}, want {head})"

    command.downgrade(cfg, "-1")
    after_down = _current_revision(url)
    assert after_down != head, "downgrade -1 should leave head"

    command.upgrade(cfg, "head")
    after_up = _current_revision(url)
    assert after_up == head

    # Sanity: password_hash column present after re-upgrade (recent rewrite)
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'users'
                      AND COLUMN_NAME = 'password_hash'
                    """
                )
            ).fetchall()
            assert rows, "users.password_hash missing after upgrade head"
    finally:
        engine.dispose()
