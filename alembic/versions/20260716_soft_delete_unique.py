"""Email length align + soft-delete–safe unique identifiers.

Revision ID: 20260716_soft_unique
Revises: 20260714_v1_harden

- users.email → VARCHAR(255) (match invite/verify)
- Replace global UNIQUE on users.email/username with active-only
  functional unique indexes (deleted_at IS NULL)
- Same for organizations.name / organizations.slug
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260716_soft_unique"
down_revision = "20260714_v1_harden"
branch_labels = None
depends_on = None


def _mysql() -> bool:
    return op.get_bind().dialect.name == "mysql"


def _index_names(table: str) -> set[str]:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- users.email length ---
    if "users" in inspector.get_table_names() and _mysql():
        op.execute(
            sa.text(
                "ALTER TABLE users MODIFY COLUMN email VARCHAR(255) NOT NULL"
            )
        )
    elif "users" in inspector.get_table_names():
        op.alter_column(
            "users",
            "email",
            existing_type=sa.String(100),
            type_=sa.String(255),
            existing_nullable=False,
        )

    # --- users: active-only unique email/username ---
    if "users" in inspector.get_table_names() and _mysql():
        indexes = _index_names("users")
        # Drop global unique indexes (names vary by historical create path)
        for name in ("ix_users_email", "email", "uq_users_email"):
            if name in indexes:
                op.drop_index(name, table_name="users")
                indexes.discard(name)
        for name in ("ix_users_username", "username", "uq_users_username"):
            if name in indexes:
                op.drop_index(name, table_name="users")
                indexes.discard(name)

        indexes = _index_names("users")
        if "uq_users_email_active" not in indexes:
            op.execute(
                sa.text(
                    """
                    CREATE UNIQUE INDEX uq_users_email_active
                    ON users ((CASE WHEN deleted_at IS NULL THEN email END))
                    """
                )
            )
        if "uq_users_username_active" not in indexes:
            op.execute(
                sa.text(
                    """
                    CREATE UNIQUE INDEX uq_users_username_active
                    ON users ((CASE WHEN deleted_at IS NULL THEN username END))
                    """
                )
            )
        # Non-unique lookup helpers (functional unique is not ideal for plain WHERE email=)
        indexes = _index_names("users")
        if "ix_users_email" not in indexes:
            op.create_index("ix_users_email", "users", ["email"])
        if "ix_users_username" not in indexes:
            op.create_index("ix_users_username", "users", ["username"])

    # --- organizations: active-only unique name/slug ---
    if "organizations" in inspector.get_table_names() and _mysql():
        indexes = _index_names("organizations")
        for name in (
            "name",
            "ix_organizations_name",
            "uq_organizations_name",
            "slug",
            "ix_organizations_slug",
            "uq_organizations_slug",
        ):
            if name in indexes:
                try:
                    op.drop_index(name, table_name="organizations")
                except Exception:
                    pass
                indexes.discard(name)

        # Also drop unique constraints if present as constraints
        uqs = {
            uq["name"]
            for uq in inspector.get_unique_constraints("organizations")
            if uq.get("name")
        }
        for name in list(uqs):
            cols = next(
                (
                    uq["column_names"]
                    for uq in inspector.get_unique_constraints("organizations")
                    if uq.get("name") == name
                ),
                [],
            )
            if cols in (["name"], ["slug"]):
                op.drop_constraint(name, "organizations", type_="unique")

        indexes = _index_names("organizations")
        if "uq_organizations_name_active" not in indexes:
            op.execute(
                sa.text(
                    """
                    CREATE UNIQUE INDEX uq_organizations_name_active
                    ON organizations ((CASE WHEN deleted_at IS NULL THEN name END))
                    """
                )
            )
        if "uq_organizations_slug_active" not in indexes:
            op.execute(
                sa.text(
                    """
                    CREATE UNIQUE INDEX uq_organizations_slug_active
                    ON organizations ((CASE WHEN deleted_at IS NULL THEN slug END))
                    """
                )
            )
        indexes = _index_names("organizations")
        if "ix_organizations_name" not in indexes:
            op.create_index("ix_organizations_name", "organizations", ["name"])
        if "ix_organizations_slug" not in indexes:
            op.create_index("ix_organizations_slug", "organizations", ["slug"])


def downgrade() -> None:
    if not _mysql():
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" in inspector.get_table_names():
        indexes = _index_names("users")
        for name in (
            "uq_users_email_active",
            "uq_users_username_active",
            "ix_users_email",
            "ix_users_username",
        ):
            if name in indexes:
                op.drop_index(name, table_name="users")
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_username", "users", ["username"], unique=True)
        op.execute(
            sa.text(
                "ALTER TABLE users MODIFY COLUMN email VARCHAR(100) NOT NULL"
            )
        )

    if "organizations" in inspector.get_table_names():
        indexes = _index_names("organizations")
        for name in (
            "uq_organizations_name_active",
            "uq_organizations_slug_active",
            "ix_organizations_name",
            "ix_organizations_slug",
        ):
            if name in indexes:
                op.drop_index(name, table_name="organizations")
        op.create_index("ix_organizations_name", "organizations", ["name"], unique=True)
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
