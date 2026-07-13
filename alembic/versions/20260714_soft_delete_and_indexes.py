"""Soft delete columns, drop dead login_attempts, add composite indexes.

Revision ID: 20260714_soft_idx
Revises: 20260714_uniques_slug
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_soft_idx"
down_revision = "20260714_uniques_slug"
branch_labels = None
depends_on = None


def _has_index(inspector, table: str, name: str) -> bool:
    return any(ix["name"] == name for ix in inspector.get_indexes(table))


def _has_column(inspector, table: str, name: str) -> bool:
    return any(c["name"] == name for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- soft delete on organizations ---
    if not _has_column(inspector, "organizations", "deleted_at"):
        op.add_column(
            "organizations",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column(inspector, "organizations", "deleted_by"):
        op.add_column(
            "organizations",
            sa.Column("deleted_by", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_organizations_deleted_by",
            "organizations",
            "users",
            ["deleted_by"],
            ["id"],
            ondelete="SET NULL",
        )

    # --- soft delete on users ---
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "users", "deleted_at"):
        op.add_column(
            "users",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_column(inspector, "users", "deleted_by"):
        op.add_column(
            "users",
            sa.Column("deleted_by", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_users_deleted_by",
            "users",
            "users",
            ["deleted_by"],
            ["id"],
            ondelete="SET NULL",
        )

    # Drop dead users.login_attempts counter (failed_login_attempts is authoritative)
    inspector = sa.inspect(bind)
    if _has_column(inspector, "users", "login_attempts"):
        op.drop_column("users", "login_attempts")

    # --- composite indexes ---
    inspector = sa.inspect(bind)
    desired = [
        ("users", "idx_users_org_status", ["organization_id", "status"]),
        ("users", "idx_users_org_role", ["organization_id", "role"]),
        ("users", "idx_users_deleted_at", ["deleted_at"]),
        ("organizations", "idx_organizations_deleted_at", ["deleted_at"]),
        (
            "refresh_tokens",
            "idx_refresh_tokens_user_revoked_expires",
            ["user_id", "is_revoked", "expires_at"],
        ),
        (
            "user_sessions",
            "idx_user_sessions_user_active_expires",
            ["user_id", "is_active", "expires_at"],
        ),
        ("login_attempts", "idx_login_attempts_ip_created", ["ip_address", "created_at"]),
        (
            "login_attempts",
            "idx_login_attempts_username_created",
            ["username", "created_at"],
        ),
        ("api_keys", "idx_api_keys_org_active", ["organization_id", "is_active"]),
        (
            "password_history",
            "idx_password_history_user_created",
            ["user_id", "created_at"],
        ),
        (
            "audit_logs",
            "idx_audit_logs_org_created",
            ["organization_id", "created_at"],
        ),
        ("audit_logs", "idx_audit_logs_user_created", ["user_id", "created_at"]),
        (
            "audit_logs",
            "idx_audit_logs_event_created",
            ["event_type", "created_at"],
        ),
    ]
    for table, name, cols in desired:
        if table not in inspector.get_table_names():
            continue
        if _has_index(inspector, table, name):
            continue
        # Skip if a column is missing (defensive)
        table_cols = {c["name"] for c in inspector.get_columns(table)}
        if not set(cols).issubset(table_cols):
            continue
        op.create_index(name, table, cols)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    indexes = [
        ("audit_logs", "idx_audit_logs_event_created"),
        ("audit_logs", "idx_audit_logs_user_created"),
        ("audit_logs", "idx_audit_logs_org_created"),
        ("password_history", "idx_password_history_user_created"),
        ("api_keys", "idx_api_keys_org_active"),
        ("login_attempts", "idx_login_attempts_username_created"),
        ("login_attempts", "idx_login_attempts_ip_created"),
        ("user_sessions", "idx_user_sessions_user_active_expires"),
        ("refresh_tokens", "idx_refresh_tokens_user_revoked_expires"),
        ("organizations", "idx_organizations_deleted_at"),
        ("users", "idx_users_deleted_at"),
        ("users", "idx_users_org_role"),
        ("users", "idx_users_org_status"),
    ]
    for table, name in indexes:
        if table in inspector.get_table_names() and _has_index(inspector, table, name):
            op.drop_index(name, table_name=table)

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "users", "login_attempts"):
        op.add_column(
            "users",
            sa.Column("login_attempts", sa.Integer(), server_default="0"),
        )

    if _has_column(inspector, "users", "deleted_by"):
        op.drop_constraint("fk_users_deleted_by", "users", type_="foreignkey")
        op.drop_column("users", "deleted_by")
    if _has_column(inspector, "users", "deleted_at"):
        op.drop_column("users", "deleted_at")

    if _has_column(inspector, "organizations", "deleted_by"):
        op.drop_constraint(
            "fk_organizations_deleted_by", "organizations", type_="foreignkey"
        )
        op.drop_column("organizations", "deleted_by")
    if _has_column(inspector, "organizations", "deleted_at"):
        op.drop_column("organizations", "deleted_at")
