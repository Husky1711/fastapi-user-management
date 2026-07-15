"""V1 cutover hardening: flags NOT NULL, permission FK, invite, consent.

Revision ID: 20260714_v1_harden
Revises: 20260714_perm_org_id

- Boolean/flag columns → NOT NULL DEFAULT
- user_permissions.permission_id FK + unique includes organization_id
- Invite role ENUM + one pending invite per (org, email)
- consent_records: ON DELETE SET NULL + optional policy_version
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_v1_harden"
down_revision = "20260714_perm_org_id"
branch_labels = None
depends_on = None


def _mysql() -> bool:
    return op.get_bind().dialect.name == "mysql"


def _modify_bool(table: str, column: str, default: int) -> None:
    """Coalesce NULLs then force NOT NULL DEFAULT (MySQL)."""
    op.execute(
        sa.text(
            f"UPDATE `{table}` SET `{column}` = :d WHERE `{column}` IS NULL"
        ).bindparams(d=default)
    )
    if _mysql():
        op.execute(
            sa.text(
                f"ALTER TABLE `{table}` MODIFY COLUMN `{column}` "
                f"TINYINT(1) NOT NULL DEFAULT {int(default)}"
            )
        )
    else:
        op.alter_column(
            table,
            column,
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.text(str(int(default))),
        )


def _fk_names(table: str) -> set[str]:
    return {fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)}


def _index_names(table: str) -> set[str]:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def _uq_names(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    names: set[str] = set()
    for uq in inspector.get_unique_constraints(table):
        if uq.get("name"):
            names.add(uq["name"])
    for ix in inspector.get_indexes(table):
        if ix.get("unique") and ix.get("name"):
            names.add(ix["name"])
    return names


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- 1) NOT NULL flags ---
    _modify_bool("users", "is_2fa_enabled", 0)
    op.execute(
        sa.text(
            "UPDATE users SET failed_login_attempts = 0 "
            "WHERE failed_login_attempts IS NULL"
        )
    )
    if _mysql():
        op.execute(
            sa.text(
                "ALTER TABLE users MODIFY COLUMN failed_login_attempts "
                "INT NOT NULL DEFAULT 0"
            )
        )
    else:
        op.alter_column(
            "users",
            "failed_login_attempts",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )

    for table, col, default in (
        ("refresh_tokens", "is_revoked", 0),
        ("user_sessions", "is_active", 1),
        ("api_keys", "is_active", 1),
        ("user_groups", "is_active", 1),
        ("user_group_memberships", "is_active", 1),
        ("user_permissions", "is_active", 1),
        ("login_attempts", "success", 0),
    ):
        if table in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns(table)}
            if col in cols:
                _modify_bool(table, col, default)

    # --- 2) user_permissions → permission_id FK ---
    up_cols = {c["name"] for c in inspector.get_columns("user_permissions")}
    if "permission_id" not in up_cols:
        # Ensure catalog rows exist for any free-text grants
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (name, description, category)
                SELECT DISTINCT up.permission_name, up.permission_name, 'migrated'
                FROM user_permissions up
                LEFT JOIN permissions p ON p.name = up.permission_name
                WHERE p.id IS NULL AND up.permission_name IS NOT NULL
                  AND up.permission_name <> ''
                """
            )
        )
        op.add_column(
            "user_permissions",
            sa.Column("permission_id", sa.Integer(), nullable=True),
        )
        op.execute(
            sa.text(
                """
                UPDATE user_permissions up
                INNER JOIN permissions p ON p.name = up.permission_name
                SET up.permission_id = p.id
                """
            )
        )
        op.execute(sa.text("DELETE FROM user_permissions WHERE permission_id IS NULL"))
        if _mysql():
            op.execute(
                sa.text(
                    "ALTER TABLE user_permissions "
                    "MODIFY COLUMN permission_id INT NOT NULL"
                )
            )
        else:
            op.alter_column(
                "user_permissions",
                "permission_id",
                existing_type=sa.Integer(),
                nullable=False,
            )

        if "uq_user_permission_grant" in _uq_names("user_permissions"):
            op.drop_constraint(
                "uq_user_permission_grant", "user_permissions", type_="unique"
            )

        op.create_foreign_key(
            "fk_user_permissions_permission_id",
            "user_permissions",
            "permissions",
            ["permission_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(
            "ix_user_permissions_permission_id",
            "user_permissions",
            ["permission_id"],
        )
        op.create_unique_constraint(
            "uq_user_permission_grant",
            "user_permissions",
            [
                "user_id",
                "organization_id",
                "permission_id",
                "resource_type",
                "resource_id",
            ],
        )

    # --- 3) Invites: ENUM role + one pending per org+email ---
    if "user_invitations" in inspector.get_table_names():
        if _mysql():
            op.execute(
                sa.text(
                    """
                    UPDATE user_invitations
                    SET role = 'user'
                    WHERE role IS NULL
                       OR role NOT IN (
                         'user', 'admin', 'organization_admin', 'super_admin'
                       )
                    """
                )
            )
            op.execute(
                sa.text(
                    """
                    ALTER TABLE user_invitations
                    MODIFY COLUMN role ENUM(
                      'user', 'admin', 'organization_admin', 'super_admin'
                    ) NOT NULL DEFAULT 'user'
                    """
                )
            )
            # Collapse duplicate pending invites: keep newest id
            op.execute(
                sa.text(
                    """
                    UPDATE user_invitations ui
                    INNER JOIN (
                        SELECT organization_id, email, MAX(id) AS keep_id
                        FROM user_invitations
                        WHERE accepted_at IS NULL AND revoked_at IS NULL
                        GROUP BY organization_id, email
                        HAVING COUNT(*) > 1
                    ) d ON ui.organization_id = d.organization_id
                       AND ui.email = d.email
                       AND ui.accepted_at IS NULL
                       AND ui.revoked_at IS NULL
                       AND ui.id <> d.keep_id
                    SET ui.revoked_at = CURRENT_TIMESTAMP
                    """
                )
            )
            if "uq_inv_one_pending_org_email" not in _index_names("user_invitations"):
                op.execute(
                    sa.text(
                        """
                        CREATE UNIQUE INDEX uq_inv_one_pending_org_email
                        ON user_invitations (
                          (CASE WHEN accepted_at IS NULL AND revoked_at IS NULL
                                THEN organization_id END),
                          (CASE WHEN accepted_at IS NULL AND revoked_at IS NULL
                                THEN email END)
                        )
                        """
                    )
                )

    # --- 4) Consent: retain evidence on user hard-delete ---
    if "consent_records" in inspector.get_table_names():
        consent_cols = {c["name"] for c in inspector.get_columns("consent_records")}
        if "policy_version" not in consent_cols:
            op.add_column(
                "consent_records",
                sa.Column("policy_version", sa.String(length=50), nullable=True),
            )

        fks = _fk_names("consent_records")
        for name in ("consent_records_ibfk_1", "fk_consent_records_user_id"):
            if name in fks:
                op.drop_constraint(name, "consent_records", type_="foreignkey")

        if _mysql():
            op.execute(
                sa.text(
                    "ALTER TABLE consent_records "
                    "MODIFY COLUMN user_id INT NULL"
                )
            )
        else:
            op.alter_column(
                "consent_records",
                "user_id",
                existing_type=sa.Integer(),
                nullable=True,
            )

        remaining = _fk_names("consent_records")
        if "fk_consent_records_user_id" not in remaining:
            op.create_foreign_key(
                "fk_consent_records_user_id",
                "consent_records",
                "users",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "consent_records" in inspector.get_table_names():
        fks = _fk_names("consent_records")
        if "fk_consent_records_user_id" in fks:
            op.drop_constraint(
                "fk_consent_records_user_id", "consent_records", type_="foreignkey"
            )
        if _mysql():
            op.execute(
                sa.text(
                    "ALTER TABLE consent_records "
                    "MODIFY COLUMN user_id INT NOT NULL"
                )
            )
        op.create_foreign_key(
            "consent_records_ibfk_1",
            "consent_records",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        cols = {c["name"] for c in inspector.get_columns("consent_records")}
        if "policy_version" in cols:
            op.drop_column("consent_records", "policy_version")

    if "user_invitations" in inspector.get_table_names():
        if "uq_inv_one_pending_org_email" in _index_names("user_invitations"):
            op.drop_index(
                "uq_inv_one_pending_org_email", table_name="user_invitations"
            )
        if _mysql():
            op.execute(
                sa.text(
                    "ALTER TABLE user_invitations "
                    "MODIFY COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
                )
            )

    up_cols = {c["name"] for c in inspector.get_columns("user_permissions")}
    if "permission_id" in up_cols:
        if "uq_user_permission_grant" in _uq_names("user_permissions"):
            op.drop_constraint(
                "uq_user_permission_grant", "user_permissions", type_="unique"
            )
        if "fk_user_permissions_permission_id" in _fk_names("user_permissions"):
            op.drop_constraint(
                "fk_user_permissions_permission_id",
                "user_permissions",
                type_="foreignkey",
            )
        if "ix_user_permissions_permission_id" in _index_names("user_permissions"):
            op.drop_index(
                "ix_user_permissions_permission_id",
                table_name="user_permissions",
            )
        op.drop_column("user_permissions", "permission_id")
        op.create_unique_constraint(
            "uq_user_permission_grant",
            "user_permissions",
            ["user_id", "permission_name", "resource_type", "resource_id"],
        )
