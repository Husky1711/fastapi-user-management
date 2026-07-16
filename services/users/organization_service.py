from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.user_model import Organization, User
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger


class OrganizationService:
    ALLOWED_STATUSES = frozenset({"active", "inactive", "suspended"})

    @staticmethod
    def slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
        return (slug or "org")[:90]

    @staticmethod
    def _unique_slug(db: Session, base: str, exclude_id: Optional[int] = None) -> str:
        candidate = base
        suffix = 2
        while True:
            q = (
                db.query(Organization)
                .filter(Organization.slug == candidate, Organization.deleted_at.is_(None))
            )
            if exclude_id is not None:
                q = q.filter(Organization.id != exclude_id)
            if q.first() is None:
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    @staticmethod
    def serialize_organization(db: Session, org: Organization) -> Dict[str, Any]:
        total_users = (
            db.query(User)
            .filter(User.organization_id == org.id, User.deleted_at.is_(None))
            .count()
        )
        active_users = (
            db.query(User)
            .filter(
                User.organization_id == org.id,
                User.status == "active",
                User.deleted_at.is_(None),
            )
            .count()
        )
        return {
            "id": org.id,
            "name": org.name,
            "slug": getattr(org, "slug", None),
            "description": org.description,
            "status": org.status,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
            "deleted_at": org.deleted_at,
            "total_users": total_users,
            "active_users": active_users,
        }

    @staticmethod
    def _active_orgs_query(db: Session):
        return db.query(Organization).filter(Organization.deleted_at.is_(None))

    @staticmethod
    def list_organizations(db: Session) -> List[Dict[str, Any]]:
        orgs = OrganizationService._active_orgs_query(db).order_by(Organization.id).all()
        return [OrganizationService.serialize_organization(db, org) for org in orgs]

    @staticmethod
    def get_organization(db: Session, organization_id: int) -> Optional[Dict[str, Any]]:
        org = (
            OrganizationService._active_orgs_query(db)
            .filter(Organization.id == organization_id)
            .first()
        )
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
        existing = (
            OrganizationService._active_orgs_query(db)
            .filter(Organization.name == name)
            .first()
        )
        if existing:
            return {"success": False, "error": f"Organization '{name}' already exists"}

        if status not in OrganizationService.ALLOWED_STATUSES:
            return {
                "success": False,
                "error": f"Invalid organization status '{status}'. "
                f"Allowed: {', '.join(sorted(OrganizationService.ALLOWED_STATUSES))}",
            }

        org = Organization(
            name=name,
            slug=OrganizationService._unique_slug(
                db, OrganizationService.slugify(name)
            ),
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
    def soft_delete_organization(
        db: Session,
        organization_id: int,
        deleted_by: int,
    ) -> Dict[str, Any]:
        org = (
            OrganizationService._active_orgs_query(db)
            .filter(Organization.id == organization_id)
            .first()
        )
        if org is None:
            return {"success": False, "error": "Organization not found"}

        active_users = (
            db.query(User)
            .filter(User.organization_id == org.id, User.deleted_at.is_(None))
            .count()
        )
        if active_users > 0:
            return {
                "success": False,
                "error": f"Cannot delete organization with {active_users} active users; "
                "soft-delete or move users first",
            }

        now = utc_now()
        original_name = org.name
        # Keep original name/slug: active-only unique indexes free them for reuse.
        org.status = "inactive"
        org.deleted_at = now
        org.deleted_by = deleted_by
        org.updated_at = now
        db.commit()

        auth_logger.info(
            f"Organization soft-deleted: {original_name}",
            organization_id=org.id,
            deleted_by=deleted_by,
            event_type="organization_soft_deleted",
        )
        return {
            "success": True,
            "message": f"Organization '{original_name}' deleted",
            "organization_id": org.id,
        }

    @staticmethod
    def update_organization(
        db: Session,
        organization_id: int,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        org = (
            OrganizationService._active_orgs_query(db)
            .filter(Organization.id == organization_id)
            .first()
        )
        if org is None:
            return {"success": False, "error": "Organization not found"}

        if "name" in updates and updates["name"] != org.name:
            existing = (
                OrganizationService._active_orgs_query(db)
                .filter(
                    Organization.name == updates["name"],
                    Organization.id != organization_id,
                )
                .first()
            )
            if existing:
                return {
                    "success": False,
                    "error": f"Organization '{updates['name']}' already exists",
                }
            org.name = updates["name"]
            if "slug" not in updates:
                org.slug = OrganizationService._unique_slug(
                    db,
                    OrganizationService.slugify(updates["name"]),
                    exclude_id=organization_id,
                )

        if "slug" in updates and updates["slug"]:
            new_slug = OrganizationService.slugify(updates["slug"])
            org.slug = OrganizationService._unique_slug(
                db, new_slug, exclude_id=organization_id
            )

        if "description" in updates:
            org.description = updates["description"]

        if "status" in updates:
            new_status = updates["status"]
            if new_status not in OrganizationService.ALLOWED_STATUSES:
                return {
                    "success": False,
                    "error": f"Invalid organization status '{new_status}'. "
                    f"Allowed: {', '.join(sorted(OrganizationService.ALLOWED_STATUSES))}",
                }
            org.status = new_status

        org.updated_at = utc_now()
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
