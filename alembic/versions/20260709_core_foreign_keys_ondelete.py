"""Add ondelete rules to core foreign keys (refresh_tokens, users).

Revision ID: 20260709_core_fks
Revises: 20260708_fks
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260709_core_fks"
down_revision = "20260708_fks"
branch_labels = None
depends_on = None


def _cleanup_orphans() -> None:
    statements = [
        "DELETE rt FROM refresh_tokens rt "
        "LEFT JOIN users u ON rt.user_id = u.id WHERE u.id IS NULL",
        "UPDATE users u LEFT JOIN users m ON u.manager_id = m.id "
        "SET u.manager_id = NULL WHERE u.manager_id IS NOT NULL AND m.id IS NULL",
        "UPDATE users u LEFT JOIN organizations o ON u.organization_id = o.id "
        "SET u.organization_id = 1 WHERE u.organization_id IS NOT NULL AND o.id IS NULL",
    ]
    for sql in statements:
        op.execute(sa.text(sql))


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        fk.get("name") == constraint_name for fk in inspector.get_foreign_keys(table_name)
    )


def _drop_fk_on_columns(table_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("constrained_columns") == columns and fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def _create_foreign_key_if_missing(
    name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str,
) -> None:
    if _foreign_key_exists(source_table, name):
        return
    op.create_foreign_key(
        name,
        source_table,
        referent_table,
        local_cols,
        remote_cols,
        ondelete=ondelete,
    )


def upgrade() -> None:
    _cleanup_orphans()

    _drop_fk_on_columns("refresh_tokens", ["user_id"])
    _create_foreign_key_if_missing(
        "fk_refresh_tokens_user_id",
        "refresh_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _drop_fk_on_columns("users", ["organization_id"])
    _create_foreign_key_if_missing(
        "fk_users_organization_id",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    _drop_fk_on_columns("users", ["manager_id"])
    _create_foreign_key_if_missing(
        "fk_users_manager_id",
        "users",
        "users",
        ["manager_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    for name, table, cols, referent, remote, ondelete in (
        ("fk_users_manager_id", "users", ["manager_id"], "users", ["id"], None),
        ("fk_users_organization_id", "users", ["organization_id"], "organizations", ["id"], None),
        ("fk_refresh_tokens_user_id", "refresh_tokens", ["user_id"], "users", ["id"], None),
    ):
        if _foreign_key_exists(table, name):
            op.drop_constraint(name, table, type_="foreignkey")
        _drop_fk_on_columns(table, cols)
        op.create_foreign_key(name, table, referent, cols, remote)
