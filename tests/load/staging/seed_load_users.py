"""Create (or delete) load-test users load_user_0000.. in org 1. STAGING ONLY.

Run from the repo root against the staging database:
    python tests/load/staging/seed_load_users.py --count 300
    python tests/load/staging/seed_load_users.py --delete      # clean up afterwards
"""

import argparse
import os
import sys

sys.path.insert(0, os.getcwd())

from config.settings import settings  # noqa: E402
from models.user_model import User  # noqa: E402
from services.permissions.rbac_catalog_service import RbacCatalogService  # noqa: E402
from utils.database import SessionLocal  # noqa: E402
from utils.jwt_config import get_password_hash  # noqa: E402

PASSWORD = "LoadTest123!"  # must match loadgen.py


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--delete", action="store_true", help="remove all load_user_* accounts")
    args = parser.parse_args()

    if settings.is_production():
        print("Refusing: APP__ENVIRONMENT=production. Load-test users are for staging only.")
        return 1

    with SessionLocal() as db:
        if args.delete:
            n = db.query(User).filter(User.username.like("load_user_%")).delete(synchronize_session=False)
            db.commit()
            print(f"deleted {n} load users")
            return 0

        hashed = get_password_hash(PASSWORD)  # one hash for all: seeding speed only
        existing = {u for (u,) in db.query(User.username).filter(User.username.like("load_user_%"))}
        for i in range(args.count):
            name = f"load_user_{i:04d}"
            if name not in existing:
                db.add(User(username=name, email=f"{name}@loadtest-example.com", password_hash=hashed,
                            status="active", phone_number="1234567890", role="user", organization_id=1))
        db.flush()
        for u in db.query(User).filter(User.username.like("load_user_%")):
            RbacCatalogService.sync_user_system_role(db, u.id, "user", commit=False)
        db.commit()
    print(f"load users ready: {args.count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
