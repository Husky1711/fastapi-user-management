"""Initial schema: users, organizations, roles and permissions, sessions, tokens, audit log.

Constraint names are written out in full (they follow app/models/base.py NAMING_CONVENTION),
so later migrations can refer to them. CHECK names are wrapped in op.f() ("final name"):
otherwise Alembic applies the naming convention to them a second time (ck_users_ck_users_…).
Triggers live only here, not in the models.

Revision ID: 0001
Revises:
Create Date: 2026-11-27
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP = sa.DateTime(timezone=True)
UPDATED_AT_TABLES = ("users", "organizations", "roles", "memberships", "sessions", "invitations")


def _id() -> sa.Column[uuid.UUID]:
    return sa.Column("id", sa.Uuid(), nullable=False)


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
    ]


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _create_users() -> None:
    op.create_table(
        "users",
        _id(),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("is_platform_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", TIMESTAMP, nullable=True),
        sa.Column("deleted_at", TIMESTAMP, nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254", name=op.f("ck_users_email_length")
        ),
        sa.CheckConstraint("char_length(full_name) <= 200", name=op.f("ck_users_full_name_length")),
        sa.CheckConstraint(
            "failed_login_count >= 0", name=op.f("ck_users_failed_login_count_not_negative")
        ),
        sa.CheckConstraint(
            "(status = 'deleted') = (deleted_at IS NOT NULL)",
            name=op.f("ck_users_deleted_status_has_deleted_at"),
        ),
        sa.CheckConstraint(
            _in("status", ("active", "disabled", "deleted")), name=op.f("ck_users_status")
        ),
    )


def _create_organizations() -> None:
    op.create_table(
        "organizations",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", postgresql.CITEXT(), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_organizations_name_length")
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 63",
            name=op.f("ck_organizations_slug_format"),
        ),
        sa.CheckConstraint(
            _in("status", ("active", "suspended")), name=op.f("ck_organizations_status")
        ),
    )


def _create_roles_and_permissions() -> None:
    op.create_table(
        "permissions",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_permissions"),
        sa.CheckConstraint("key ~ '^[a-z]+:[a-z_]+$'", name=op.f("ck_permissions_key_format")),
    )
    op.create_table(
        "roles",
        _id(),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_roles"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_roles_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "key",
            name="uq_roles_organization_id_key",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9_]{1,49}$'", name=op.f("ck_roles_key_format")),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 100", name=op.f("ck_roles_name_length")
        ),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_key", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission_key", name="pk_role_permissions"),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_role_permissions_role_id_roles", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["permission_key"],
            ["permissions.key"],
            name="fk_role_permissions_permission_key_permissions",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
    )
    op.create_index("ix_role_permissions_permission_key", "role_permissions", ["permission_key"])


def _create_memberships() -> None:
    op.create_table(
        "memberships",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_memberships"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_memberships_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_memberships_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_memberships_role_id_roles", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "user_id", "organization_id", name="uq_memberships_user_id_organization_id"
        ),
    )
    op.create_index(
        "ix_memberships_organization_id_created_at",
        "memberships",
        ["organization_id", "created_at"],
    )
    op.create_index("ix_memberships_role_id", "memberships", ["role_id"])


def _token_hash_check(table: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "octet_length(token_hash) = 32", name=op.f(f"ck_{table}_token_hash_size")
    )


def _expiry_check(table: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "expires_at > created_at", name=op.f(f"ck_{table}_expires_after_created")
    )


def _user_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["users.id"], name=f"fk_{table}_user_id_users", ondelete="CASCADE"
    )


def _create_sessions() -> None:
    op.create_table(
        "sessions",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("revoked_at", TIMESTAMP, nullable=True),
        sa.Column("last_used_at", TIMESTAMP, nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        _user_fk("sessions"),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        _token_hash_check("sessions"),
        _expiry_check("sessions"),
        sa.CheckConstraint(
            "char_length(user_agent) <= 256", name=op.f("ck_sessions_user_agent_length")
        ),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_family_id", "sessions", ["family_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])


def _create_one_time_tokens() -> None:
    op.create_table(
        "one_time_tokens",
        _id(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("used_at", TIMESTAMP, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_one_time_tokens"),
        _user_fk("one_time_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_one_time_tokens_token_hash"),
        _token_hash_check("one_time_tokens"),
        _expiry_check("one_time_tokens"),
        sa.CheckConstraint(
            _in("purpose", ("verify_email", "reset_password")),
            name=op.f("ck_one_time_tokens_purpose"),
        ),
    )
    op.create_index("ix_one_time_tokens_user_id_purpose", "one_time_tokens", ["user_id", "purpose"])
    op.create_index("ix_one_time_tokens_expires_at", "one_time_tokens", ["expires_at"])


def _create_invitations() -> None:
    op.create_table(
        "invitations",
        _id(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("accepted_at", TIMESTAMP, nullable=True),
        sa.Column("revoked_at", TIMESTAMP, nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_invitations"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_invitations_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name="fk_invitations_role_id_roles", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name="fk_invitations_invited_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
        _token_hash_check("invitations"),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 3 AND 254", name=op.f("ck_invitations_email_length")
        ),
        _expiry_check("invitations"),
        sa.CheckConstraint(
            "accepted_at IS NULL OR revoked_at IS NULL",
            name=op.f("ck_invitations_not_accepted_and_revoked"),
        ),
    )
    op.create_index(
        "uq_invitations_organization_id_email_pending",
        "invitations",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )
    op.create_index(
        "ix_invitations_organization_id_created_at",
        "invitations",
        ["organization_id", "created_at"],
    )
    op.create_index("ix_invitations_role_id", "invitations", ["role_id"])
    op.create_index("ix_invitations_invited_by_user_id", "invitations", ["invited_by_user_id"])
    op.create_index("ix_invitations_expires_at", "invitations", ["expires_at"])


def _create_audit_logs() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP, server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_audit_logs_organization_id_organizations",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "action ~ '^[a-z_]+(\\.[a-z_]+)+$'", name=op.f("ck_audit_logs_action_format")
        ),
    )
    op.create_index(
        "ix_audit_logs_organization_id_created_at", "audit_logs", ["organization_id", "created_at"]
    )
    op.create_index(
        "ix_audit_logs_actor_user_id_created_at", "audit_logs", ["actor_user_id", "created_at"]
    )


# clock_timestamp(), not now(): now() is fixed for the whole transaction, so an update made in
# the same transaction as the insert would otherwise not move updated_at.
SET_UPDATED_AT = """
CREATE FUNCTION set_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END
$$
"""

# A membership or invitation may use a system role or a role of its own organization only.
CHECK_ROLE_SCOPE = """
CREATE FUNCTION check_role_scope() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    role_organization_id uuid;
BEGIN
    SELECT organization_id INTO role_organization_id FROM roles WHERE id = NEW.role_id;
    IF role_organization_id IS NOT NULL
       AND role_organization_id IS DISTINCT FROM NEW.organization_id THEN
        RAISE EXCEPTION 'role belongs to another organization'
            USING ERRCODE = 'check_violation', CONSTRAINT = 'role_scope';
    END IF;
    RETURN NEW;
