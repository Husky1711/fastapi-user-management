"""Admin invitation service for multi-tenant onboarding."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config.settings import settings
from models.user_model import Organization, User, UserInvitation
from services.users.role_policy import RoleHierarchyValidator
from utils.datetime_utc import utc_now
from utils.jwt_config import get_password_hash
from utils.loggers import auth_logger
from services.permissions.rbac_catalog_service import RbacCatalogService

INVITE_TTL_DAYS = 7


class InvitationService:
    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _active_invite_query(db: Session, token: Optional[str] = None):
        q = (
            db.query(UserInvitation)
            .filter(UserInvitation.accepted_at.is_(None))
            .filter(UserInvitation.revoked_at.is_(None))
            .filter(UserInvitation.expires_at > utc_now())
        )
        if token is not None:
            q = q.filter(
                UserInvitation.token_hash == InvitationService._hash_token(token)
            )
        return q

    @staticmethod
    def create_invitation(
        db: Session,
        inviter: User,
        email: str,
        role: str = "user",
        organization_id: Optional[int] = None,
        expires_in_days: int = INVITE_TTL_DAYS,
    ) -> Dict[str, Any]:
        email = email.strip().lower()
        if not RoleHierarchyValidator.is_valid_role(role) or role == "super_admin":
            return {
                "success": False,
                "error": "Invalid invitation role",
            }
        if not RoleHierarchyValidator.can_create_role(inviter.role, role):
            return {
                "success": False,
                "error": f"Role '{inviter.role}' cannot invite role '{role}'",
                "allowed_roles": RoleHierarchyValidator.get_allowed_roles(inviter.role),
            }

        target_org_id = organization_id or inviter.organization_id
        if inviter.role != "super_admin" and target_org_id != inviter.organization_id:
            return {
                "success": False,
                "error": "Cannot invite users to another organization",
            }

        org = db.query(Organization).filter(Organization.id == target_org_id).first()
        if not org:
            return {"success": False, "error": "Organization not found"}
        if (org.status or "").lower() != "active":
            return {"success": False, "error": "Organization is not active"}

        if db.query(User).filter(User.email == email).first():
            return {"success": False, "error": "A user with this email already exists"}

        # Revoke prior open invites for same email+org
        (
            db.query(UserInvitation)
            .filter(UserInvitation.email == email)
            .filter(UserInvitation.organization_id == target_org_id)
            .filter(UserInvitation.accepted_at.is_(None))
            .filter(UserInvitation.revoked_at.is_(None))
            .update({UserInvitation.revoked_at: utc_now()}, synchronize_session=False)
        )

        raw = InvitationService.generate_token()
        expires_at = utc_now() + timedelta(days=max(1, min(expires_in_days, 30)))
        row = UserInvitation(
            organization_id=target_org_id,
            email=email,
            role=role,
            token_hash=InvitationService._hash_token(raw),
            invited_by=inviter.id,
            expires_at=expires_at,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        InvitationService._send_invite_email(
            email=email,
            token=raw,
            org_name=org.name,
            role=role,
            invited_by=inviter.username,
        )

        auth_logger.info(
            f"Invitation created for {email}",
            invitation_id=row.id,
            organization_id=target_org_id,
            role=role,
            invited_by=inviter.id,
            event_type="invitation_created",
        )

        result: Dict[str, Any] = {
            "success": True,
            "invitation_id": row.id,
            "email": email,
            "role": role,
            "organization_id": target_org_id,
            "expires_at": expires_at.isoformat(),
            "message": "Invitation created",
        }
        if settings.is_development():
            result["invite_token"] = raw
        return result

    @staticmethod
    def _send_invite_email(
        *,
        email: str,
        token: str,
        org_name: str,
        role: str,
        invited_by: str,
    ) -> None:
        if not settings.email.enable_emails:
            return
        try:
            from utils.email_service import get_email_service

            get_email_service().send_invitation_email(
                to_email=email,
                invite_token=token,
                organization_name=org_name,
                role=role,
                invited_by=invited_by,
            )
        except Exception as exc:
            auth_logger.error(
                f"Failed to send invitation email: {exc}",
                email=email,
                error=str(exc),
                event_type="invitation_email_error",
            )

    @staticmethod
    def list_invitations(
        db: Session,
        viewer: User,
        include_accepted: bool = False,
    ) -> Dict[str, Any]:
        q = db.query(UserInvitation)
        if viewer.role != "super_admin":
            q = q.filter(UserInvitation.organization_id == viewer.organization_id)
        if not include_accepted:
            q = (
                q.filter(UserInvitation.accepted_at.is_(None))
                .filter(UserInvitation.revoked_at.is_(None))
            )
        rows = q.order_by(UserInvitation.created_at.desc()).limit(200).all()
        invitations: List[Dict[str, Any]] = [
            {
                "id": r.id,
                "email": r.email,
                "role": r.role,
                "organization_id": r.organization_id,
                "invited_by": r.invited_by,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
                "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "is_open": r.accepted_at is None
                and r.revoked_at is None
                and r.expires_at > utc_now(),
            }
            for r in rows
        ]
        return {"success": True, "invitations": invitations, "count": len(invitations)}

    @staticmethod
    def revoke_invitation(
        db: Session, viewer: User, invitation_id: int
    ) -> Dict[str, Any]:
        row = db.query(UserInvitation).filter(UserInvitation.id == invitation_id).first()
        if not row:
            return {"success": False, "error": "Invitation not found"}
        if viewer.role != "super_admin" and row.organization_id != viewer.organization_id:
            return {"success": False, "error": "Access denied"}
        if row.accepted_at is not None:
            return {"success": False, "error": "Invitation already accepted"}
        if row.revoked_at is not None:
            return {"success": False, "error": "Invitation already revoked"}
        row.revoked_at = utc_now()
        db.commit()
        return {"success": True, "message": "Invitation revoked"}

    @staticmethod
    def validate_token(db: Session, token: str) -> Dict[str, Any]:
        row = InvitationService._active_invite_query(db, token).first()
        if not row:
            return {"valid": False, "error": "Invalid or expired invitation"}
        org = db.query(Organization).filter(Organization.id == row.organization_id).first()
        return {
            "valid": True,
            "email": row.email,
            "role": row.role,
            "organization_id": row.organization_id,
            "organization_name": org.name if org else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }

    @staticmethod
    def accept_invitation(
        db: Session,
        token: str,
        username: str,
        password: str,
    ) -> Dict[str, Any]:
        from services.users.user_service import UserService

        row = InvitationService._active_invite_query(db, token).first()
        if not row:
            return {"success": False, "error": "Invalid or expired invitation"}

        if not UserService.validate_username(username):
            return {"success": False, "error": "Invalid username"}
        if UserService.check_username_exists(db, username):
            return {"success": False, "error": "Username already exists"}
        if UserService.check_email_exists(db, row.email):
            return {"success": False, "error": "Email already registered"}

        now = utc_now()
        user = User(
            username=username,
            password_hash=get_password_hash(password),
            email=row.email,
            role=row.role,
            organization_id=row.organization_id,
            status="active",
            email_verified_at=now,
            password_changed_at=now,
        )
        db.add(user)
        db.flush()
        RbacCatalogService.sync_user_system_role(
            db, user.id, user.role or "user", granted_by=row.invited_by
        )
        row.accepted_at = now
        db.commit()
        db.refresh(user)

        try:
            from utils.email_service import get_email_service

            # Soft welcome (no temp password — user chose one at accept)
            get_email_service().send_welcome_email(
                to_email=user.email,
                username=user.username,
                temp_password=None,
            )
        except Exception as exc:
            auth_logger.error(
                f"Failed to send welcome email after invitation accept: {exc}",
                user_id=user.id,
                email=user.email,
                error=str(exc),
                event_type="welcome_email_error",
            )

        auth_logger.info(
            f"Invitation accepted by {username}",
            user_id=user.id,
            invitation_id=row.id,
            organization_id=row.organization_id,
            event_type="invitation_accepted",
        )
        return {
            "success": True,
            "message": "Invitation accepted",
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
        }
