from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.user_model import Organization, User
from utils.loggers import auth_logger


class OrganizationService:
    @staticmethod
    def serialize_organization(db: Session, org: Organization) -> Dict[str, Any]:
        total_users = db.query(User).filter(User.organization_id == org.id).count()
        active_users = (
            db.query(User)
            .filter(User.organization_id == org.id, User.status == "active")
            .count()
        )
        return {
            "id": org.id,
            "name": org.name,
            "description": org.description,
            "status": org.status,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
            "total_users": total_users,
            "active_users": active_users,
        }

    @staticmethod
    def list_organizations(db: Session) -> List[Dict[str, Any]]:
        orgs = db.query(Organization).order_by(Organization.id).all()
        return [OrganizationService.serialize_organization(db, org) for org in orgs]

    @staticmethod
    def get_organization(db: Session, organization_id: int) -> Optional[Dict[str, Any]]:
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if org is None:
            return None
        return OrganizationService.serialize_organization(db, org)

    @staticmethod
    def create_organization(
        db: Session,
        name: str,
        description: Optional[str] = None,
        status: str = "active",
    ) -> Dict[str, Any]:
        existing = db.query(Organization).filter(Organization.name == name).first()
        if existing:
            return {"success": False, "error": f"Organization '{name}' already exists"}

        org = Organization(
            name=name,
            description=description,
            status=status,
        )
        db.add(org)
        db.commit()
        db.refresh(org)

        auth_logger.info(
            f"Organization created: {org.name}",
            organization_id=org.id,
            event_type="organization_created",
        )

        return {
            "success": True,
            "organization": OrganizationService.serialize_organization(db, org),
            "message": f"Organization '{org.name}' created successfully",
        }

    @staticmethod
    def update_organization(
        db: Session,
        organization_id: int,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if org is None:
            return {"success": False, "error": "Organization not found"}

        if "name" in updates and updates["name"] != org.name:
            existing = (
                db.query(Organization)
                .filter(Organization.name == updates["name"], Organization.id != organization_id)
                .first()
            )
            if existing:
                return {
                    "success": False,
                    "error": f"Organization '{updates['name']}' already exists",
                }
            org.name = updates["name"]

        if "description" in updates:
            org.description = updates["description"]

        if "status" in updates:
            org.status = updates["status"]

        org.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(org)

        auth_logger.info(
            f"Organization updated: {org.name}",
            organization_id=org.id,
            updates=list(updates.keys()),
            event_type="organization_updated",
        )

        return {
            "success": True,
            "organization": OrganizationService.serialize_organization(db, org),
            "message": f"Organization '{org.name}' updated successfully",
        }
