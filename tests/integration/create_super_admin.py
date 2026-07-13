"""
Create a test super admin
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.database import SessionLocal
from models.user_model import User
from utils.jwt_config import get_password_hash

db = SessionLocal()

# Check if test_super_admin already exists
existing = db.query(User).filter(User.username == "test_super_admin").first()

if existing:
    print(f"✅ Super Admin 'test_super_admin' already exists")
    print(f"   Password: TestSuperAdminPass123!")
else:
    # Create super admin user
    password = "TestSuperAdminPass123!"
    hashed_password = get_password_hash(password)
    
    new_admin = User(
        username="test_super_admin",
        email="test_super_admin@test.com",
        password_hash=hashed_password,
        role="super_admin",
        organization_id=1,
        phone_number="1234567890",
        status="active"
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    print(f"✅ Super Admin created: test_super_admin")
    print(f"   Password: TestSuperAdminPass123!")
    print(f"   Role: super_admin")

db.close()
