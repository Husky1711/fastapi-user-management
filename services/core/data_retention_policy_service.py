"""Read/write data_retention_policies used by RetentionService."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config.settings import settings
from models.user_model import DataRetentionPolicy
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger

# Fallback when DB row missing or inactive
_SETTINGS_FALLBACKS = {
    "login_attempts": lambda: settings.app.login_attempts_retention_days,
    "audit_logs": lambda: settings.app.audit_logs_retention_days,
    "password_history": lambda: settings.password_policy.password_history_retention_days,
    "user_invitations": lambda: 30,
}


class DataRetentionPolicyService:
    @staticmethod
    def get_retention_days(db: Session, table_name: str) -> Optional[int]:
        """
        Active policy days for table, or settings fallback.
        Returns None if purge for this table should be skipped (inactive, no fallback).
        """
        row = (
            db.query(DataRetentionPolicy)
            .filter(DataRetentionPolicy.table_name == table_name)
            .first()
        )
        if row is not None:
            if not row.is_active:
                return None
            return int(row.retention_days)
        fallback = _SETTINGS_FALLBACKS.get(table_name)
        return int(fallback()) if fallback else None

    @staticmethod
    def list_policies(db: Session) -> Dict[str, Any]:
        rows = (
            db.query(DataRetentionPolicy)
            .order_by(DataRetentionPolicy.table_name)
            .all()
        )
        return {
            "success": True,
            "policies": [
                {
                    "id": r.id,
                    "table_name": r.table_name,
                    "retention_days": r.retention_days,
                    "is_active": r.is_active,
                    "description": r.description,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in rows
            ],
        }

    @staticmethod
    def upsert_policy(
        db: Session,
        table_name: str,
        retention_days: int,
        *,
        is_active: bool = True,
        description: Optional[str] = None,
        updated_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        if retention_days < 1:
            return {"success": False, "error": "retention_days must be >= 1"}
        if not table_name or len(table_name) > 100:
            return {"success": False, "error": "invalid table_name"}

        row = (
            db.query(DataRetentionPolicy)
            .filter(DataRetentionPolicy.table_name == table_name)
            .first()
        )
        now = utc_now()
        if row is None:
            row = DataRetentionPolicy(
                table_name=table_name,
                retention_days=retention_days,
                is_active=is_active,
                description=description,
                updated_by=updated_by,
                updated_at=now,
                created_at=now,
            )
            db.add(row)
        else:
            row.retention_days = retention_days
            row.is_active = is_active
            if description is not None:
                row.description = description
            row.updated_by = updated_by
            row.updated_at = now
        db.commit()
        db.refresh(row)
        auth_logger.info(
            f"Retention policy updated: {table_name}",
            table_name=table_name,
            retention_days=retention_days,
            is_active=is_active,
            updated_by=updated_by,
            event_type="retention_policy_updated",
        )
        return {
            "success": True,
            "policy": {
                "id": row.id,
                "table_name": row.table_name,
                "retention_days": row.retention_days,
                "is_active": row.is_active,
                "description": row.description,
            },
        }
