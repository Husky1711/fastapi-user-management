"""Per-organization key/value settings."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.user_model import Organization, OrganizationSetting
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger

# Known keys with expected Python types (stored as JSON).
KNOWN_SETTINGS: Dict[str, type] = {
    "require_2fa": bool,
    "max_sessions_per_user": int,
    "password_max_age_days": int,
    "session_idle_timeout_minutes": int,
    "allow_public_invite_accept": bool,
}


class OrganizationSettingsService:
    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value)

    @staticmethod
    def _decode(raw: str) -> Any:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return raw

    @staticmethod
    def _validate_key_value(key: str, value: Any) -> Optional[str]:
        if not key or len(key) > 100:
            return "setting_key must be 1–100 characters"
        expected = KNOWN_SETTINGS.get(key)
        if expected is not None and not isinstance(value, expected):
            return f"setting '{key}' must be of type {expected.__name__}"
        # Allow unknown keys as JSON-serializable values for forward compat
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return "setting_value must be JSON-serializable"
        return None

    @staticmethod
    def list_settings(db: Session, organization_id: int) -> Dict[str, Any]:
        rows = (
            db.query(OrganizationSetting)
            .filter(OrganizationSetting.organization_id == organization_id)
            .order_by(OrganizationSetting.setting_key)
            .all()
        )
        settings = {
            row.setting_key: OrganizationSettingsService._decode(row.setting_value)
            for row in rows
        }
        return {
            "success": True,
            "organization_id": organization_id,
            "settings": settings,
            "known_keys": list(KNOWN_SETTINGS.keys()),
        }

    @staticmethod
    def get_setting(
        db: Session, organization_id: int, key: str, default: Any = None
    ) -> Any:
        row = (
            db.query(OrganizationSetting)
            .filter(
                OrganizationSetting.organization_id == organization_id,
                OrganizationSetting.setting_key == key,
            )
            .first()
        )
        if row is None:
            return default
        return OrganizationSettingsService._decode(row.setting_value)

    @staticmethod
    def set_setting(
        db: Session,
        organization_id: int,
        key: str,
        value: Any,
        updated_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        org = (
            db.query(Organization)
            .filter(
                Organization.id == organization_id,
                Organization.deleted_at.is_(None),
            )
            .first()
        )
        if not org:
            return {"success": False, "error": "Organization not found"}

        err = OrganizationSettingsService._validate_key_value(key, value)
        if err:
            return {"success": False, "error": err}

        row = (
            db.query(OrganizationSetting)
            .filter(
                OrganizationSetting.organization_id == organization_id,
                OrganizationSetting.setting_key == key,
            )
            .first()
        )
        now = utc_now()
        if row is None:
            row = OrganizationSetting(
                organization_id=organization_id,
                setting_key=key,
                setting_value=OrganizationSettingsService._encode(value),
                updated_by=updated_by,
                updated_at=now,
                created_at=now,
            )
            db.add(row)
        else:
            row.setting_value = OrganizationSettingsService._encode(value)
            row.updated_by = updated_by
            row.updated_at = now

        db.commit()
        auth_logger.info(
            f"Organization setting updated: {key}",
            organization_id=organization_id,
            setting_key=key,
            updated_by=updated_by,
            event_type="org_setting_updated",
        )
        return {
            "success": True,
            "organization_id": organization_id,
            "setting_key": key,
            "setting_value": value,
        }

    @staticmethod
    def delete_setting(
        db: Session,
        organization_id: int,
        key: str,
        deleted_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        row = (
            db.query(OrganizationSetting)
            .filter(
                OrganizationSetting.organization_id == organization_id,
                OrganizationSetting.setting_key == key,
            )
            .first()
        )
        if row is None:
            return {"success": False, "error": "Setting not found"}
        db.delete(row)
        db.commit()
        auth_logger.info(
            f"Organization setting deleted: {key}",
            organization_id=organization_id,
            setting_key=key,
            deleted_by=deleted_by,
            event_type="org_setting_deleted",
        )
        return {"success": True, "organization_id": organization_id, "setting_key": key}
