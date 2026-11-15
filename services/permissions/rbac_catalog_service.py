"""RBAC catalog: system roles, permissions and user role assignments.

Roles are stored only in ``user_roles`` (``users.role`` was dropped); role rules
(level / platform / peers) live on ``roles`` and are read via
``services.permissions.role_catalog``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from sqlalchemy import or_

from sqlalchemy.orm import Session

from models.rbac_model import Permission, Role, RolePermission, UserRole
from services.permissions.api_key_service import ApiKeyService
from services.permissions.user_permission_service import UserPermissionService
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger
from services.permissions.role_catalog import (
    DEFAULT_ROLE_NAME,
    DEFAULT_SYSTEM_ROLES,
    highest,
    invalidate_cache,
)

# Seed defaults (runtime rules come from the roles table via role_catalog).
SYSTEM_ROLE_NAMES = tuple(r.name for r in DEFAULT_SYSTEM_ROLES)
SYSTEM_ROLE_DESCRIPTIONS = {r.name: r.description for r in DEFAULT_SYSTEM_ROLES}


def _category_for_permission(name: str) -> str:
    if ":" not in name:
        return "other"
    return name.split(":", 1)[0]


def _default_role_permission_names(role_name: str) -> Set[str]:
    """Seed permissions for a default system role, derived from its rules."""
    all_names = set(UserPermissionService.STANDARD_PERMISSIONS.keys())
    info = next((r for r in DEFAULT_SYSTEM_ROLES if r.name == role_name), None)
    if info is not None and info.is_platform:
        return all_names
    base = min(r.level for r in DEFAULT_SYSTEM_ROLES)
    if info is not None and info.level > base:
        return {n for n in all_names if not n.startswith("system:")}
    return {"users:read", "sessions:read", "groups:read", "organizations:read"}


class RbacCatalogService:
    """Read/write helpers for permissions / roles / user_roles tables."""

    @staticmethod
    def get_effective_system_role(
        db: Session,
        user_id: int,
        fallback: str = DEFAULT_ROLE_NAME,
    ) -> str:
        """Highest-level system role assigned in ``user_roles`` (else ``fallback``)."""
        names = [
            row[0]
            for row in (
                db.query(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .filter(
                    UserRole.user_id == user_id,
                    Role.is_system.is_(True),
                    Role.org_scope_key == 0,
                    UserRole.unit_id.is_(None),
                )
                .all()
            )
        ]
        return highest(names) or fallback or DEFAULT_ROLE_NAME

    @staticmethod
    def apply_effective_role(db: Session, user) -> str:
        """Kept for callers: ``user.role`` is already derived from ``user_roles``."""
        return user.role

    @staticmethod
    def user_has_role_permission(
        db: Session,
        user_id: int,
        permission_name: str,
        *,
        organization_id: Optional[int] = None,
    ) -> bool:
        """True if any of the user's roles map to this catalog permission.

        Platform roles hold every permission, including ones added after seeding.
        """
        platform = (
            db.query(Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(
                UserRole.user_id == user_id,
                Role.is_platform.is_(True),
                UserRole.unit_id.is_(None),
            )
            .first()
        )
        if platform is not None:
            return True
        row = (
            db.query(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(
                UserRole.user_id == user_id,
                Permission.name == permission_name,
                UserRole.unit_id.is_(None),  # unit grants: see unit_access
                # role assignments apply only in their org (None = everywhere)
                True
                if organization_id is None
                else or_(
                    UserRole.organization_id == organization_id,
                    UserRole.organization_id.is_(None),
                ),
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
        """Set the user's system role (stored only in ``user_roles``).

        Org-scoped custom roles are untouched. Returns False for an unknown user/role.
        """
        from models.user_model import User

        user = db.get(User, user_id)
        if user is None:
            return False
        try:
            user.role = role_name
            user.__dict__["_pending_granted_by"] = granted_by
            db.flush()
        except ValueError as exc:
            user.__dict__.pop("_pending_system_role", None)
            user.__dict__.pop("_pending_granted_by", None)
            auth_logger.warning(
                f"Cannot assign system role '{role_name}': {exc}",
                user_id=user_id,
                event_type="rbac_sync_role_missing",
            )
            return False
        if commit:
            db.commit()
        return True

    @staticmethod
    def find_role_drifts(db: Session) -> List[Dict[str, object]]:
        """Active users with no system role in ``user_roles`` (invariant check)."""
        from models.user_model import User

        has_system_role = (
            db.query(UserRole.id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(
                UserRole.user_id == User.id,
                Role.is_system.is_(True),
                Role.org_scope_key == 0,
                UserRole.unit_id.is_(None),
            )
            .exists()
        )
        users = (
            db.query(User.id, User.username)
            .filter(User.deleted_at.is_(None), ~has_system_role)
            .all()
        )
        return [
            {"user_id": uid, "username": name, "has_system_user_role": False}
            for uid, name in users
        ]

    @staticmethod
    def repair_role_drifts(db: Session, *, commit: bool = True) -> int:
        """Give every user without a system role the default role. Returns count."""
        repaired = sum(
            RbacCatalogService.sync_user_system_role(
                db, row["user_id"], DEFAULT_ROLE_NAME, commit=False
            )
            for row in RbacCatalogService.find_role_drifts(db)
        )
        if commit and repaired:
            db.commit()
        return repaired

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
        for info in DEFAULT_SYSTEM_ROLES:
            role_name = info.name
            role = RbacCatalogService.get_system_role(db, role_name)
            if role is None:
                role = Role(
                    name=role_name,
                    organization_id=None,
                    org_scope_key=0,
                    is_system=True,
                    level=info.level,
                    is_platform=info.is_platform,
                    can_view_peers=info.can_view_peers,
                    description=info.description,
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
        invalidate_cache()
        return {"permissions_created": created_perms, "roles_created": created_roles}
