"""RBAC catalog + dual-write helpers for normalized roles/permissions."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from models.rbac_model import Permission, Role, RolePermission, UserRole
from services.permissions.api_key_service import ApiKeyService
from services.permissions.user_permission_service import UserPermissionService
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger

SYSTEM_ROLE_NAMES = ("user", "admin", "organization_admin", "super_admin")

SYSTEM_ROLE_RANK = {
    "user": 1,
    "admin": 2,
    "organization_admin": 3,
    "super_admin": 4,
}

SYSTEM_ROLE_DESCRIPTIONS = {
    "user": "Standard end user",
    "admin": "Organization staff administrator",
    "organization_admin": "Organization administrator",
    "super_admin": "Platform super administrator",
}


def _category_for_permission(name: str) -> str:
    if ":" not in name:
        return "other"
    return name.split(":", 1)[0]


def _default_role_permission_names(role_name: str) -> Set[str]:
    all_names = set(UserPermissionService.STANDARD_PERMISSIONS.keys())
    if role_name == "super_admin":
        return all_names
    if role_name in ("admin", "organization_admin"):
        return {n for n in all_names if not n.startswith("system:")}
    # end user
    return {
        "users:read",
        "sessions:read",
        "groups:read",
        "organizations:read",
    }


class RbacCatalogService:
    """Read/write helpers for permissions / roles / user_roles tables."""

    @staticmethod
    def get_effective_system_role(
        db: Session,
        user_id: int,
        fallback: str = "user",
    ) -> str:
        """Highest-ranked system role from `user_roles`, else `fallback` (`users.role`)."""
        names = [
            row[0]
            for row in (
                db.query(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .filter(
                    UserRole.user_id == user_id,
                    Role.is_system.is_(True),
                    Role.org_scope_key == 0,
                )
                .all()
            )
        ]
        if not names:
            return fallback or "user"
        return max(names, key=lambda n: SYSTEM_ROLE_RANK.get(n, 0))

    @staticmethod
    def apply_effective_role(db: Session, user) -> str:
        """
        Align `user.role` with catalog without dirtying the ORM session.

        Uses SQLAlchemy `set_committed_value` so accidental commits do not
        rewrite `users.role` on every authenticated request.
        """
        from sqlalchemy.orm.attributes import set_committed_value

        fallback = getattr(user, "role", None) or "user"
        effective = RbacCatalogService.get_effective_system_role(
            db, user.id, fallback
        )
        if effective != user.role:
            set_committed_value(user, "role", effective)
        return effective

    @staticmethod
    def user_has_role_permission(
        db: Session, user_id: int, permission_name: str
    ) -> bool:
        """True if any of the user's roles map to this catalog permission."""
        row = (
            db.query(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(
                UserRole.user_id == user_id,
                Permission.name == permission_name,
            )
            .first()
        )
        return row is not None

    @staticmethod
    def list_permission_names(db: Session) -> Dict[str, str]:
        """Prefer DB catalog; fall back to in-code STANDARD_PERMISSIONS."""
        rows = db.query(Permission).order_by(Permission.name).all()
        if rows:
            return {r.name: (r.description or "") for r in rows if r.category != "api_key"}
        return UserPermissionService.STANDARD_PERMISSIONS.copy()

    @staticmethod
    def list_api_key_permission_names(db: Session) -> Dict[str, str]:
        rows = (
            db.query(Permission)
            .filter(Permission.category == "api_key")
            .order_by(Permission.name)
            .all()
        )
        if rows:
            return {r.name: (r.description or "") for r in rows}
        return ApiKeyService.STANDARD_API_PERMISSIONS.copy()

    @staticmethod
    def permission_exists(db: Session, name: str) -> bool:
        if db.query(Permission.id).filter(Permission.name == name).first():
            return True
        return name in UserPermissionService.STANDARD_PERMISSIONS

    @staticmethod
    def get_system_role(db: Session, role_name: str) -> Optional[Role]:
        return (
            db.query(Role)
            .filter(
                Role.name == role_name,
                Role.is_system.is_(True),
                Role.org_scope_key == 0,
            )
            .first()
        )

    @staticmethod
    def sync_user_system_role(
        db: Session,
        user_id: int,
        role_name: str,
        granted_by: Optional[int] = None,
        *,
        commit: bool = False,
    ) -> bool:
        """
        Replace the user's system-role membership to match users.role.

        Does not touch org-scoped custom roles (org_scope_key != 0).
        """
        role = RbacCatalogService.get_system_role(db, role_name)
        if role is None:
            auth_logger.warning(
                f"System role '{role_name}' missing from roles table; skip user_roles sync",
                user_id=user_id,
                event_type="rbac_sync_role_missing",
            )
            return False

        existing = (
            db.query(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .filter(UserRole.user_id == user_id, Role.is_system.is_(True))
            .all()
        )
        for row in existing:
            if row.role_id != role.id:
                db.delete(row)

        still = (
            db.query(UserRole)
            .filter(UserRole.user_id == user_id, UserRole.role_id == role.id)
            .first()
        )
        if still is None:
            db.add(
                UserRole(
                    user_id=user_id,
                    role_id=role.id,
                    granted_by=granted_by,
                    granted_at=utc_now(),
                )
            )
        if commit:
            db.commit()
        return True

    @staticmethod
    def permission_names_for_system_role(db: Session, role_name: str) -> List[str]:
        role = RbacCatalogService.get_system_role(db, role_name)
        if role is None:
            return sorted(_default_role_permission_names(role_name))
        names = (
            db.query(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == role.id)
            .order_by(Permission.name)
            .all()
        )
        return [n[0] for n in names]

    @staticmethod
    def ensure_seed_data(db: Session) -> Dict[str, int]:
        """
        Idempotent seed of catalog + system role_permissions.
        Used by migration and optional runtime repair.
        """
        created_perms = 0
        catalogs = [
            (UserPermissionService.STANDARD_PERMISSIONS, None),
            (ApiKeyService.STANDARD_API_PERMISSIONS, "api_key"),
        ]
        for catalog, forced_category in catalogs:
            for name, description in catalog.items():
                existing = (
                    db.query(Permission).filter(Permission.name == name).first()
                )
                if existing:
                    continue
                category = forced_category or _category_for_permission(name)
                db.add(
                    Permission(
                        name=name,
                        description=description,
                        category=category,
                    )
                )
                created_perms += 1
        db.flush()

        created_roles = 0
        for role_name in SYSTEM_ROLE_NAMES:
            role = RbacCatalogService.get_system_role(db, role_name)
            if role is None:
                role = Role(
                    name=role_name,
                    organization_id=None,
                    org_scope_key=0,
                    is_system=True,
                    description=SYSTEM_ROLE_DESCRIPTIONS.get(role_name),
                )
                db.add(role)
                db.flush()
                created_roles += 1

            wanted = _default_role_permission_names(role_name)
            existing_ids = {
                rp.permission_id
                for rp in db.query(RolePermission)
                .filter(RolePermission.role_id == role.id)
                .all()
            }
            perms = (
                db.query(Permission)
                .filter(
                    Permission.name.in_(wanted),
                    Permission.category != "api_key",
                )
                .all()
            )
            for perm in perms:
                if perm.id not in existing_ids:
                    db.add(
                        RolePermission(role_id=role.id, permission_id=perm.id)
                    )

        db.flush()
        return {"permissions_created": created_perms, "roles_created": created_roles}
