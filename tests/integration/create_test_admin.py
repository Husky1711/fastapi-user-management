"""
Create a test admin for testing admin dashboard
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.database import SessionLocal
from models.user_model import User
from utils.jwt_config import get_password_hash

db = SessionLocal()

# Check if test_admin already exists
existing = db.query(User).filter(User.username == "test_dashboard_admin").first()

if existing:
    print(f"✅ Admin 'test_dashboard_admin' already exists")
    print(f"   Password: TestDashboardPass123!")
else:
    # Create admin user
    password = "TestDashboardPass123!"
    hashed_password = get_password_hash(password)
    
    new_admin = User(
        username="test_dashboard_admin",
        email="test_dashboard_admin@test.com",
        password_hash=hashed_password,
        role="admin",
        organization_id=1,
        phone_number="1234567890",
        status="active"
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    print(f"✅ Admin created: test_dashboard_admin")
    print(f"   Password: TestDashboardPass123!")
    print(f"   Role: admin")
    print(f"   Organization ID: 1")

db.close()
