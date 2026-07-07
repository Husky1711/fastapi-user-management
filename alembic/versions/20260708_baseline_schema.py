"""Baseline schema from SQLAlchemy models.

Existing databases created via create_all() should be stamped with:
    alembic stamp head
"""

from __future__ import annotations

from alembic import op

revision = "20260708_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    import models.user_model  # noqa: F401 — register tables on Base.metadata

    from utils.database import Base

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    import models.user_model  # noqa: F401

    from utils.database import Base

    Base.metadata.drop_all(bind=op.get_bind())
