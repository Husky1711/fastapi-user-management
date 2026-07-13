"""Rename users.password → users.password_hash.

Revision ID: 20260714_password_hash_col
Revises: 20260714_retention_policies
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_password_hash_col"
down_revision = "20260714_retention_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "password" in cols and "password_hash" not in cols:
        # MySQL CHANGE keeps NULLability/type; portable rename for Postgres too.
        op.alter_column(
            "users",
            "password",
            new_column_name="password_hash",
            existing_type=sa.String(length=255),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "password_hash" in cols and "password" not in cols:
        op.alter_column(
            "users",
            "password_hash",
            new_column_name="password",
            existing_type=sa.String(length=255),
            existing_nullable=False,
        )
