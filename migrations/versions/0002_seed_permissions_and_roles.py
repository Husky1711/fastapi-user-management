"""Seed the permission catalogue and the system roles owner, admin and member.

The values are copied from app/core/permissions.py as they were when this migration was
written (migrations never import app code that may change later). A test checks that the
code and the database still agree.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "org:read": "View the organization",
    "org:update": "Change the organization's name and settings",
    "org:delete": "Delete the organization",
    "org:transfer": "Transfer ownership of the organization",
    "members:read": "List members and their roles",
    "members:invite": "Invite people to the organization",
    "members:update": "Change members' roles",
    "members:remove": "Remove members from the organization",
    "invitations:read": "List the organization's invitations",
    "invitations:revoke": "Revoke pending invitations",
    "roles:read": "List roles and their permissions",
    "roles:manage": "Create, change and delete custom roles",
    "audit:read": "Read the organization's audit log",
}
OWNER_ONLY = {"org:delete", "org:transfer", "roles:manage"}
SYSTEM_ROLES = {
    "owner": ("Owner", set(PERMISSIONS)),
    "admin": ("Admin", set(PERMISSIONS) - OWNER_ONLY),
    "member": ("Member", {"org:read", "members:read"}),
}

permissions = sa.table("permissions", sa.column("key"), sa.column("description"))
role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_key"))


def upgrade() -> None:
    op.bulk_insert(permissions, [{"key": k, "description": d} for k, d in PERMISSIONS.items()])
    connection = op.get_bind()
    for key, (name, granted) in SYSTEM_ROLES.items():
        role_id = connection.execute(
            sa.text(
                "INSERT INTO roles (id, organization_id, key, name) "
                "VALUES (gen_random_uuid(), NULL, :key, :name) RETURNING id"
            ),
            {"key": key, "name": name},
        ).scalar_one()
        op.bulk_insert(
            role_permissions,
            [{"role_id": role_id, "permission_key": p} for p in sorted(granted)],
        )


def downgrade() -> None:
    # Fails (RESTRICT) while any membership or invitation still uses a system role: removing
    # roles that people hold must be a deliberate data migration, not a side effect.
    op.execute(
        sa.text("DELETE FROM roles WHERE organization_id IS NULL AND key IN :keys").bindparams(
            sa.bindparam("keys", list(SYSTEM_ROLES), expanding=True)
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE key IN :keys").bindparams(
            sa.bindparam("keys", list(PERMISSIONS), expanding=True)
        )
    )
