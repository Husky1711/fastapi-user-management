"""
Verify SMTP settings by sending one test email (go-live checklist 15.1.11).

Uses the same EMAIL__* settings as the app and reports which step fails
(connect / STARTTLS / login / send), so a broken mail setup is found before users
hit password reset or invitations.

Usage:
    python scripts/check_email.py --to you@yourcompany.com
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.mime.text import MIMEText

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config.settings import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a test email with EMAIL__* settings")
    parser.add_argument("--to", required=True, help="recipient address")
    args = parser.parse_args()

    cfg = settings.email
    print(
        f"host={cfg.smtp_host or '(unset)'} port={cfg.smtp_port} "
        f"user={'set' if cfg.smtp_username else '(unset)'} from={cfg.from_email or '(unset)'} "
        f"enable_emails={cfg.enable_emails} base_url={cfg.base_url}"
    )
    problems = []
    if not cfg.enable_emails:
        problems.append("EMAIL__ENABLE_EMAILS is false: the app will not send any email")
    if not cfg.smtp_host:
        problems.append("EMAIL__SMTP_HOST is not set")
    if not cfg.from_email:
        problems.append("EMAIL__FROM_EMAIL is not set")
    if "localhost" in (cfg.base_url or "") or "127.0.0.1" in (cfg.base_url or ""):
        problems.append(f"EMAIL__BASE_URL={cfg.base_url} - links in emails would point at localhost")
    for p in problems:
        print("FAIL:", p)
    if not cfg.smtp_host or not cfg.from_email:
        return 1

    msg = MIMEText("Test email from the FastAPI user-management backend. SMTP works.")
    msg["Subject"] = "SMTP check"
    msg["From"] = cfg.from_email
    msg["To"] = args.to

    step = "connect"
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=cfg.smtp_timeout_seconds) as smtp:
            step = "STARTTLS"
            smtp.starttls()
            if cfg.smtp_username:
                step = "login"
                smtp.login(cfg.smtp_username, cfg.smtp_password)
            step = "send"
            smtp.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL at {step}: {type(exc).__name__}: {exc}")
        return 1

    print(f"PASS: test email sent to {args.to} - check the inbox (and spam folder).")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
