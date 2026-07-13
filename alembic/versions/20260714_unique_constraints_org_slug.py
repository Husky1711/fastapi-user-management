"""Unique constraints, org slug, and retention-related column defaults.

Revision ID: 20260714_uniques_slug
Revises: 20260714_invitations
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_uniques_slug"
down_revision = "20260714_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- organizations.slug ---
    org_cols = {c["name"] for c in inspector.get_columns("organizations")}
    if "slug" not in org_cols:
        op.add_column(
            "organizations",
            sa.Column("slug", sa.String(length=100), nullable=True),
        )
        op.execute(
            sa.text(
                "UPDATE organizations SET slug = CONCAT('org-', id) WHERE slug IS NULL OR slug = ''"
            )
        )
        # Ensure uniqueness for legacy rows
        op.execute(
            sa.text(
                "UPDATE organizations o "
                "JOIN ("
                "  SELECT slug, MIN(id) AS keep_id FROM organizations GROUP BY slug HAVING COUNT(*) > 1"
                ") d ON o.slug = d.slug AND o.id <> d.keep_id "
                "SET o.slug = CONCAT(o.slug, '-', o.id)"
            )
        )
        if bind.dialect.name == "mysql":
            op.execute(
                sa.text(
                    "ALTER TABLE organizations "
                    "MODIFY COLUMN slug VARCHAR(100) NOT NULL"
                )
            )
            op.create_index("uq_organizations_slug", "organizations", ["slug"], unique=True)
        else:
            op.alter_column(
                "organizations",
                "slug",
                existing_type=sa.String(length=100),
                nullable=False,
            )
            op.create_index("uq_organizations_slug", "organizations", ["slug"], unique=True)

    # --- user_groups UNIQUE (organization_id, name) ---
    # Rename soft-deleted duplicates so active names stay unique.
    op.execute(
        sa.text(
            "UPDATE user_groups "
            "SET name = CONCAT(name, '__deleted__', id) "
            "WHERE is_active = 0 AND name NOT LIKE '%__deleted__%'"
        )
    )
    # Keep one row per (org, name); rename extras
    op.execute(
        sa.text(
            "UPDATE user_groups g "
            "JOIN ("
            "  SELECT organization_id, name, MIN(id) AS keep_id "
            "  FROM user_groups GROUP BY organization_id, name HAVING COUNT(*) > 1"
            ") d ON g.organization_id = d.organization_id AND g.name = d.name AND g.id <> d.keep_id "
            "SET g.name = CONCAT(g.name, '__dup__', g.id)"
        )
    )
    existing_ug = {ix["name"] for ix in inspector.get_indexes("user_groups")}
    if "uq_user_groups_org_name" not in existing_ug:
        op.create_index(
            "uq_user_groups_org_name",
            "user_groups",
            ["organization_id", "name"],
            unique=True,
        )

    # --- user_permissions UNIQUE, normalize NULLs for MySQL ---
    op.execute(
        sa.text(
            "UPDATE user_permissions SET resource_type = '' WHERE resource_type IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE user_permissions SET resource_id = 0 WHERE resource_id IS NULL"
        )
    )
    # Deactivate duplicate actives, keep lowest id
    op.execute(
        sa.text(
            "UPDATE user_permissions up "
            "JOIN ("
            "  SELECT user_id, permission_name, resource_type, resource_id, MIN(id) AS keep_id "
            "  FROM user_permissions "
            "  WHERE is_active = 1 "
            "  GROUP BY user_id, permission_name, resource_type, resource_id "
            "  HAVING COUNT(*) > 1"
            ") d ON up.user_id = d.user_id "
            "   AND up.permission_name = d.permission_name "
            "   AND up.resource_type = d.resource_type "
            "   AND up.resource_id = d.resource_id "
            "   AND up.id <> d.keep_id "
            "SET up.is_active = 0"
        )
    )
    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE user_permissions "
                "MODIFY COLUMN resource_type VARCHAR(50) NOT NULL DEFAULT ''"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE user_permissions "
                "MODIFY COLUMN resource_id INT NOT NULL DEFAULT 0"
            )
        )
    else:
        op.alter_column(
            "user_permissions",
            "resource_type",
            existing_type=sa.String(length=50),
            nullable=False,
            server_default="",
        )
        op.alter_column(
            "user_permissions",
            "resource_id",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )

    inspector = sa.inspect(bind)
    existing_up = {ix["name"] for ix in inspector.get_indexes("user_permissions")}
    if "uq_user_permission_grant" not in existing_up:
        op.create_index(
            "uq_user_permission_grant",
            "user_permissions",
            ["user_id", "permission_name", "resource_type", "resource_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    up_indexes = {ix["name"] for ix in inspector.get_indexes("user_permissions")}
    if "uq_user_permission_grant" in up_indexes:
        op.drop_index("uq_user_permission_grant", table_name="user_permissions")

    ug_indexes = {ix["name"] for ix in inspector.get_indexes("user_groups")}
    if "uq_user_groups_org_name" in ug_indexes:
        op.drop_index("uq_user_groups_org_name", table_name="user_groups")

    org_cols = {c["name"] for c in inspector.get_columns("organizations")}
    if "slug" in org_cols:
        org_indexes = {ix["name"] for ix in inspector.get_indexes("organizations")}
        if "uq_organizations_slug" in org_indexes:
            op.drop_index("uq_organizations_slug", table_name="organizations")
        op.drop_column("organizations", "slug")
