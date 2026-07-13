"""consent_records + security_incidents.

Revision ID: 20260714_consent_incidents
Revises: 20260714_org_settings
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_consent_incidents"
down_revision = "20260714_org_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "consent_records" not in tables:
        op.create_table(
            "consent_records",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("consent_type", sa.String(length=100), nullable=False),
            sa.Column(
                "granted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            ),
            sa.Column("granted_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("source", sa.String(length=100), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="CASCADE"
            ),
        )
        op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])
        op.create_index(
            "ix_consent_records_organization_id",
            "consent_records",
            ["organization_id"],
        )
        op.create_index(
            "ix_consent_records_consent_type", "consent_records", ["consent_type"]
        )

    if "security_incidents" not in tables:
        op.create_table(
            "security_incidents",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("incident_type", sa.String(length=100), nullable=False),
            sa.Column(
                "severity",
                sa.String(length=20),
                nullable=False,
                server_default="medium",
            ),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(length=45), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"], ["organizations.id"], ondelete="SET NULL"
            ),
        )
        op.create_index(
            "ix_security_incidents_user_id", "security_incidents", ["user_id"]
        )
        op.create_index(
            "ix_security_incidents_organization_id",
            "security_incidents",
            ["organization_id"],
        )
        op.create_index(
            "ix_security_incidents_incident_type",
            "security_incidents",
            ["incident_type"],
        )
        op.create_index(
            "ix_security_incidents_severity", "security_incidents", ["severity"]
        )
        op.create_index(
            "ix_security_incidents_created_at", "security_incidents", ["created_at"]
        )


def downgrade() -> None:
    op.drop_table("security_incidents")
    op.drop_table("consent_records")