END
$$
"""

# Moving a custom role to another organization would silently break the rule above.
FORBID_ROLE_MOVE = """
CREATE FUNCTION forbid_role_organization_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'a role cannot move to another organization'
        USING ERRCODE = 'check_violation', CONSTRAINT = 'role_organization_fixed';
END
$$
"""


def _create_triggers() -> None:
    op.execute(SET_UPDATED_AT)
    for table in UPDATED_AT_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_set_updated_at BEFORE UPDATE ON {table} FOR EACH ROW "
            "WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()"
        )
    op.execute(CHECK_ROLE_SCOPE)
    for table in ("memberships", "invitations"):
        op.execute(
            f"CREATE TRIGGER {table}_role_scope BEFORE INSERT OR UPDATE OF role_id, "
            f"organization_id ON {table} FOR EACH ROW EXECUTE FUNCTION check_role_scope()"
        )
    op.execute(FORBID_ROLE_MOVE)
    op.execute(
        "CREATE TRIGGER roles_organization_fixed BEFORE UPDATE OF organization_id ON roles "
        "FOR EACH ROW WHEN (OLD.organization_id IS DISTINCT FROM NEW.organization_id) "
        "EXECUTE FUNCTION forbid_role_organization_change()"
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    _create_users()
    _create_organizations()
    _create_roles_and_permissions()
    _create_memberships()
    _create_sessions()
    _create_one_time_tokens()
    _create_invitations()
    _create_audit_logs()
    _create_triggers()


def downgrade() -> None:
    for table in (
        "audit_logs",
        "invitations",
        "one_time_tokens",
        "sessions",
        "memberships",
        "role_permissions",
        "roles",
        "permissions",
        "organizations",
        "users",
    ):
        op.drop_table(table)  # drops the table's indexes and triggers with it
    for function in ("set_updated_at", "check_role_scope", "forbid_role_organization_change"):
        op.execute(f"DROP FUNCTION {function}()")
    op.execute("DROP EXTENSION IF EXISTS citext")
