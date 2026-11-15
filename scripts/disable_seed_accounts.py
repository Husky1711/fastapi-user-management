"""
Neutralise publicly known dev/CI seed accounts before going live.

For every account in utils/seed_credentials.KNOWN_SEED_CREDENTIALS that still
accepts its committed password: set a random password, mark it inactive and revoke
its sessions. Nothing is deleted; an admin can re-activate an account and set a
real password later.

Usage (against the target database, e.g. production):
    python scripts/disable_seed_accounts.py            # dry run: report only
    python scripts/disable_seed_accounts.py --apply    # make the changes

Production startup refuses to run while any such account is usable.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from models.user_model import User  # noqa: E402
from services.auth.refresh_token_service import RefreshTokenService  # noqa: E402
from utils.database import SessionLocal  # noqa: E402
from utils.jwt_config import get_password_hash  # noqa: E402
from utils.seed_credentials import find_accounts_with_known_passwords  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--apply", action="store_true", help="make changes (default: dry run)")
    args = parser.parse_args()

    with SessionLocal() as db:
        exposed = find_accounts_with_known_passwords(db)
        if not exposed:
            print("OK: no active account accepts a known seed password.")
            return 0

        print("Accounts using publicly known seed passwords:", ", ".join(exposed))
        if not args.apply:
            print("Dry run only. Re-run with --apply to disable them.")
            return 1

        for user in db.query(User).filter(User.username.in_(exposed)):
            user.password_hash = get_password_hash(secrets.token_urlsafe(32))
            user.status = "inactive"
            RefreshTokenService.revoke_all_user_tokens(
                db, user.id, reason="seed_account_disabled", commit=False
            )
        db.commit()
        print(f"Disabled {len(exposed)} account(s): random password, inactive, sessions revoked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
