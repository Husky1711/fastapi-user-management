"""
Upgrade known seed (and optional) user passwords from legacy SHA-256 to bcrypt.

Codespaces / local:
  python scripts/ensure_bcrypt_seed_passwords.py

Production cutover checklist:
  1. Run with --report (no writes) and migrate any remaining SHA-256 users
     (known seeds are upgraded when you run without --report).
  2. For non-seed users still on SHA-256: force a password reset or provide
     plaintext via CUTOVER_PASSWORD_<USERNAME> env (prefer reset).
  3. Confirm --report shows zero legacy hashes.
  4. Set PASSWORD__ALLOW_LEGACY_SHA256_HASHES=false
     (required by validate_production_config() in production).

Exit codes:
  0 — success (or report with zero legacy hashes)
  1 — --report found remaining legacy SHA-256 hashes
  2 — usage / runtime error
"""

from __future__ import annotations

import argparse
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from models.user_model import User  # noqa: E402
from utils.database import SessionLocal  # noqa: E402
from utils.jwt_config import get_password_hash, is_legacy_sha256_hash  # noqa: E402

SEED_PASSWORDS: dict[str, str] = {
    "testadmin": "admin123",
    "testuser": "user123",
    "testorgadmin": "orgadmin123",
    "test_super_admin": "TestSuperAdminPass123!",
}


def _plaintext_for(username: str) -> str | None:
    if username in SEED_PASSWORDS:
        return SEED_PASSWORDS[username]
    env_key = f"CUTOVER_PASSWORD_{username.upper()}"
    return os.getenv(env_key) or None


def report_legacy(db) -> list[str]:
    usernames: list[str] = []
    for user in db.query(User).all():
        if user.password_hash and is_legacy_sha256_hash(user.password_hash):
            usernames.append(user.username)
    return usernames


def upgrade_known(db) -> tuple[int, list[str]]:
    """Upgrade users we know plaintext for. Returns (upgraded_count, skipped_unknown)."""
    upgraded = 0
    skipped: list[str] = []
    for user in db.query(User).all():
        if not user.password_hash or not is_legacy_sha256_hash(user.password_hash):
            continue
        plain = _plaintext_for(user.username)
        if not plain:
            skipped.append(user.username)
            continue
        user.password_hash = get_password_hash(plain)
        upgraded += 1
    if upgraded:
        db.commit()
    return upgraded, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        action="store_true",
        help="List users still on legacy SHA-256; exit 1 if any remain (no writes).",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        if args.report:
            left = report_legacy(db)
            if left:
                print(f"Legacy SHA-256 hashes remaining ({len(left)}): {', '.join(left)}")
                return 1
            print("No legacy SHA-256 password hashes found.")
            return 0

        upgraded, skipped = upgrade_known(db)
        if upgraded:
            print(f"Upgraded {upgraded} user password(s) to bcrypt.")
        else:
            print("No known-plaintext legacy passwords to upgrade.")

        if skipped:
            print(
                "Still on SHA-256 (provide CUTOVER_PASSWORD_<USER> or force reset): "
                + ", ".join(skipped)
            )
            return 1

        left = report_legacy(db)
        if left:
            print(f"Unexpected remaining legacy hashes: {', '.join(left)}")
            return 1
        print("All stored passwords use bcrypt (or no users present).")
        return 0
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
