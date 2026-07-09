"""Add foreign keys to compliance tables.

Revision ID: 20260708_fks
Revises: 20260708_baseline
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260708_fks"
down_revision = "20260708_baseline"
branch_labels = None
depends_on = None


def _cleanup_orphans() -> None:
    """Remove or null out rows that would violate new foreign keys."""
    statements = [
        # audit_logs — preserve rows, drop invalid references
        "UPDATE audit_logs al LEFT JOIN users u ON al.user_id = u.id "
        "SET al.user_id = NULL WHERE al.user_id IS NOT NULL AND u.id IS NULL",
        "UPDATE audit_logs al LEFT JOIN organizations o ON al.organization_id = o.id "
        "SET al.organization_id = NULL WHERE al.organization_id IS NOT NULL AND o.id IS NULL",
        # user_sessions
        "DELETE us FROM user_sessions us "
        "LEFT JOIN users u ON us.user_id = u.id WHERE u.id IS NULL",
        "UPDATE user_sessions us LEFT JOIN refresh_tokens rt ON us.refresh_token_id = rt.id "
        "SET us.refresh_token_id = NULL "
        "WHERE us.refresh_token_id IS NOT NULL AND rt.id IS NULL",
        # password_history
        "DELETE ph FROM password_history ph "
        "LEFT JOIN users u ON ph.user_id = u.id WHERE u.id IS NULL",
        "UPDATE password_history ph LEFT JOIN users u ON ph.changed_by = u.id "
        "SET ph.changed_by = NULL WHERE ph.changed_by IS NOT NULL AND u.id IS NULL",
        # login_attempts
        "UPDATE login_attempts la LEFT JOIN users u ON la.user_id = u.id "
        "SET la.user_id = NULL WHERE la.user_id IS NOT NULL AND u.id IS NULL",
        # user_permissions
        "DELETE up FROM user_permissions up "
        "LEFT JOIN users u ON up.user_id = u.id WHERE u.id IS NULL",
        "UPDATE user_permissions up LEFT JOIN users u ON up.granted_by = u.id "
        "SET up.granted_by = NULL WHERE up.granted_by IS NOT NULL AND u.id IS NULL",
        # user_groups
        "DELETE ug FROM user_groups ug "
        "LEFT JOIN organizations o ON ug.organization_id = o.id WHERE o.id IS NULL",
        "DELETE ug FROM user_groups ug "
        "LEFT JOIN users u ON ug.created_by = u.id WHERE u.id IS NULL",
        # memberships — dedupe then remove orphans
        "DELETE t1 FROM user_group_memberships t1 "
        "INNER JOIN user_group_memberships t2 "
        "ON t1.user_id = t2.user_id AND t1.group_id = t2.group_id AND t1.id > t2.id",
        "DELETE ugm FROM user_group_memberships ugm "
        "LEFT JOIN users u ON ugm.user_id = u.id WHERE u.id IS NULL",
        "DELETE ugm FROM user_group_memberships ugm "
        "LEFT JOIN user_groups g ON ugm.group_id = g.id WHERE g.id IS NULL",
        "DELETE ugm FROM user_group_memberships ugm "
        "LEFT JOIN users u ON ugm.added_by = u.id WHERE u.id IS NULL",
        # api_keys
        "DELETE ak FROM api_keys ak LEFT JOIN users u ON ak.user_id = u.id WHERE u.id IS NULL",
        "DELETE ak FROM api_keys ak "
        "LEFT JOIN organizations o ON ak.organization_id = o.id WHERE o.id IS NULL",
        "DELETE ak FROM api_keys ak LEFT JOIN users u ON ak.created_by = u.id WHERE u.id IS NULL",
    ]
    for sql in statements:
        op.execute(sa.text(sql))


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        fk.get("name") == constraint_name for fk in inspector.get_foreign_keys(table_name)
    )


def _unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        uc.get("name") == constraint_name for uc in inspector.get_unique_constraints(table_name)
    )


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

    _create_foreign_key_if_missing(
        "fk_user_sessions_user_id",
        "user_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_if_missing(
        "fk_user_sessions_refresh_token_id",
        "user_sessions",
        "refresh_tokens",
        ["refresh_token_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_foreign_key_if_missing(
        "fk_audit_logs_user_id",
        "audit_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_foreign_key_if_missing(
        "fk_audit_logs_organization_id",
        "audit_logs",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_foreign_key_if_missing(
        "fk_password_history_user_id",
        "password_history",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_if_missing(
        "fk_password_history_changed_by",
        "password_history",
        "users",
        ["changed_by"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_foreign_key_if_missing(
        "fk_login_attempts_user_id",
        "login_attempts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_foreign_key_if_missing(
        "fk_user_permissions_user_id",
        "user_permissions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_if_missing(
        "fk_user_permissions_granted_by",
        "user_permissions",
        "users",
        ["granted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_foreign_key_if_missing(
        "fk_user_groups_organization_id",
        "user_groups",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_if_missing(
        "fk_user_groups_created_by",
        "user_groups",
        "users",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    _create_foreign_key_if_missing(
        "fk_user_group_memberships_user_id",
        "user_group_memberships",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_if_missing(
        "fk_user_group_memberships_group_id",
        "user_group_memberships",
        "user_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_if_missing(
        "fk_user_group_memberships_added_by",
        "user_group_memberships",
        "users",
        ["added_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    _create_foreign_key_if_missing(
        "fk_api_keys_user_id",
        "api_keys",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_if_missing(
        "fk_api_keys_organization_id",
        "api_keys",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_if_missing(
        "fk_api_keys_created_by",
        "api_keys",
        "users",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    if not _unique_constraint_exists("user_group_memberships", "uq_user_group_membership"):
        op.create_unique_constraint(
            "uq_user_group_membership",
            "user_group_memberships",
            ["user_id", "group_id"],
        )


def downgrade() -> None:
    op.drop_constraint("uq_user_group_membership", "user_group_memberships", type_="unique")

    fk_names = [
        ("api_keys", "fk_api_keys_created_by"),
        ("api_keys", "fk_api_keys_organization_id"),
        ("api_keys", "fk_api_keys_user_id"),
        ("user_group_memberships", "fk_user_group_memberships_added_by"),
        ("user_group_memberships", "fk_user_group_memberships_group_id"),
        ("user_group_memberships", "fk_user_group_memberships_user_id"),
        ("user_groups", "fk_user_groups_created_by"),
        ("user_groups", "fk_user_groups_organization_id"),
        ("user_permissions", "fk_user_permissions_granted_by"),
        ("user_permissions", "fk_user_permissions_user_id"),
        ("login_attempts", "fk_login_attempts_user_id"),
        ("password_history", "fk_password_history_changed_by"),
        ("password_history", "fk_password_history_user_id"),
        ("audit_logs", "fk_audit_logs_organization_id"),
        ("audit_logs", "fk_audit_logs_user_id"),
        ("user_sessions", "fk_user_sessions_refresh_token_id"),
        ("user_sessions", "fk_user_sessions_user_id"),
    ]
    for table, name in fk_names:
        op.drop_constraint(name, table, type_="foreignkey")
