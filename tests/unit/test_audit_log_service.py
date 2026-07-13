"""Lightweight unit coverage for AuditLogService (readiness 10.8 sample)."""

from unittest.mock import MagicMock, patch

import pytest

from services.audit.audit_log_service import AuditLogService


@pytest.mark.unit
def test_create_audit_log_persists_and_returns_success():
    db = MagicMock()
    with patch("services.audit.audit_log_service.AuditLog") as AuditLogMock:
        instance = MagicMock()
        instance.id = 42
        AuditLogMock.return_value = instance
        result = AuditLogService.create_audit_log(
            db=db,
            event_type="login",
            event_category="auth",
            action="login",
            user_id=1,
            organization_id=1,
            status="success",
        )
    assert result["success"] is True
    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.unit
def test_create_audit_log_rolls_back_on_error():
    db = MagicMock()
    db.commit.side_effect = RuntimeError("db down")
    with patch("services.audit.audit_log_service.AuditLog"):
        result = AuditLogService.create_audit_log(
            db=db,
            event_type="login",
            event_category="auth",
            action="login",
        )
    assert result["success"] is False
    db.rollback.assert_called()
