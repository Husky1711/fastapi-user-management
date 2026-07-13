"""Add organization_id to user_permissions for tenant-scoped audit.

Revision ID: 20260714_perm_org_id
Revises: 20260714_drop_dup_fks
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_perm_org_id"
down_revision = "20260714_drop_dup_fks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("user_permissions")}
    if "organization_id" not in cols:
        op.add_column(
            "user_permissions",
            sa.Column("organization_id", sa.Integer(), nullable=True),
        )
        op.execute(
            sa.text(
                """
                UPDATE user_permissions up
                INNER JOIN users u ON u.id = up.user_id
                SET up.organization_id = u.organization_id
                WHERE up.organization_id IS NULL
                """
            )
        )
        # Orphans after user delete should be rare (CASCADE); drop any leftover nulls
        op.execute(sa.text("DELETE FROM user_permissions WHERE organization_id IS NULL"))
        dialect = bind.dialect.name
        if dialect == "mysql":
            op.execute(
                sa.text(
                    "ALTER TABLE user_permissions "
                    "MODIFY COLUMN organization_id INT NOT NULL"
                )
            )
        else:
            op.alter_column(
                "user_permissions",
                "organization_id",
                existing_type=sa.Integer(),
                nullable=False,
            )
        op.create_foreign_key(
            "fk_user_permissions_organization_id",
            "user_permissions",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(
            "ix_user_permissions_organization_id",
            "user_permissions",
            ["organization_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("user_permissions")}
    if "organization_id" not in cols:
        return
    fks = {fk["name"] for fk in inspector.get_foreign_keys("user_permissions")}
    if "fk_user_permissions_organization_id" in fks:
        op.drop_constraint(
            "fk_user_permissions_organization_id",
            "user_permissions",
            type_="foreignkey",
        )
    indexes = {ix["name"] for ix in inspector.get_indexes("user_permissions")}
    if "ix_user_permissions_organization_id" in indexes:
        op.drop_index("ix_user_permissions_organization_id", table_name="user_permissions")
    op.drop_column("user_permissions", "organization_id")
