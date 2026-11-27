"""Auth: last login time, revocation reasons, family start time, one active token per family.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP = sa.DateTime(timezone=True)
REVOKE_REASONS = (
    "rotated",
    "logout",
    "logout_all",
    "revoked",
    "replaced",
    "password_changed",
    "reuse_detected",
)


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", TIMESTAMP, nullable=True))
    op.add_column("sessions", sa.Column("revoked_reason", sa.String(32), nullable=True))
    op.add_column("sessions", sa.Column("family_started_at", TIMESTAMP, nullable=True))
    # Rows written before this migration: a revoked row's reason is unknown ("revoked"), and
    # the family started no later than its oldest row.
    op.execute("UPDATE sessions SET revoked_reason = 'revoked' WHERE revoked_at IS NOT NULL")
    op.execute(
        "UPDATE sessions s SET family_started_at = f.started FROM "
        "(SELECT family_id, min(created_at) AS started FROM sessions GROUP BY family_id) f "
        "WHERE s.family_id = f.family_id"
    )
    op.alter_column("sessions", "family_started_at", nullable=False)
    reasons = ", ".join(f"'{reason}'" for reason in REVOKE_REASONS)
    op.create_check_constraint(
        op.f("ck_sessions_revoked_reason"), "sessions", f"revoked_reason IN ({reasons})"
    )
    op.create_check_constraint(
        op.f("ck_sessions_revoked_reason_set"),
        "sessions",
        "(revoked_at IS NULL) = (revoked_reason IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_sessions_family_started_first"), "sessions", "family_started_at <= created_at"
    )
    # Older data may hold several active rows in one family: keep the newest active.
    op.execute(
        "UPDATE sessions s SET revoked_at = now(), revoked_reason = 'rotated' "
        "WHERE s.revoked_at IS NULL AND EXISTS (SELECT 1 FROM sessions n "
        "WHERE n.family_id = s.family_id AND n.revoked_at IS NULL AND n.created_at > s.created_at)"
    )
    op.create_index(
        "uq_sessions_family_id_active",
        "sessions",
        ["family_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sessions_family_id_active", table_name="sessions")
    for name in ("family_started_first", "revoked_reason_set", "revoked_reason"):
        op.drop_constraint(op.f(f"ck_sessions_{name}"), "sessions", type_="check")
    op.drop_column("sessions", "family_started_at")
    op.drop_column("sessions", "revoked_reason")
    op.drop_column("users", "last_login_at")
