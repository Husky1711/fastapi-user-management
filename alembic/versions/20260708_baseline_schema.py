"""Baseline schema bootstrap.

Greenfield (empty DB): creates all tables registered on ``Base.metadata`` from the
current models package. Later revisions are **idempotent** (inspector / IF NOT EXISTS),
so running ``alembic upgrade head`` after this is safe even when models already include
columns added by those revisions.

Legacy DBs that already have tables: do **not** re-run this upgrade — stamp instead::

    alembic stamp 20260708_baseline
    alembic upgrade head

Full per-table ``op.create_table`` listings are impractical to keep in sync with every
subsequent revision; the reproducible path for greenfield is metadata create +
idempotent follow-ups (see docs/DATABASE_SCHEMA_REVIEW.md §4.7.1).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260708_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    import models  # noqa: F401 — register identity/session/compliance tables
    import models.rbac_model  # noqa: F401

    from utils.database import Base

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    if "users" in existing:
        # Legacy / stamped database — DDL already present; later revisions evolve it.
        return

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    import models  # noqa: F401
    import models.rbac_model  # noqa: F401

    from utils.database import Base

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Only drop tables that still exist — avoids errors on partial stamp paths.
    tables = [t for t in reversed(Base.metadata.sorted_tables) if t.name in inspector.get_table_names()]
    for table in tables:
        table.drop(bind=bind, checkfirst=True)
