"""Role rules as data: the single place that knows what a role may do structurally.

Every system role is a row in ``roles`` with:
  * ``level``          rank; higher levels manage strictly lower ones
  * ``is_platform``    cross-tenant role (sees/manages every organization; hidden
                       from tenant users) — e.g. the platform super admin
  * ``can_view_peers`` may also see users holding the same role (org owners)

Business code asks questions (``is_platform_role``, ``is_manager_role``,
``assignable_roles``, ``visible_role_names``) instead of comparing role names, so a
product can add roles (e.g. ``teacher`` at level 15) with a database row and no code.

Rules are read from the database and cached per process for ``_TTL_SECONDS``.
``DEFAULT_SYSTEM_ROLES`` seeds new databases and is the fallback if the database is
unreachable (e.g. pure unit tests).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class RoleInfo:
    name: str
    level: int
    is_platform: bool = False
    can_view_peers: bool = False
    description: str = ""


DEFAULT_SYSTEM_ROLES: tuple[RoleInfo, ...] = (
    RoleInfo("user", 10, description="Standard end user"),
    RoleInfo("admin", 20, description="Organization staff administrator"),
    RoleInfo(
        "organization_admin", 30, can_view_peers=True,
        description="Organization administrator",
    ),
    RoleInfo(
        "super_admin", 100, is_platform=True,
        description="Platform super administrator",
    ),
)
DEFAULT_ROLE_NAME = "user"  # assigned to new users when no role is given

_TTL_SECONDS = 60.0
_lock = threading.Lock()
_cache: Optional[Dict[str, RoleInfo]] = None
_cache_expires = 0.0


def _load_from_db() -> Dict[str, RoleInfo]:
    from models.rbac_model import Role
    from utils.database import SessionLocal

    with SessionLocal() as db:
        rows = (
            db.query(Role)
            .filter(Role.is_system.is_(True), Role.org_scope_key == 0)
            .all()
        )
        return {
            r.name: RoleInfo(
                r.name,
                int(r.level or 0),
                bool(r.is_platform),
                bool(r.can_view_peers),
                r.description or "",
            )
            for r in rows
        }


def system_roles() -> Dict[str, RoleInfo]:
    """name -> RoleInfo for all system roles (cached)."""
    global _cache, _cache_expires
    now = time.monotonic()
    if _cache is not None and now < _cache_expires:
        return _cache
    with _lock:
        if _cache is not None and now < _cache_expires:
            return _cache
        try:
            loaded = _load_from_db()
        except Exception:  # noqa: BLE001 - DB down / no schema: use seed defaults
            loaded = {}
        _cache = loaded or {r.name: r for r in DEFAULT_SYSTEM_ROLES}
        _cache_expires = now + _TTL_SECONDS
        return _cache


def invalidate_cache() -> None:
    """Call after changing role rows so the next lookup reloads them."""
    global _cache_expires
    _cache_expires = 0.0


def role_info(name: Optional[str]) -> Optional[RoleInfo]:
    return system_roles().get(name or "")


def level_of(name: Optional[str]) -> int:
    info = role_info(name)
    return info.level if info else 0


def is_platform_role(name: Optional[str]) -> bool:
    info = role_info(name)
    return bool(info and info.is_platform)


def base_level() -> int:
    """Level of the lowest system role (the plain end user)."""
    roles = system_roles()
    return min((r.level for r in roles.values()), default=0)


def is_base_role(name: Optional[str]) -> bool:
    """True for the lowest-ranked role (plain end user)."""
    info = role_info(name)
    return info is not None and info.level == base_level()


def is_manager_role(name: Optional[str]) -> bool:
    """Ranks above the base role: may manage users / be a manager / see staff tools."""
    info = role_info(name)
    return info is not None and info.level > base_level()


def assignable_roles(creator: Optional[str]) -> List[str]:
    """Roles a holder of ``creator`` may grant: strictly lower level."""
    lvl = level_of(creator)
    return [
        r.name
        for r in sorted(system_roles().values(), key=lambda r: -r.level)
        if r.level < lvl
    ]


def visible_role_names(viewer: Optional[str]) -> Optional[List[str]]:
    """Roles a viewer may see inside their organization; None = everything (platform)."""
    info = role_info(viewer)
    if info is None:
        return []
    if info.is_platform:
        return None
    return [
        r.name
        for r in sorted(system_roles().values(), key=lambda r: -r.level)
        if not r.is_platform
        and (r.level < info.level or (info.can_view_peers and r.level == info.level))
    ]


def highest(names) -> Optional[str]:
    """The highest-level role name among ``names`` (unknown names rank lowest)."""
    names = [n for n in names if n]
    return max(names, key=level_of) if names else None
