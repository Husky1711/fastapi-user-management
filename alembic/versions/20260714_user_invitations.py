"""Add user_invitations table for admin invite onboarding.

Revision ID: 20260714_invitations
Revises: 20260714_email_verify
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_invitations"
down_revision = "20260714_email_verify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_invitations" in inspector.get_table_names():
        return

    op.create_table(
        "user_invitations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        # String role until normalized `roles` / `role_id` tables exist.
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_inv_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name="fk_inv_invited_by",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("token_hash", name="uq_inv_token_hash"),
    )
    op.create_index(
        "idx_inv_org_email",
        "user_invitations",
        ["organization_id", "email"],
    )
    op.create_index("idx_inv_expires", "user_invitations", ["expires_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_invitations" not in inspector.get_table_names():
        return
    op.drop_index("idx_inv_expires", table_name="user_invitations")
    op.drop_index("idx_inv_org_email", table_name="user_invitations")
    op.drop_table("user_invitations")
