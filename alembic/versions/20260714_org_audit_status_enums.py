"""Add organizations.status and audit_logs.status ENUMs.

Revision ID: 20260714_status_enums
Revises: 20260714_enums_reset
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_status_enums"
down_revision = "20260714_enums_reset"
branch_labels = None
depends_on = None

ORG_STATUSES = ("active", "inactive", "suspended")
AUDIT_STATUSES = ("success", "failure", "error")


def upgrade() -> None:
    bind = op.get_bind()

    op.execute(
        sa.text(
            "UPDATE organizations SET status = 'active' "
            "WHERE status IS NULL OR status NOT IN ('active','inactive','suspended')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE audit_logs SET status = NULL "
            "WHERE status IS NOT NULL "
            "AND status NOT IN ('success','failure','error')"
        )
    )

    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE organizations "
                "MODIFY COLUMN status ENUM('active','inactive','suspended') "
                "NOT NULL DEFAULT 'active'"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE audit_logs "
                "MODIFY COLUMN status ENUM('success','failure','error') NULL"
            )
        )
    else:
        org_enum = sa.Enum(*ORG_STATUSES, name="organization_status_enum")
        audit_enum = sa.Enum(*AUDIT_STATUSES, name="audit_status_enum")
        org_enum.create(bind, checkfirst=True)
        audit_enum.create(bind, checkfirst=True)
        op.alter_column(
            "organizations",
            "status",
            existing_type=sa.String(length=20),
            type_=org_enum,
            existing_nullable=True,
            nullable=False,
            server_default="active",
        )
        op.alter_column(
            "audit_logs",
            "status",
            existing_type=sa.String(length=20),
            type_=audit_enum,
            existing_nullable=True,
            nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE organizations "
                "MODIFY COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE audit_logs MODIFY COLUMN status VARCHAR(20) NULL"
            )
        )
    else:
        op.alter_column(
            "organizations",
            "status",
            existing_type=sa.Enum(*ORG_STATUSES, name="organization_status_enum"),
            type_=sa.String(length=20),
            nullable=False,
            server_default="active",
        )
        op.alter_column(
            "audit_logs",
            "status",
            existing_type=sa.Enum(*AUDIT_STATUSES, name="audit_status_enum"),
            type_=sa.String(length=20),
            nullable=True,
        )
        sa.Enum(name="organization_status_enum").drop(bind, checkfirst=True)
        sa.Enum(name="audit_status_enum").drop(bind, checkfirst=True)
