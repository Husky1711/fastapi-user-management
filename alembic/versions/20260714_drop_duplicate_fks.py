"""Drop duplicate MySQL auto-named ibfk_* FKs; keep explicit fk_* names.

Revision ID: 20260714_drop_dup_fks
Revises: 20260714_password_hash_col
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_drop_dup_fks"
down_revision = "20260714_password_hash_col"
branch_labels = None
depends_on = None

# Tables that historically had both ORM/MySQL ibfk_* and Alembic fk_* constraints.
_TARGET_TABLES = (
    "api_keys",
    "audit_logs",
    "login_attempts",
    "password_history",
    "user_groups",
    "user_group_memberships",
    "user_permissions",
    "user_sessions",
)


def _ibfk_names(table_name: str) -> list[str]:
    inspector = sa.inspect(op.get_bind())
    return sorted(
        fk["name"]
        for fk in inspector.get_foreign_keys(table_name)
        if fk.get("name") and "_ibfk_" in fk["name"]
    )


def upgrade() -> None:
    for table in _TARGET_TABLES:
        for name in _ibfk_names(table):
            op.drop_constraint(name, table_name=table, type_="foreignkey")


def downgrade() -> None:
    # Intentionally empty: recreating MySQL auto-names is non-deterministic and
    # duplicate FKs were accidental. Named fk_* constraints remain.
    pass
