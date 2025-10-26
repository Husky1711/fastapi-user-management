"""
Create a test organization admin for testing
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.database import SessionLocal
from models.user_model import User
from utils.jwt_config import get_password_hash

db = SessionLocal()

# Check if test_org_admin already exists
existing = db.query(User).filter(User.username == "test_org_admin").first()

if existing:
    print(f"✅ Org Admin 'test_org_admin' already exists")
    print(f"   Password: TestOrgAdminPass123!")
else:
    # Create organization admin user
    password = "TestOrgAdminPass123!"
    hashed_password = get_password_hash(password)
    
    new_admin = User(
        username="test_org_admin",
        email="test_org_admin@test.com",
        password=hashed_password,
        role="organization_admin",
        organization_id=1,
        phone_number="1234567890",
        status="active"
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    print(f"✅ Org Admin created: test_org_admin")
    print(f"   Password: TestOrgAdminPass123!")
    print(f"   Role: organization_admin")
    print(f"   Organization ID: 1")

db.close()
