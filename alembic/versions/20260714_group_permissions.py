"""group_permissions + backup_codes_generated_at.

Revision ID: 20260714_group_perms
Revises: 20260714_rbac_catalog
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_group_perms"
down_revision = "20260714_rbac_catalog"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_table(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "group_permissions"):
        op.create_table(
            "group_permissions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("group_id", sa.Integer(), nullable=False),
            sa.Column("permission_id", sa.Integer(), nullable=False),
            sa.Column("granted_by", sa.Integer(), nullable=True),
            sa.Column(
                "granted_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["group_id"], ["user_groups.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["permission_id"], ["permissions.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["granted_by"], ["users.id"], ondelete="SET NULL"
            ),
            sa.UniqueConstraint(
                "group_id", "permission_id", name="uq_group_permissions"
            ),
        )
        op.create_index(
            "ix_group_permissions_group_id", "group_permissions", ["group_id"]
        )
        op.create_index(
            "ix_group_permissions_permission_id",
            "group_permissions",
            ["permission_id"],
        )

    if not _has_column(inspector, "users", "backup_codes_generated_at"):
        op.add_column(
            "users",
            sa.Column("backup_codes_generated_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "users", "backup_codes_generated_at"):
        op.drop_column("users", "backup_codes_generated_at")
    if _has_table(inspector, "group_permissions"):
        op.drop_table("group_permissions")
