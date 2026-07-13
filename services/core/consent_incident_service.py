"""Consent records (GDPR) and security incident logging."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.user_model import ConsentRecord, SecurityIncident, User
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger, security_logger


class ConsentService:
    @staticmethod
    def grant(
        db: Session,
        user_id: int,
        consent_type: str,
        *,
        organization_id: Optional[int] = None,
        source: Optional[str] = None,
        details: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = utc_now()
        row = ConsentRecord(
            user_id=user_id,
            organization_id=organization_id,
            consent_type=consent_type,
            granted=True,
            granted_at=now,
            revoked_at=None,
            source=source,
            details=details,
            created_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        auth_logger.info(
            f"Consent granted: {consent_type}",
            user_id=user_id,
            consent_type=consent_type,
            event_type="consent_granted",
        )
        return {
            "success": True,
            "id": row.id,
            "consent_type": consent_type,
            "granted_at": row.granted_at.isoformat() if row.granted_at else None,
        }

    @staticmethod
    def revoke(
        db: Session,
        user_id: int,
        consent_type: str,
        *,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = utc_now()
        active = (
            db.query(ConsentRecord)
            .filter(
                ConsentRecord.user_id == user_id,
                ConsentRecord.consent_type == consent_type,
                ConsentRecord.granted.is_(True),
                ConsentRecord.revoked_at.is_(None),
            )
            .order_by(ConsentRecord.id.desc())
            .first()
        )
        if active:
            active.granted = False
            active.revoked_at = now
        else:
            db.add(
                ConsentRecord(
                    user_id=user_id,
                    consent_type=consent_type,
                    granted=False,
                    revoked_at=now,
                    source=source or "revoke",
                    created_at=now,
                )
            )
        db.commit()
        return {"success": True, "consent_type": consent_type, "revoked_at": now.isoformat()}

    @staticmethod
    def list_for_user(db: Session, user_id: int) -> Dict[str, Any]:
        rows = (
            db.query(ConsentRecord)
            .filter(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.created_at.desc())
            .limit(100)
            .all()
        )
        return {
            "success": True,
            "consents": [
                {
                    "id": r.id,
                    "consent_type": r.consent_type,
                    "granted": r.granted,
                    "granted_at": r.granted_at.isoformat() if r.granted_at else None,
                    "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
                    "source": r.source,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }


class SecurityIncidentService:
    @staticmethod
    def record(
        db: Session,
        incident_type: str,
        *,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        severity: str = "medium",
        details: Optional[Any] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        detail_str = details
        if details is not None and not isinstance(details, str):
            detail_str = json.dumps(details)

        if organization_id is None and user_id is not None:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                organization_id = user.organization_id

        row = SecurityIncident(
            user_id=user_id,
            organization_id=organization_id,
            incident_type=incident_type,
            severity=severity,
            details=detail_str,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=utc_now(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        security_logger.warning(
            f"Security incident: {incident_type}",
            user_id=user_id,
            organization_id=organization_id,
            incident_type=incident_type,
            severity=severity,
            event_type="security_incident",
        )
        return {"success": True, "id": row.id, "incident_type": incident_type}

    @staticmethod
    def list_incidents(
        db: Session,
        *,
        organization_id: Optional[int] = None,
        user_id: Optional[int] = None,
        incident_type: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        q = db.query(SecurityIncident)
        if organization_id is not None:
            q = q.filter(SecurityIncident.organization_id == organization_id)
        if user_id is not None:
            q = q.filter(SecurityIncident.user_id == user_id)
        if incident_type:
            q = q.filter(SecurityIncident.incident_type == incident_type)
        rows = q.order_by(SecurityIncident.created_at.desc()).limit(limit).all()
        return {
            "success": True,
            "incidents": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "organization_id": r.organization_id,
                    "incident_type": r.incident_type,
                    "severity": r.severity,
                    "details": r.details,
                    "ip_address": r.ip_address,
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }
