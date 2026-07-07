"""
Upgrade known seed user passwords from legacy SHA-256 to bcrypt.

Safe to run after scripts/seed.sql on every Codespaces bootstrap.
"""

from __future__ import annotations

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


def main() -> None:
    db = SessionLocal()
    try:
        upgraded = 0
        for username, plain_password in SEED_PASSWORDS.items():
            user = db.query(User).filter(User.username == username).first()
            if not user or not is_legacy_sha256_hash(user.password):
                continue
            user.password = get_password_hash(plain_password)
            upgraded += 1
        if upgraded:
            db.commit()
            print(f"Upgraded {upgraded} seed user password(s) to bcrypt.")
        else:
            print("Seed passwords already use bcrypt (no changes).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
