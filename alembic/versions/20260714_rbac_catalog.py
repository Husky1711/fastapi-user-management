"""Normalized RBAC tables: permissions, roles, role_permissions, user_roles.

Revision ID: 20260714_rbac_catalog
Revises: 20260714_drop_redund_idx
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_rbac_catalog"
down_revision = "20260714_drop_redund_idx"
branch_labels = None
depends_on = None


SYSTEM_PERMISSIONS = {
    "users:create": ("Create new users", "users"),
    "users:read": ("View user information", "users"),
    "users:update": ("Update user information", "users"),
    "users:delete": ("Delete users", "users"),
    "users:list": ("List all users", "users"),
    "permissions:read": ("View permission grants and statistics", "permissions"),
    "permissions:grant": ("Grant permissions to users", "permissions"),
    "permissions:revoke": ("Revoke user permissions", "permissions"),
    "organizations:create": ("Create new organizations", "organizations"),
    "organizations:read": ("View organization information", "organizations"),
    "organizations:update": ("Update organization information", "organizations"),
    "organizations:delete": ("Delete organizations", "organizations"),
    "organizations:list": ("List all organizations", "organizations"),
    "sessions:read": ("View user sessions", "sessions"),
    "sessions:revoke": ("Revoke user sessions", "sessions"),
    "sessions:list": ("List all sessions", "sessions"),
    "groups:read": ("View user groups", "groups"),
    "groups:create": ("Create user groups", "groups"),
    "groups:update": ("Update user groups", "groups"),
    "groups:delete": ("Delete user groups", "groups"),
    "audit:read": ("View audit logs", "audit"),
    "audit:export": ("Export audit logs", "audit"),
    "audit:statistics": ("View audit statistics", "audit"),
    "api_keys:create": ("Create API keys", "api_keys"),
    "api_keys:read": ("View API keys", "api_keys"),
    "api_keys:update": ("Update API keys", "api_keys"),
    "api_keys:delete": ("Delete API keys", "api_keys"),
    "api_keys:list": ("List API keys", "api_keys"),
    "system:config": ("Modify system configuration", "system"),
    "system:maintenance": ("Perform system maintenance", "system"),
    "system:backup": ("Create system backups", "system"),
    "system:restore": ("Restore system backups", "system"),
    "reports:generate": ("Generate reports", "reports"),
    "reports:export": ("Export reports", "reports"),
    "analytics:view": ("View analytics dashboard", "analytics"),
    "security:monitor": ("Monitor security events", "security"),
    "security:alerts": ("Manage security alerts", "security"),
    "security:incidents": ("Handle security incidents", "security"),
}

API_KEY_PERMISSIONS = {
    "read:users": ("Read user information", "api_key"),
    "read:organizations": ("Read organization information", "api_key"),
    "read:sessions": ("Read session information", "api_key"),
    "read:audit": ("Read audit logs", "api_key"),
    "read:reports": ("Read reports", "api_key"),
    "write:users": ("Create and update users", "api_key"),
    "write:organizations": ("Create and update organizations", "api_key"),
    "write:sessions": ("Manage sessions", "api_key"),
    "write:audit": ("Write audit logs", "api_key"),
    "admin:system": ("System administration", "api_key"),
    "admin:security": ("Security management", "api_key"),
    "admin:config": ("Configuration management", "api_key"),
    "webhook:send": ("Send webhooks", "api_key"),
    "integration:sync": ("Data synchronization", "api_key"),
    "backup:create": ("Create backups", "api_key"),
    "restore:execute": ("Execute restores", "api_key"),
}

ROLE_DESCS = {
    "user": "Standard end user",
    "admin": "Organization staff administrator",
    "organization_admin": "Organization administrator",
    "super_admin": "Platform super administrator",
}


def _role_perm_names(role_name: str):
    all_names = list(SYSTEM_PERMISSIONS.keys())
    if role_name == "super_admin":
        return all_names
    if role_name in ("admin", "organization_admin"):
        return [n for n in all_names if not n.startswith("system:")]
    return [
        "users:read",
        "sessions:read",
        "groups:read",
        "organizations:read",
    ]


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.UniqueConstraint("name", name="uq_permissions_name"),
    )
    op.create_index("ix_permissions_name", "permissions", ["name"])
    op.create_index("ix_permissions_category", "permissions", ["category"])

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column(
            "org_scope_key",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "name", "org_scope_key", name="uq_roles_name_org_scope"
        ),
    )
    op.create_index("ix_roles_name", "roles", ["name"])
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])
    op.create_index("ix_roles_is_system", "roles", ["is_system"])

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["permission_id"], ["permissions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "role_id", "permission_id", name="uq_role_permissions"
        ),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index(
        "ix_role_permissions_permission_id", "role_permissions", ["permission_id"]
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["granted_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    bind = op.get_bind()
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("category", sa.String),
    )
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("organization_id", sa.Integer),
        sa.column("org_scope_key", sa.Integer),
        sa.column("is_system", sa.Boolean),
        sa.column("description", sa.String),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    user_roles = sa.table(
        "user_roles",
        sa.column("user_id", sa.Integer),
        sa.column("role_id", sa.Integer),
    )
    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("role", sa.String),
    )

    perm_rows = [
        {"name": n, "description": d, "category": c}
        for n, (d, c) in {**SYSTEM_PERMISSIONS, **API_KEY_PERMISSIONS}.items()
    ]
    op.bulk_insert(permissions, perm_rows)

    role_rows = [
        {
            "name": name,
            "organization_id": None,
            "org_scope_key": 0,
            "is_system": True,
            "description": desc,
        }
        for name, desc in ROLE_DESCS.items()
    ]
    op.bulk_insert(roles, role_rows)

    # Map role_permissions after inserting — query IDs
    perm_id_by_name = {
        row.name: row.id
        for row in bind.execute(sa.select(permissions.c.id, permissions.c.name))
    }
    role_id_by_name = {
        row.name: row.id
        for row in bind.execute(sa.select(roles.c.id, roles.c.name))
    }

    rp_rows = []
    for role_name in ROLE_DESCS:
        rid = role_id_by_name[role_name]
        for pname in _role_perm_names(role_name):
            pid = perm_id_by_name.get(pname)
            if pid is not None:
                rp_rows.append({"role_id": rid, "permission_id": pid})
    if rp_rows:
        op.bulk_insert(role_permissions, rp_rows)

    # Backfill user_roles from users.role
    ur_rows = []
    for row in bind.execute(sa.select(users.c.id, users.c.role)):
        rid = role_id_by_name.get(row.role)
        if rid is not None:
            ur_rows.append({"user_id": row.id, "role_id": rid})
    if ur_rows:
        op.bulk_insert(user_roles, ur_rows)


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("permissions")
