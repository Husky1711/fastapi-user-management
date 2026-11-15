"""Sector templates: the per-sector data that makes one backend fit many products.

A template (``config/sector_templates/<key>.json``) defines, for organizations that
use it:

* ``terms`` / ``role_labels`` — UI wording ("Student", "Ward", "Principal"...);
* ``unit_types`` — allowed unit types and which may sit under which;
* ``roles`` — extra roles (name, level, permissions; ``perm@own`` limits a permission
  to related people, ``*`` = every non-system permission);
* ``relations`` — relation keys used by "own" scopes (teaches, attends...).

Nothing here is sector-specific code: adding a sector is adding a JSON file.
Organizations without a template get ``generic`` *wording* but no restrictions
(free-text unit types, any catalog role, any relation key) — rules are enforced
only once an organization chooses a template. Per-org wording overrides live in
``organizations.vocabulary_overrides``.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "config" / "sector_templates"
DEFAULT_TEMPLATE = "generic"


class TemplateError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# --- loading --------------------------------------------------------------------

_templates: Optional[Dict[str, Dict[str, Any]]] = None
_lock = threading.Lock()


def _validate(t: Dict[str, Any], source: str) -> Dict[str, Any]:
    for field in ("key", "name", "terms", "unit_types", "roles"):
        if field not in t:
            raise TemplateError(f"{source}: missing '{field}'")
    keys = {u["key"] for u in t["unit_types"]}
    for u in t["unit_types"]:
        for parent in u.get("parents", [None]):
            if parent is not None and parent not in keys:
                raise TemplateError(f"{source}: unit type '{u['key']}' has unknown parent '{parent}'")
    for r in t["roles"]:
        if not isinstance(r.get("level"), int) or not r.get("name"):
            raise TemplateError(f"{source}: every role needs a name and an integer level")
    t.setdefault("role_labels", {})
    t.setdefault("relations", [])
    t.setdefault("description", "")
    return t


def templates() -> Dict[str, Dict[str, Any]]:
    global _templates
    if _templates is None:
        with _lock:
            if _templates is None:
                loaded = {}
                for f in sorted(TEMPLATE_DIR.glob("*.json")):
                    t = _validate(json.loads(f.read_text(encoding="utf-8")), f.name)
                    loaded[t["key"]] = t
                _templates = loaded
    return _templates


def get_template(key: Optional[str]) -> Dict[str, Any]:
    all_t = templates()
    t = all_t.get(key or DEFAULT_TEMPLATE)
    if t is None:
        raise TemplateError(f"Unknown sector template '{key}'", 404)
    return t


def list_templates() -> List[Dict[str, Any]]:
    return [
        {
            "key": t["key"],
            "name": t["name"],
            "description": t["description"],
            "unit_types": [u["label"] for u in t["unit_types"]],
            "roles": [r.get("label", r["name"]) for r in t["roles"]],
        }
        for t in templates().values()
    ]


# --- per organization -------------------------------------------------------------

def chosen_template_key(organization_id: Optional[int]) -> Optional[str]:
    """Template the org chose, or None.

    Not cached: it is read only on writes (role grants, unit changes, relations),
    and a cache would let other worker processes act on a stale template.
    """
    if organization_id is None:
        return None
    from models.identity import Organization
    from utils.database import SessionLocal

    try:
        with SessionLocal() as db:
            return (
                db.query(Organization.sector_template)
                .filter(Organization.id == organization_id)
                .scalar()
            )
    except Exception:  # noqa: BLE001 — no DB (unit tests): generic rules
        return None


def chosen_template(organization_id: Optional[int]) -> Optional[Dict[str, Any]]:
    key = chosen_template_key(organization_id)
    return get_template(key) if key else None


def allowed_role_names(organization_id: Optional[int]) -> Optional[Set[str]]:
    """Default system roles plus the org's template roles; None = no restriction."""
    from services.permissions.role_catalog import DEFAULT_SYSTEM_ROLES

    t = chosen_template(organization_id)
    if t is None:
        return None
    return {r.name for r in DEFAULT_SYSTEM_ROLES} | {r["name"] for r in t["roles"]}


def validate_unit_type(organization_id: int, unit_type: str, parent_type: Optional[str]) -> None:
    t = chosen_template(organization_id)
    if t is None:
        return
    spec = next((u for u in t["unit_types"] if u["key"] == unit_type), None)
    if spec is None:
        allowed = ", ".join(u["key"] for u in t["unit_types"])
        raise TemplateError(f"Unit type '{unit_type}' is not used in this organization (allowed: {allowed})")
    if parent_type not in spec.get("parents", [None]):
        where = "at the top level" if parent_type is None else f"under a '{parent_type}'"
        raise TemplateError(f"A '{unit_type}' cannot be placed {where}")


