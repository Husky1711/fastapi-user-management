"""organization_settings per-tenant config.

Revision ID: 20260714_org_settings
Revises: 20260714_group_perms
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_org_settings"
down_revision = "20260714_group_perms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "organization_settings" in inspector.get_table_names():
        return

    op.create_table(
        "organization_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("setting_key", sa.String(length=100), nullable=False),
        sa.Column("setting_value", sa.Text(), nullable=False),
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
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "organization_id", "setting_key", name="uq_org_settings_key"
        ),
    )
    op.create_index(
        "ix_organization_settings_organization_id",
        "organization_settings",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_settings_setting_key",
        "organization_settings",
        ["setting_key"],
    )


def downgrade() -> None:
    op.drop_table("organization_settings")
