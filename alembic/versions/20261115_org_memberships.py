"""Organization memberships + organization-scoped role assignments.

* ``organization_memberships`` (user ↔ organization, many-to-many); backfilled with
  every user's home org (``users.organization_id``).
* ``user_roles`` gains ``organization_id`` / ``scope_key``: tenant (non-platform)
  system roles are scoped to the user's home org; platform roles stay unscoped.
  Unique key becomes (user_id, role_id, scope_key).

Idempotent. Downgrade keeps one assignment per (user, role), preferring the home org.

Revision ID: 20261115_org_memberships
Revises: 20261115_role_authority
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_org_memberships"
down_revision = "20261115_role_authority"
branch_labels = None
depends_on = None


def _tables(bind):
    return set(sa.inspect(bind).get_table_names())


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _uniques(bind, table):
    insp = sa.inspect(bind)
    names = {u["name"] for u in insp.get_unique_constraints(table)}
    names |= {i["name"] for i in insp.get_indexes(table) if i.get("unique")}
    return names


def _indexes(bind, table):
    return {i["name"] for i in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if "organization_memberships" not in _tables(bind):
        op.create_table(
            "organization_memberships",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id", sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column(
                "organization_id", sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "organization_id", name="uq_org_memberships_user_org"),
        )
        op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"])
        op.create_index(
            "ix_organization_memberships_organization_id", "organization_memberships", ["organization_id"]
        )

    bind.execute(
        sa.text(
            """
            INSERT INTO organization_memberships (user_id, organization_id, status, created_at)
            SELECT u.id, u.organization_id, 'active', CURRENT_TIMESTAMP
            FROM users u
            WHERE u.organization_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM organization_memberships m
                WHERE m.user_id = u.id AND m.organization_id = u.organization_id
              )
            """
        )
    )

    ur_cols = _columns(bind, "user_roles")
    if "organization_id" not in ur_cols:
        op.add_column("user_roles", sa.Column("organization_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_user_roles_organization_id", "user_roles", "organizations",
            ["organization_id"], ["id"], ondelete="CASCADE",
        )
        op.create_index("ix_user_roles_organization_id", "user_roles", ["organization_id"])
    if "scope_key" not in ur_cols:
        op.add_column(
            "user_roles",
            sa.Column("scope_key", sa.Integer(), nullable=False, server_default="0"),
        )

    # Tenant system roles apply in the user's home org; platform roles stay global.
    bind.execute(
        sa.text(
            """
            UPDATE user_roles
            SET organization_id = (SELECT u.organization_id FROM users u WHERE u.id = user_roles.user_id),
                scope_key = COALESCE(
                    (SELECT u.organization_id FROM users u WHERE u.id = user_roles.user_id), 0)
            WHERE organization_id IS NULL
              AND role_id IN (
                SELECT r.id FROM roles r
                WHERE r.is_system = 1 AND r.org_scope_key = 0 AND r.is_platform = 0
              )
            """
        )
        if bind.dialect.name != "mysql"
        else sa.text(
            """
            UPDATE user_roles ur
            JOIN users u ON u.id = ur.user_id
            JOIN roles r ON r.id = ur.role_id
            SET ur.organization_id = u.organization_id,
                ur.scope_key = COALESCE(u.organization_id, 0)
            WHERE ur.organization_id IS NULL
              AND r.is_system = 1 AND r.org_scope_key = 0 AND r.is_platform = 0
            """
        )
    )

    uniques = _uniques(bind, "user_roles")
    if "uq_user_roles_scope" not in uniques:
        op.create_unique_constraint(
            "uq_user_roles_scope", "user_roles", ["user_id", "role_id", "scope_key"]
        )
    if "uq_user_roles" in _uniques(bind, "user_roles"):
        # ix_user_roles_user_id keeps the FK on user_id indexed
        if "ix_user_roles_user_id" not in _indexes(bind, "user_roles"):
            op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
        op.drop_constraint("uq_user_roles", "user_roles", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()

    if "organization_id" in _columns(bind, "user_roles"):
        # One row per (user, role): prefer the home-org (or global) assignment.
        bind.execute(
            sa.text(
                """
                DELETE ur FROM user_roles ur
                JOIN users u ON u.id = ur.user_id
                JOIN user_roles keep
                  ON keep.user_id = ur.user_id AND keep.role_id = ur.role_id
                 AND keep.id <> ur.id
                 AND (keep.organization_id IS NULL OR keep.organization_id = u.organization_id)
                WHERE NOT (ur.organization_id IS NULL OR ur.organization_id = u.organization_id)
                """
            )
            if bind.dialect.name == "mysql"
            else sa.text(
                """
                DELETE FROM user_roles ur
                USING users u, user_roles keep
                WHERE u.id = ur.user_id
                  AND keep.user_id = ur.user_id AND keep.role_id = ur.role_id
                  AND keep.id <> ur.id
                  AND (keep.organization_id IS NULL OR keep.organization_id = u.organization_id)
                  AND NOT (ur.organization_id IS NULL OR ur.organization_id = u.organization_id)
                """
            )
        )
        bind.execute(
            sa.text(
                """
                DELETE FROM user_roles WHERE id NOT IN (
                    SELECT keep_id FROM (
                        SELECT MIN(id) AS keep_id FROM user_roles GROUP BY user_id, role_id
                    ) k
                )
                """
            )
        )
        if "uq_user_roles" not in _uniques(bind, "user_roles"):
            op.create_unique_constraint("uq_user_roles", "user_roles", ["user_id", "role_id"])
        if "uq_user_roles_scope" in _uniques(bind, "user_roles"):
            op.drop_constraint("uq_user_roles_scope", "user_roles", type_="unique")
        # FK name differs on greenfield DBs (built from models): find it by column.
        for fk in sa.inspect(bind).get_foreign_keys("user_roles"):
            if fk.get("constrained_columns") == ["organization_id"] and fk.get("name"):
                op.drop_constraint(fk["name"], "user_roles", type_="foreignkey")
        if "ix_user_roles_organization_id" in _indexes(bind, "user_roles"):
            op.drop_index("ix_user_roles_organization_id", table_name="user_roles")
        op.drop_column("user_roles", "organization_id")
    if "scope_key" in _columns(bind, "user_roles"):
        op.drop_column("user_roles", "scope_key")

    if "organization_memberships" in _tables(bind):
        op.drop_table("organization_memberships")
