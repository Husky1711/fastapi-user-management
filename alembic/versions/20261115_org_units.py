"""Organization units (tree of any depth) + unit-scoped role grants.

* ``org_units``: tree inside an organization (``unit_type`` is free text: department,
  class, ward, site...), materialised ``path`` for subtree checks.
* ``org_unit_members``: people placed in units.
* ``user_roles`` gains ``unit_id`` / ``unit_key``: a role granted on a unit covers the
  unit and its subtree only. Unique key becomes (user_id, role_id, scope_key, unit_key).

Idempotent. Downgrade drops unit grants, units and placements.

Revision ID: 20261115_org_units
Revises: 20261115_org_memberships
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_org_units"
down_revision = "20261115_org_memberships"
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
    tables = _tables(bind)

    if "org_units" not in tables:
        op.create_table(
            "org_units",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id", sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column(
                "parent_id", sa.Integer(),
                sa.ForeignKey("org_units.id", ondelete="RESTRICT"), nullable=True,
            ),
            sa.Column("unit_type", sa.String(50), nullable=False),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("path", sa.String(500), nullable=False),
            sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_org_units_organization_id", "org_units", ["organization_id"])
        op.create_index("ix_org_units_parent_id", "org_units", ["parent_id"])
        op.create_index("ix_org_units_path", "org_units", ["path"])

    if "org_unit_members" not in tables:
        op.create_table(
            "org_unit_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "unit_id", sa.Integer(),
                sa.ForeignKey("org_units.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column(
                "user_id", sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("unit_id", "user_id", name="uq_org_unit_members"),
        )
        op.create_index("ix_org_unit_members_unit_id", "org_unit_members", ["unit_id"])
        op.create_index("ix_org_unit_members_user_id", "org_unit_members", ["user_id"])

    ur_cols = _columns(bind, "user_roles")
    if "unit_id" not in ur_cols:
        op.add_column("user_roles", sa.Column("unit_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_user_roles_unit_id", "user_roles", "org_units",
            ["unit_id"], ["id"], ondelete="CASCADE",
        )
        op.create_index("ix_user_roles_unit_id", "user_roles", ["unit_id"])
    if "unit_key" not in ur_cols:
        op.add_column(
            "user_roles",
            sa.Column("unit_key", sa.Integer(), nullable=False, server_default="0"),
        )

    if "uq_user_roles_scope_unit" not in _uniques(bind, "user_roles"):
        op.create_unique_constraint(
            "uq_user_roles_scope_unit", "user_roles",
            ["user_id", "role_id", "scope_key", "unit_key"],
        )
    if "uq_user_roles_scope" in _uniques(bind, "user_roles"):
        op.drop_constraint("uq_user_roles_scope", "user_roles", type_="unique")


def downgrade() -> None:
    bind = op.get_bind()

    if "unit_id" in _columns(bind, "user_roles"):
        bind.execute(sa.text("DELETE FROM user_roles WHERE unit_id IS NOT NULL"))
        if "uq_user_roles_scope" not in _uniques(bind, "user_roles"):
            op.create_unique_constraint(
                "uq_user_roles_scope", "user_roles", ["user_id", "role_id", "scope_key"]
            )
        if "uq_user_roles_scope_unit" in _uniques(bind, "user_roles"):
            op.drop_constraint("uq_user_roles_scope_unit", "user_roles", type_="unique")
        for fk in sa.inspect(bind).get_foreign_keys("user_roles"):
            if fk.get("constrained_columns") == ["unit_id"] and fk.get("name"):
                op.drop_constraint(fk["name"], "user_roles", type_="foreignkey")
        if "ix_user_roles_unit_id" in _indexes(bind, "user_roles"):
            op.drop_index("ix_user_roles_unit_id", table_name="user_roles")
        op.drop_column("user_roles", "unit_id")
    if "unit_key" in _columns(bind, "user_roles"):
        op.drop_column("user_roles", "unit_key")

    tables = _tables(bind)
    if "org_unit_members" in tables:
        op.drop_table("org_unit_members")
    if "org_units" in tables:
        op.drop_table("org_units")
