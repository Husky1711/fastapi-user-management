"""Organization units: tree management, placing people in units, unit-scoped roles."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.identity import User
from models.rbac_model import Role, UserRole
from models.units import OrgUnit, OrgUnitMember
from utils.datetime_utc import utc_now

MAX_DEPTH = 10


class UnitError(ValueError):
    """Validation failure; ``status`` is the HTTP status to report."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class UnitService:
    # --- tree -----------------------------------------------------------------

    @staticmethod
    def get_unit(db: Session, organization_id: int, unit_id: int) -> OrgUnit:
        unit = (
            db.query(OrgUnit)
            .filter(OrgUnit.id == unit_id, OrgUnit.organization_id == organization_id)
            .first()
        )
        if unit is None:
            raise UnitError("Unit not found", 404)
        return unit

    @staticmethod
    def list_tree(db: Session, organization_id: int) -> List[Dict[str, Any]]:
        counts = dict(
            db.query(OrgUnitMember.unit_id, func.count(OrgUnitMember.id))
            .join(OrgUnit, OrgUnit.id == OrgUnitMember.unit_id)
            .filter(OrgUnit.organization_id == organization_id)
            .group_by(OrgUnitMember.unit_id)
            .all()
        )
        units = (
            db.query(OrgUnit)
            .filter(OrgUnit.organization_id == organization_id)
            .order_by(OrgUnit.path)
            .all()
        )
        return [UnitService.serialize(u, counts.get(u.id, 0)) for u in units]

    @staticmethod
    def serialize(unit: OrgUnit, member_count: Optional[int] = None) -> Dict[str, Any]:
        row = {
            "id": unit.id,
            "parent_id": unit.parent_id,
            "unit_type": unit.unit_type,
            "name": unit.name,
            "depth": unit.depth,
            "path": unit.path,
        }
        if member_count is not None:
            row["member_count"] = member_count
        return row

    @staticmethod
    def create_unit(
        db: Session,
        organization_id: int,
        name: str,
        unit_type: str,
        parent_id: Optional[int] = None,
    ) -> OrgUnit:
        name, unit_type = (name or "").strip(), (unit_type or "").strip().lower()
        if not name or not unit_type:
            raise UnitError("name and unit_type are required")
        parent = None
        if parent_id is not None:
            parent = UnitService.get_unit(db, organization_id, parent_id)
            if parent.depth + 1 >= MAX_DEPTH:
                raise UnitError(f"Units can be nested at most {MAX_DEPTH} levels")
        dup = (
            db.query(OrgUnit.id)
            .filter(
                OrgUnit.organization_id == organization_id,
                OrgUnit.parent_id.is_(None) if parent is None else OrgUnit.parent_id == parent.id,
                func.lower(OrgUnit.name) == name.lower(),
            )
            .first()
        )
        if dup:
            raise UnitError("A unit with this name already exists here", 409)
        unit = OrgUnit(
            organization_id=organization_id,
            parent_id=parent.id if parent else None,
            unit_type=unit_type,
            name=name,
            depth=(parent.depth + 1) if parent else 0,
            path="",
        )
        db.add(unit)
        db.flush()  # id needed for the path
        unit.path = f"{parent.path if parent else '/'}{unit.id}/"
        return unit

    @staticmethod
    def update_unit(db: Session, unit: OrgUnit, name: Optional[str], unit_type: Optional[str]) -> OrgUnit:
        if name is not None:
            name = name.strip()
            if not name:
                raise UnitError("name cannot be empty")
            unit.name = name
        if unit_type is not None:
            unit_type = unit_type.strip().lower()
            if not unit_type:
                raise UnitError("unit_type cannot be empty")
            unit.unit_type = unit_type
        return unit

    @staticmethod
    def delete_unit(db: Session, unit: OrgUnit) -> None:
        if db.query(OrgUnit.id).filter(OrgUnit.parent_id == unit.id).first():
            raise UnitError("Delete or move the child units first", 409)
        if db.query(OrgUnitMember.id).filter(OrgUnitMember.unit_id == unit.id).first():
            raise UnitError("Remove the people placed in this unit first", 409)
        db.query(UserRole).filter(UserRole.unit_id == unit.id).delete(synchronize_session=False)
        db.delete(unit)

    # --- people in units --------------------------------------------------------

    @staticmethod
    def members(db: Session, unit: OrgUnit, include_subtree: bool = False) -> List[User]:
        q = (
            db.query(User)
            .join(OrgUnitMember, OrgUnitMember.user_id == User.id)
            .join(OrgUnit, OrgUnit.id == OrgUnitMember.unit_id)
            .filter(User.deleted_at.is_(None), OrgUnit.organization_id == unit.organization_id)
        )
        q = q.filter(OrgUnit.path.startswith(unit.path)) if include_subtree else q.filter(OrgUnit.id == unit.id)
        return q.distinct().order_by(User.username).all()

    @staticmethod
    def add_member(db: Session, unit: OrgUnit, user: User) -> bool:
        if unit.organization_id not in user.member_org_ids():
            raise UnitError("User is not a member of this organization", 404)
        exists_ = (
            db.query(OrgUnitMember.id)
            .filter(OrgUnitMember.unit_id == unit.id, OrgUnitMember.user_id == user.id)
            .first()
        )
        if exists_:
            return False
        db.add(OrgUnitMember(unit_id=unit.id, user_id=user.id))
        return True

    @staticmethod
    def remove_member(db: Session, unit: OrgUnit, user: User) -> None:
        n = (
            db.query(OrgUnitMember)
            .filter(OrgUnitMember.unit_id == unit.id, OrgUnitMember.user_id == user.id)
            .delete(synchronize_session=False)
        )
        if not n:
            raise UnitError("User is not placed in this unit", 404)

    # --- roles on units ---------------------------------------------------------

    @staticmethod
    def role_grants(db: Session, unit: OrgUnit) -> List[Dict[str, Any]]:
        rows = (
            db.query(UserRole, Role.name, User.username)
            .join(Role, Role.id == UserRole.role_id)
            .join(User, User.id == UserRole.user_id)
            .filter(UserRole.unit_id == unit.id)
            .order_by(User.username)
            .all()
        )
        return [
            {"user_id": ur.user_id, "username": username, "role": role, "unit_id": unit.id}
            for ur, role, username in rows
        ]

    @staticmethod
    def grant_role(
        db: Session, unit: OrgUnit, user: User, role_name: str, granted_by: Optional[int]
    ) -> bool:
        from models.role_events import _system_role

        if unit.organization_id not in user.member_org_ids():
            raise UnitError("User is not a member of this organization", 404)
        role = _system_role(db, role_name)
        if role.is_platform:
            raise UnitError("Platform roles cannot be granted on a unit", 403)
        existing = (
            db.query(UserRole.id)
            .filter(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
                UserRole.unit_id == unit.id,
            )
            .first()
        )
        if existing:
            return False
        db.add(
            UserRole(
                user_id=user.id,
                role_id=role.id,
                organization_id=unit.organization_id,
                scope_key=unit.organization_id,
                unit_id=unit.id,
                unit_key=unit.id,
                granted_by=granted_by,
                granted_at=utc_now(),
            )
        )
        return True

    @staticmethod
    def revoke_role(db: Session, unit: OrgUnit, user: User, role_name: str) -> None:
        n = (
            db.query(UserRole)
            .filter(
                UserRole.user_id == user.id,
                UserRole.unit_id == unit.id,
                UserRole.role_id.in_(db.query(Role.id).filter(Role.name == role_name)),
            )
            .delete(synchronize_session=False)
        )
        if not n:
            raise UnitError("No such role on this unit", 404)
