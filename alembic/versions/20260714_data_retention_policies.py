"""data_retention_policies for RetentionService.

Revision ID: 20260714_retention_policies
Revises: 20260714_consent_incidents
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_retention_policies"
down_revision = "20260714_consent_incidents"
branch_labels = None
depends_on = None

DEFAULT_POLICIES = [
    ("login_attempts", 90, "Age-based purge of login attempt rows"),
    ("audit_logs", 365, "Age-based purge until monthly partitioning"),
    ("password_history", 365, "Password history retention window"),
    ("user_invitations", 30, "Expired / accepted / revoked invites"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "data_retention_policies" not in inspector.get_table_names():
        op.create_table(
            "data_retention_policies",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("table_name", sa.String(length=100), nullable=False),
            sa.Column("retention_days", sa.Integer(), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["updated_by"], ["users.id"], ondelete="SET NULL"
            ),
            sa.UniqueConstraint("table_name", name="uq_data_retention_table_name"),
        )
        op.create_index(
            "ix_data_retention_policies_table_name",
            "data_retention_policies",
            ["table_name"],
        )
        op.create_index(
            "ix_data_retention_policies_is_active",
            "data_retention_policies",
            ["is_active"],
        )

    policies = sa.table(
        "data_retention_policies",
        sa.column("table_name", sa.String),
        sa.column("retention_days", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("description", sa.String),
    )
    existing = {
        row[0]
        for row in bind.execute(sa.select(policies.c.table_name)).fetchall()
    }
    rows = [
        {
            "table_name": name,
            "retention_days": days,
            "is_active": True,
            "description": desc,
        }
        for name, days, desc in DEFAULT_POLICIES
        if name not in existing
    ]
    if rows:
        op.bulk_insert(policies, rows)


def downgrade() -> None:
    op.drop_table("data_retention_policies")
