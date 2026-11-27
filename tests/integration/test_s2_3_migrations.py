"""Section 2.3: the migrated database matches the models.

The upgrade / downgrade / upgrade round trip itself runs as a CI step before the tests
(scenarios 2.3-01, 2.3-02, 2.3-04); these tests check what that left behind.
"""

from pathlib import Path
from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import Base
from tests.db import SERVICES

pytestmark = SERVICES
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

TRIGGERS = {
    *(
        f"{table}_set_updated_at"
        for table in ("users", "organizations", "roles", "memberships", "sessions", "invitations")
    ),
    "memberships_role_scope",
    "invitations_role_scope",
    "roles_organization_fixed",
}


# Any: Alembic reports differences as loosely typed tuples.
def _differences(connection: Connection) -> list[Any]:
    context = MigrationContext.configure(connection, opts={"compare_type": True})
    return list(compare_metadata(context, Base.metadata))


async def test_s2_3_03_models_and_migrated_database_have_no_differences(
    db_connection: AsyncConnection,
) -> None:
    assert await db_connection.run_sync(_differences) == []


def _model_constraint_names() -> set[str]:
    names: set[str] = set()
    for table in Base.metadata.sorted_tables:
        for constraint in table.constraints:
            assert constraint.name, f"unnamed constraint on {table.name}"
            names.add(str(constraint.name))
    return names


async def test_s2_3_03_constraint_names_match_the_models(db_connection: AsyncConnection) -> None:
    rows = await db_connection.execute(
        text(
            "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relnamespace = 'public'::regnamespace AND t.relname <> 'alembic_version' "
            "AND c.contype IN ('p', 'f', 'u', 'c')"
        )
    )
    assert set(rows.scalars()) == _model_constraint_names()


async def test_s2_3_01_extension_and_triggers_are_installed(db_connection: AsyncConnection) -> None:
    extensions = await db_connection.execute(text("SELECT extname FROM pg_extension"))
    assert "citext" in set(extensions.scalars())
    triggers = await db_connection.execute(
        text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
    )
    assert set(triggers.scalars()) == TRIGGERS


async def test_s2_3_04_database_is_at_the_latest_revision(db_connection: AsyncConnection) -> None:
    version = await db_connection.execute(text("SELECT version_num FROM alembic_version"))
    head = ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_current_head()
    assert list(version.scalars()) == [head]
