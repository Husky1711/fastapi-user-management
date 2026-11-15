"""Sector templates, permission scopes ('own'), relations; flexible invitation roles.

* ``organizations.sector_template`` / ``vocabulary_overrides``.
* ``role_permissions.scope``: 'all' (default, unchanged behaviour) or 'own'.
* ``resource_relations``: subject —relation→ object (e.g. teacher teaches student).
* ``user_invitations.role``: ENUM of the four default roles -> VARCHAR(50), so custom
  roles (teacher, doctor...) can be invited.

Idempotent. Downgrade restores the ENUM (custom invite roles become 'user').

Revision ID: 20261115_templates_relations
Revises: 20261115_org_units
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_templates_relations"
down_revision = "20261115_org_units"
branch_labels = None
depends_on = None

DEFAULT_ROLES = ("user", "admin", "organization_admin", "super_admin")


def _tables(bind):
    return set(sa.inspect(bind).get_table_names())


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    org_cols = _columns(bind, "organizations")
    if "sector_template" not in org_cols:
        op.add_column("organizations", sa.Column("sector_template", sa.String(50), nullable=True))
    if "vocabulary_overrides" not in org_cols:
        op.add_column("organizations", sa.Column("vocabulary_overrides", sa.JSON(), nullable=True))

    if "scope" not in _columns(bind, "role_permissions"):
        op.add_column(
            "role_permissions",
            sa.Column("scope", sa.String(10), nullable=False, server_default="all"),
        )

    if "resource_relations" not in _tables(bind):
        op.create_table(
            "resource_relations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "organization_id", sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column(
                "subject_user_id", sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("relation", sa.String(50), nullable=False),
            sa.Column("object_type", sa.String(50), nullable=False, server_default="user"),
            sa.Column("object_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_by", sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint(
                "organization_id", "subject_user_id", "relation", "object_type", "object_id",
                name="uq_resource_relations",
            ),
        )
        op.create_index("ix_resource_relations_subject_user_id", "resource_relations", ["subject_user_id"])
        op.create_index(
            "ix_resource_relations_object", "resource_relations",
            ["organization_id", "object_type", "object_id"],
        )

    if "user_invitations" in _tables(bind):
        if bind.dialect.name == "mysql":
            op.execute(sa.text(
                "ALTER TABLE user_invitations MODIFY COLUMN role VARCHAR(50) NOT NULL DEFAULT 'user'"
            ))
        else:
            op.alter_column(
                "user_invitations", "role",
                type_=sa.String(50), existing_nullable=False, server_default="user",
                postgresql_using="role::text",
            )


def downgrade() -> None:
    bind = op.get_bind()
    if "user_invitations" in _tables(bind):
        quoted = ", ".join(f"'{r}'" for r in DEFAULT_ROLES)
        op.execute(sa.text(f"UPDATE user_invitations SET role = 'user' WHERE role NOT IN ({quoted})"))
        if bind.dialect.name == "mysql":
            op.execute(sa.text(
                f"ALTER TABLE user_invitations MODIFY COLUMN role ENUM({quoted}) NOT NULL DEFAULT 'user'"
            ))
    if "resource_relations" in _tables(bind):
        op.drop_table("resource_relations")
    if "scope" in _columns(bind, "role_permissions"):
        op.drop_column("role_permissions", "scope")
    org_cols = _columns(bind, "organizations")
    for col in ("vocabulary_overrides", "sector_template"):
        if col in org_cols:
            op.drop_column("organizations", col)
