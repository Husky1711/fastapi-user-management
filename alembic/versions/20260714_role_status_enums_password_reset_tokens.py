"""Add users role/status ENUMs and password_reset_tokens table.

Revision ID: 20260714_enums_reset
Revises: 20260709_core_fks
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_enums_reset"
down_revision = "20260709_core_fks"
branch_labels = None
depends_on = None

USER_ROLES = ("user", "admin", "organization_admin", "super_admin")
USER_STATUSES = ("active", "inactive", "suspended", "pending")


def upgrade() -> None:
    bind = op.get_bind()

    # Normalize free-form strings before converting to ENUM.
    op.execute(
        sa.text(
            "UPDATE users SET role = 'user' "
            "WHERE role IS NULL OR role NOT IN "
            "('user', 'admin', 'organization_admin', 'super_admin')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE users SET status = 'active' "
            "WHERE status IS NULL OR status NOT IN "
            "('active', 'inactive', 'suspended', 'pending')"
        )
    )

    op.execute(
        sa.text(
            "UPDATE users SET organization_id = 1 WHERE organization_id IS NULL"
        )
    )

    # MySQL ENUM via native ALTER (portable enough for this project's dialect).
    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE users "
                "MODIFY COLUMN role ENUM("
                "'user','admin','organization_admin','super_admin'"
                ") NOT NULL DEFAULT 'user'"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE users "
                "MODIFY COLUMN status ENUM("
                "'active','inactive','suspended','pending'"
                ") NOT NULL DEFAULT 'active'"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE users "
                "MODIFY COLUMN organization_id INT NOT NULL"
            )
        )
    else:
        role_enum = sa.Enum(*USER_ROLES, name="user_role_enum")
        status_enum = sa.Enum(*USER_STATUSES, name="user_status_enum")
        role_enum.create(bind, checkfirst=True)
        status_enum.create(bind, checkfirst=True)
        op.alter_column(
            "users",
            "role",
            existing_type=sa.String(length=20),
            type_=role_enum,
            existing_nullable=True,
            nullable=False,
            server_default="user",
        )
        op.alter_column(
            "users",
            "status",
            existing_type=sa.String(length=20),
            type_=status_enum,
            existing_nullable=True,
            nullable=False,
            server_default="active",
        )
        op.alter_column(
            "users",
            "organization_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    inspector = sa.inspect(bind)
    if "password_reset_tokens" not in inspector.get_table_names():
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("requested_ip", sa.String(length=45), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name="fk_prt_user_id",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("token_hash", name="uq_prt_token_hash"),
        )
        op.create_index(
            "idx_prt_user_expires",
            "password_reset_tokens",
            ["user_id", "expires_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "password_reset_tokens" in inspector.get_table_names():
        op.drop_index("idx_prt_user_expires", table_name="password_reset_tokens")
        op.drop_table("password_reset_tokens")

    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE users MODIFY COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE users "
                "MODIFY COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE users "
                "MODIFY COLUMN organization_id INT NULL DEFAULT 1"
            )
        )
    else:
        op.alter_column(
            "users",
            "role",
            existing_type=sa.Enum(*USER_ROLES, name="user_role_enum"),
            type_=sa.String(length=20),
            nullable=False,
            server_default="user",
        )
        op.alter_column(
            "users",
            "status",
            existing_type=sa.Enum(*USER_STATUSES, name="user_status_enum"),
            type_=sa.String(length=20),
            nullable=False,
            server_default="active",
        )
        op.alter_column(
            "users",
            "organization_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        sa.Enum(name="user_role_enum").drop(bind, checkfirst=True)
        sa.Enum(name="user_status_enum").drop(bind, checkfirst=True)
