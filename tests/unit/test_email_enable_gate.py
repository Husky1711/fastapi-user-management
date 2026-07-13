"""Unit tests for EmailService enable_emails gating."""

from unittest.mock import patch

import pytest

from utils.email_service import EmailService


@pytest.mark.unit
def test_send_email_skipped_when_disabled():
    svc = EmailService()
    with patch("utils.email_service.settings.email.enable_emails", False):
        with patch.object(svc, "smtp_host", "smtp.example.com"):
            assert svc.send_email("a@b.com", "subj", "<p>hi</p>") is False


@pytest.mark.unit
def test_welcome_email_respects_enable_emails():
    svc = EmailService()
    with patch("utils.email_service.settings.email.enable_emails", False):
        with patch.object(svc, "render_template", return_value="<p>welcome</p>"):
            assert svc.send_welcome_email("a@b.com", "alice", temp_password="x") is False
