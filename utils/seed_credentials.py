"""Publicly known dev/CI seed accounts, and a production guard against them.

These usernames/passwords are committed in scripts (CI bootstrap, sign-off checks),
so any environment where they still work is trivially compromised. Production
startup refuses to run while an active account accepts one of them.
"""

from __future__ import annotations

from typing import Dict, List

KNOWN_SEED_CREDENTIALS: Dict[str, str] = {
    "testadmin": "admin123",
    "testuser": "user123",
    "testorgadmin": "orgadmin123",
    "testuser_org2": "user2123",
    "test_super_admin": "TestSuperAdminPass123!",
}


def find_accounts_with_known_passwords(db) -> List[str]:
    """Usernames of active accounts whose password is a publicly known seed password."""
    from models.user_model import User
    from utils.jwt_config import verify_password

    users = (
        db.query(User)
        .filter(
            User.username.in_(list(KNOWN_SEED_CREDENTIALS)),
            User.deleted_at.is_(None),
        )
        .all()
    )
    return sorted(
        u.username
        for u in users
        if u.password_hash
        and verify_password(KNOWN_SEED_CREDENTIALS[u.username], u.password_hash)
    )
