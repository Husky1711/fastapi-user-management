#!/usr/bin/env python3
"""
Database Migration Script - Add 2FA Support
Adds 2FA columns to users table
"""

import sys
import os
from sqlalchemy import text
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.database import get_db
from utils.loggers import api_logger


def add_2fa_columns():
    """Add 2FA columns to users table"""
    db = next(get_db())
    
    try:
        print("🔄 ADDING 2FA COLUMNS TO DATABASE")
        print("=" * 50)
        
        # Check if columns already exist
        result = db.execute(text("DESCRIBE users"))
        existing_columns = [row[0] for row in result]
        
        print(f"\nExisting columns: {len(existing_columns)}")
        
        # Add is_2fa_enabled column
        if 'is_2fa_enabled' not in existing_columns:
            print("\n1. Adding is_2fa_enabled column...")
            db.execute(text(
                "ALTER TABLE users ADD COLUMN is_2fa_enabled BOOLEAN DEFAULT FALSE"
            ))
            db.commit()
            print("✅ Added is_2fa_enabled column")
        else:
            print("✅ is_2fa_enabled column already exists")
        
        # Add two_factor_secret column
        if 'two_factor_secret' not in existing_columns:
            print("\n2. Adding two_factor_secret column...")
            db.execute(text(
                "ALTER TABLE users ADD COLUMN two_factor_secret VARCHAR(255) NULL"
            ))
            db.commit()
            print("✅ Added two_factor_secret column")
        else:
            print("✅ two_factor_secret column already exists")
        
        # Add backup_codes column
        if 'backup_codes' not in existing_columns:
            print("\n3. Adding backup_codes column...")
            db.execute(text(
                "ALTER TABLE users ADD COLUMN backup_codes JSON NULL"
            ))
            db.commit()
            print("✅ Added backup_codes column")
        else:
            print("✅ backup_codes column already exists")
        
        # Add failed_login_attempts column
        if 'failed_login_attempts' not in existing_columns:
            print("\n4. Adding failed_login_attempts column...")
            db.execute(text(
                "ALTER TABLE users ADD COLUMN failed_login_attempts INT DEFAULT 0"
            ))
            db.commit()
            print("✅ Added failed_login_attempts column")
        else:
            print("✅ failed_login_attempts column already exists")
        
        # Create login_attempts table
        print("\n5. Creating login_attempts table...")
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                success BOOLEAN,
                failure_reason VARCHAR(255),
                created_at DATETIME DEFAULT NOW(),
                INDEX idx_user_id (user_id),
                INDEX idx_ip (ip_address),
                INDEX idx_created (created_at)
            )
        """))
        db.commit()
        print("✅ Created login_attempts table")
        
        print("\n🎉 Migration completed successfully!")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        db.rollback()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    success = add_2fa_columns()
    sys.exit(0 if success else 1)
