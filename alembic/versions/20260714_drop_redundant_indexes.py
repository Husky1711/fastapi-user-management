"""Drop redundant single-column indexes covered by composites/PKs.

Revision ID: 20260714_drop_redund_idx
Revises: 20260714_soft_idx
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_drop_redund_idx"
down_revision = "20260714_soft_idx"
branch_labels = None
depends_on = None

# Covered by composite indexes or PRIMARY KEY.
DROP_INDEXES = [
    ("audit_logs", "ix_audit_logs_id"),
    ("audit_logs", "ix_audit_logs_event_type"),  # covered by idx_audit_logs_event_created
    ("audit_logs", "ix_audit_logs_organization_id"),  # covered by idx_audit_logs_org_created
    ("audit_logs", "ix_audit_logs_user_id"),  # covered by idx_audit_logs_user_created
    ("users", "ix_users_id"),
    ("organizations", "ix_organizations_id"),
    ("refresh_tokens", "ix_refresh_tokens_id"),
    ("login_attempts", "ix_login_attempts_id"),
    ("login_attempts", "ix_login_attempts_ip_address"),  # covered by idx_login_attempts_ip_created
    ("login_attempts", "ix_login_attempts_username"),  # covered by idx_login_attempts_username_created
]


def _has_index(inspector, table: str, name: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(ix["name"] == name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, name in DROP_INDEXES:
        if _has_index(inspector, table, name):
            op.drop_index(name, table_name=table)


def downgrade() -> None:
    # Recreate as non-unique single-column indexes (best-effort restore).
    restores = [
        ("audit_logs", "ix_audit_logs_id", ["id"]),
        ("audit_logs", "ix_audit_logs_event_type", ["event_type"]),
        ("audit_logs", "ix_audit_logs_organization_id", ["organization_id"]),
        ("audit_logs", "ix_audit_logs_user_id", ["user_id"]),
        ("users", "ix_users_id", ["id"]),
        ("organizations", "ix_organizations_id", ["id"]),
        ("refresh_tokens", "ix_refresh_tokens_id", ["id"]),
        ("login_attempts", "ix_login_attempts_id", ["id"]),
        ("login_attempts", "ix_login_attempts_ip_address", ["ip_address"]),
        ("login_attempts", "ix_login_attempts_username", ["username"]),
    ]
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, name, cols in restores:
        if table not in inspector.get_table_names():
            continue
        if _has_index(inspector, table, name):
            continue
        op.create_index(name, table, cols)
