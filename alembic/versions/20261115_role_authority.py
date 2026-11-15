"""Role authority: user_roles is the only role store; role rules become data.

* ``roles`` gains ``level`` / ``is_platform`` / ``can_view_peers`` (see
  services/permissions/role_catalog.py), set for the four system roles.
* Every user gets a system role in ``user_roles`` (from ``users.role`` when present).
* ``users.role`` (and ``idx_users_org_role``) are dropped.

Idempotent (greenfield DBs built from current models already have the new columns
and no ``users.role``). Downgrade restores ``users.role`` from ``user_roles``.

Revision ID: 20261115_role_authority
Revises: 20260716_soft_unique
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_role_authority"
down_revision = "20260716_soft_unique"
branch_labels = None
depends_on = None

# Frozen snapshot of the defaults at this revision (do not import app code).
SYSTEM_ROLES = {
    # name: (level, is_platform, can_view_peers)
    "user": (10, False, False),
    "admin": (20, False, False),
    "organization_admin": (30, False, True),
    "super_admin": (100, True, False),
}


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {i["name"] for i in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    role_cols = _columns(bind, "roles")
    for name, col in (
        ("level", sa.Column("level", sa.Integer(), nullable=False, server_default="0")),
        ("is_platform", sa.Column("is_platform", sa.Boolean(), nullable=False, server_default=sa.text("0"))),
        ("can_view_peers", sa.Column("can_view_peers", sa.Boolean(), nullable=False, server_default=sa.text("0"))),
    ):
        if name not in role_cols:
            op.add_column("roles", col)

    for name, (level, platform, peers) in SYSTEM_ROLES.items():
        bind.execute(
            sa.text(
                "UPDATE roles SET level = :level, is_platform = :platform, "
                "can_view_peers = :peers "
                "WHERE name = :name AND is_system = 1 AND org_scope_key = 0"
            ),
            {"level": level, "platform": platform, "peers": peers, "name": name},
        )

    users_cols = _columns(bind, "users")
    role_expr = "u.role" if "role" in users_cols else "'user'"
    # Users without any system role get one (their users.role, else 'user').
    bind.execute(
        sa.text(
            f"""
            INSERT INTO user_roles (user_id, role_id, granted_at)
            SELECT u.id, r.id, CURRENT_TIMESTAMP
            FROM users u
            JOIN roles r
              ON r.name = COALESCE(NULLIF({role_expr}, ''), 'user')
             AND r.is_system = 1 AND r.org_scope_key = 0
            WHERE NOT EXISTS (
                SELECT 1 FROM user_roles ur
                JOIN roles r2 ON r2.id = ur.role_id
                WHERE ur.user_id = u.id AND r2.is_system = 1 AND r2.org_scope_key = 0
            )
            """
        )
    )

    if "role" in users_cols:
        if "idx_users_org_role" in _indexes(bind, "users"):
            op.drop_index("idx_users_org_role", table_name="users")
        op.drop_column("users", "role")
        if bind.dialect.name == "postgresql":
            op.execute(sa.text("DROP TYPE IF EXISTS user_role_enum"))


def downgrade() -> None:
    bind = op.get_bind()

    if "role" not in _columns(bind, "users"):
        op.add_column(
            "users",
            sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        )
        # Highest-level system role per user (level column still present here).
        bind.execute(
            sa.text(
                """
                UPDATE users u
                JOIN (
                    SELECT ur.user_id, r.name,
                           ROW_NUMBER() OVER (
                               PARTITION BY ur.user_id ORDER BY r.level DESC
                           ) AS rn
                    FROM user_roles ur
                    JOIN roles r ON r.id = ur.role_id
                    WHERE r.is_system = 1 AND r.org_scope_key = 0
                ) best ON best.user_id = u.id AND best.rn = 1
                SET u.role = best.name
                """
            )
            if bind.dialect.name == "mysql"
            else sa.text(
                """
                UPDATE users SET role = best.name
                FROM (
                    SELECT DISTINCT ON (ur.user_id) ur.user_id, r.name
                    FROM user_roles ur JOIN roles r ON r.id = ur.role_id
                    WHERE r.is_system AND r.org_scope_key = 0
                    ORDER BY ur.user_id, r.level DESC
                ) best
                WHERE users.id = best.user_id
                """
            )
        )
        if "idx_users_org_role" not in _indexes(bind, "users"):
            op.create_index("idx_users_org_role", "users", ["organization_id", "role"])

    role_cols = _columns(bind, "roles")
    for name in ("can_view_peers", "is_platform", "level"):
        if name in role_cols:
            op.drop_column("roles", name)