def validate_relation(organization_id: int, relation: str) -> None:
    t = chosen_template(organization_id)
    keys = {r["key"] for r in t["relations"]} if t else set()
    if keys and relation not in keys:
        raise TemplateError(f"Relation '{relation}' is not used in this organization (allowed: {', '.join(sorted(keys))})")


def roles_blocking_switch(db: Session, organization_id: int, key: str) -> Dict[str, int]:
    """Roles held in the org (org-wide or on its units) that template ``key`` does
    not use, with how many people hold each. Empty = safe to switch."""
    from sqlalchemy import func

    from models.rbac_model import Role, UserRole
    from services.permissions.role_catalog import DEFAULT_SYSTEM_ROLES

    t = get_template(key)
    allowed = {r.name for r in DEFAULT_SYSTEM_ROLES} | {r["name"] for r in t["roles"]}
    rows = (
        db.query(Role.name, func.count(func.distinct(UserRole.user_id)))
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.organization_id == organization_id, Role.name.notin_(allowed))
        .group_by(Role.name)
        .all()
    )
    return {name: count for name, count in rows}


def vocabulary(org) -> Dict[str, Any]:
    """Wording for an organization: generic <- template <- org overrides."""
    base = get_template(DEFAULT_TEMPLATE)
    t = get_template(org.sector_template)
    overrides = org.vocabulary_overrides or {}
    terms = {**base["terms"], **t["terms"], **(overrides.get("terms") or {})}
    role_labels = {**base["role_labels"], **t["role_labels"]}
    role_labels.update({r["name"]: r.get("label", r["name"]) for r in t["roles"]})
    role_labels.update(overrides.get("role_labels") or {})
    return {
        "organization_id": org.id,
        "sector": t["key"],
        "sector_name": t["name"],
        "terms": terms,
        "role_labels": role_labels,
        "unit_types": [
            {
                "key": u["key"],
                "label": u["label"],
                "plural": u.get("plural", u["label"] + "s"),
                "parents": u.get("parents", [None]),
            }
            for u in t["unit_types"]
        ],
        "relations": t["relations"],
    }


def apply_template(db: Session, org, key: str) -> Dict[str, Any]:
    """Set the org's template and make sure its roles (+ permissions) exist."""
    from models.rbac_model import Permission, Role, RolePermission
    from services.permissions.role_catalog import invalidate_cache
    from services.permissions.user_permission_service import UserPermissionService

    t = get_template(key)
    created, updated, removed = [], [], []
    all_perms = {p.name: p for p in db.query(Permission).all()}
    perm_names = {p.id: name for name, p in all_perms.items()}
    non_system = [n for n in UserPermissionService.STANDARD_PERMISSIONS if not n.startswith("system:")]
    for spec in t["roles"]:
        role = (
            db.query(Role)
            .filter(Role.name == spec["name"], Role.is_system.is_(True), Role.org_scope_key == 0)
            .one_or_none()
        )
        if role is None:
            role = Role(
                name=spec["name"], organization_id=None, org_scope_key=0, is_system=True,
                level=spec["level"], is_platform=False, can_view_peers=bool(spec.get("can_view_peers")),
                description=spec.get("description", ""),
            )
            db.add(role)
            db.flush()
            created.append(spec["name"])
        elif role.level != spec["level"] or role.is_platform:
            raise TemplateError(
                f"Role '{spec['name']}' already exists with a different level "
                f"({role.level} vs {spec['level']}); rename it in the template", 409
            )
        wanted: Dict[str, str] = {}
        for entry in spec.get("permissions", []):
            if entry == "*":
                wanted.update({n: "all" for n in non_system})
                continue
            name, _, scope = entry.partition("@")
            wanted[name] = scope or "all"
        existing = {rp.permission_id: rp for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id)}
        for name, scope in wanted.items():
            perm = all_perms.get(name)
            if perm is None:
                raise TemplateError(f"Template '{key}': unknown permission '{name}'")
            rp = existing.get(perm.id)
            if rp is None:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id, scope=scope))
            elif rp.scope != scope:
                rp.scope = scope
                updated.append(f"{spec['name']}:{name}")
        # Template roles are defined by their file: drop permissions no longer listed.
        wanted_ids = {all_perms[n].id for n in wanted}
        for perm_id, rp in existing.items():
            if perm_id not in wanted_ids:
                db.delete(rp)
                removed.append(f"{spec['name']}:{perm_names.get(perm_id, perm_id)}")
    org.sector_template = t["key"]
    db.flush()
    invalidate_cache()
    return {
        "organization_id": org.id,
        "sector": t["key"],
        "roles_created": created,
        "scopes_updated": updated,
        "permissions_removed": removed,
    }
