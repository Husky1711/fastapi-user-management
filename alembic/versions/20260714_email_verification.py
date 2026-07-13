"""Add email verification + password_changed_at.

Revision ID: 20260714_email_verify
Revises: 20260714_status_enums
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_email_verify"
down_revision = "20260714_status_enums"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "email_verified_at" not in user_cols:
        op.add_column(
            "users",
            sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        )
        # Existing accounts are treated as already verified so login is not broken.
        op.execute(
            sa.text(
                "UPDATE users SET email_verified_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                "WHERE email_verified_at IS NULL"
            )
        )

    if "password_changed_at" not in user_cols:
        op.add_column(
            "users",
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.execute(
            sa.text(
                "UPDATE users SET password_changed_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) "
                "WHERE password_changed_at IS NULL"
            )
        )

    if "email_verification_tokens" not in inspector.get_table_names():
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("token_hash", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name="fk_evt_user_id",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("token_hash", name="uq_evt_token_hash"),
        )
        op.create_index(
            "idx_evt_user_expires",
            "email_verification_tokens",
            ["user_id", "expires_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "email_verification_tokens" in inspector.get_table_names():
        op.drop_index("idx_evt_user_expires", table_name="email_verification_tokens")
        op.drop_table("email_verification_tokens")

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "password_changed_at" in user_cols:
        op.drop_column("users", "password_changed_at")
    if "email_verified_at" in user_cols:
        op.drop_column("users", "email_verified_at")
