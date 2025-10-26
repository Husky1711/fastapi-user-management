"""
Database Index Migration Script (Updated)
Uses SQLAlchemy to create indexes
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from utils.database import get_db
import time

class DatabaseIndexMigrator:
    """Database index migration tool using SQLAlchemy"""
    
    def __init__(self):
        self.create_index_count = 0
        self.existing_index_count = 0
        self.error_count = 0
    
    def create_index(self, db, table_name, index_name, columns, unique=False):
        """Create an index on a table"""
        try:
            # Check if index already exists
            check_query = text(f"""
                SELECT COUNT(*) as count 
                FROM information_schema.statistics 
                WHERE table_schema = DATABASE()
                AND table_name = '{table_name}'
                AND index_name = '{index_name}'
            """)
            
            result = db.execute(check_query).fetchone()
            if result and result[0] > 0:
                print(f"  ⏭️  Index '{index_name}' on '{table_name}' already exists")
                self.existing_index_count += 1
                return True
            
            # Build CREATE INDEX statement
            unique_keyword = "UNIQUE" if unique else ""
            columns_str = ", ".join(columns) if isinstance(columns, list) else columns
            
            sql = f"CREATE {unique_keyword} INDEX {index_name} ON {table_name}({columns_str})"
            
            print(f"  Creating index '{index_name}' on '{table_name}'...")
            db.execute(text(sql))
            db.commit()
            
            print(f"  ✅ Created index '{index_name}' on '{table_name}'")
            self.create_index_count += 1
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to create index '{index_name}' on '{table_name}': {str(e)}")
            self.error_count += 1
            db.rollback()
            return False
    
    def create_users_indexes(self, db):
        """Create indexes on users table"""
        print("\n📋 Creating indexes on 'users' table...")
        
        indexes = [
            ("idx_users_email", "email", False),
            ("idx_users_username", "username", False),
            ("idx_users_organization", "organization_id", False),
            ("idx_users_role", "role", False),
            ("idx_users_status", "status", False),
            ("idx_users_org_role", ["organization_id", "role"], False),
            ("idx_users_org_status", ["organization_id", "status"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "users", index_name, columns, is_unique)
    
    def create_refresh_tokens_indexes(self, db):
        """Create indexes on refresh_tokens table"""
        print("\n📋 Creating indexes on 'refresh_tokens' table...")
        
        indexes = [
            ("idx_refresh_tokens_user", "user_id", False),
            ("idx_refresh_tokens_token", "token_hash", False),
            ("idx_refresh_tokens_revoked", "is_revoked", False),
            ("idx_refresh_tokens_expires", "expires_at", False),
            ("idx_refresh_tokens_user_active", ["user_id", "is_revoked"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "refresh_tokens", index_name, columns, is_unique)
    
    def create_user_sessions_indexes(self, db):
        """Create indexes on user_sessions table"""
        print("\n📋 Creating indexes on 'user_sessions' table...")
        
        indexes = [
            ("idx_user_sessions_user", "user_id", False),
            ("idx_user_sessions_active", "is_active", False),
            ("idx_user_sessions_device", "device_info", False),
            ("idx_user_sessions_user_active", ["user_id", "is_active"], False),
            ("idx_user_sessions_expires", "expires_at", False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "user_sessions", index_name, columns, is_unique)
    
    def create_audit_logs_indexes(self, db):
        """Create indexes on audit_logs table"""
        print("\n📋 Creating indexes on 'audit_logs' table...")
        
        indexes = [
            ("idx_audit_logs_user", "user_id", False),
            ("idx_audit_logs_created", "created_at", False),
            ("idx_audit_logs_event", "event_type", False),
            ("idx_audit_logs_org", "organization_id", False),
            ("idx_audit_logs_user_date", ["user_id", "created_at"], False),
            ("idx_audit_logs_org_date", ["organization_id", "created_at"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "audit_logs", index_name, columns, is_unique)
    
    def create_login_attempts_indexes(self, db):
        """Create indexes on login_attempts table"""
        print("\n📋 Creating indexes on 'login_attempts' table...")
        
        indexes = [
            ("idx_login_attempts_user", "user_id", False),
            ("idx_login_attempts_success", "success", False),
            ("idx_login_attempts_created", "created_at", False),
            ("idx_login_attempts_ip", "ip_address", False),
            ("idx_login_attempts_user_recent", ["user_id", "created_at"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "login_attempts", index_name, columns, is_unique)
    
    def create_organizations_indexes(self, db):
        """Create indexes on organizations table"""
        print("\n📋 Creating indexes on 'organizations' table...")
        
        indexes = [
            ("idx_organizations_name", "name", False),
            ("idx_organizations_status", "status", False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "organizations", index_name, columns, is_unique)
    
    def create_password_history_indexes(self, db):
        """Create indexes on password_history table"""
        print("\n📋 Creating indexes on 'password_history' table...")
        
        indexes = [
            ("idx_password_history_user", "user_id", False),
            ("idx_password_history_created", "created_at", False),
            ("idx_password_history_user_date", ["user_id", "created_at"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "password_history", index_name, columns, is_unique)
    
    def create_user_permissions_indexes(self, db):
        """Create indexes on user_permissions table"""
        print("\n📋 Creating indexes on 'user_permissions' table...")
        
        indexes = [
            ("idx_user_permissions_user", "user_id", False),
            ("idx_user_permissions_resource", "resource_type", False),
            ("idx_user_permissions_user_resource", ["user_id", "resource_type"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "user_permissions", index_name, columns, is_unique)
    
    def create_api_keys_indexes(self, db):
        """Create indexes on api_keys table"""
        print("\n📋 Creating indexes on 'api_keys' table...")
        
        indexes = [
            ("idx_api_keys_user", "user_id", False),
            ("idx_api_keys_key_hash", "key_hash", False),
            ("idx_api_keys_active", "is_active", False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "api_keys", index_name, columns, is_unique)
    
    def create_user_groups_indexes(self, db):
        """Create indexes on user_groups table"""
        print("\n📋 Creating indexes on 'user_groups' table...")
        
        indexes = [
            ("idx_user_groups_org", "organization_id", False),
            ("idx_user_groups_name", "name", False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "user_groups", index_name, columns, is_unique)
    
    def create_user_group_memberships_indexes(self, db):
        """Create indexes on user_group_memberships table"""
        print("\n📋 Creating indexes on 'user_group_memberships' table...")
        
        indexes = [
            ("idx_user_group_memberships_user", "user_id", False),
            ("idx_user_group_memberships_group", "group_id", False),
            ("idx_user_group_memberships_user_group", ["user_id", "group_id"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index(db, "user_group_memberships", index_name, columns, is_unique)
    
    def create_all_indexes(self, db):
        """Create all indexes"""
        start_time = time.time()
        
        print("\n" + "=" * 60)
        print("🚀 DATABASE INDEX MIGRATION")
        print("=" * 60)
        
        # Create indexes for all tables
        self.create_users_indexes(db)
        self.create_refresh_tokens_indexes(db)
        self.create_user_sessions_indexes(db)
        self.create_audit_logs_indexes(db)
        self.create_login_attempts_indexes(db)
        self.create_organizations_indexes(db)
        self.create_password_history_indexes(db)
        self.create_user_permissions_indexes(db)
        self.create_api_keys_indexes(db)
        self.create_user_groups_indexes(db)
        self.create_user_group_memberships_indexes(db)
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("📊 MIGRATION SUMMARY")
        print("=" * 60)
        print(f"✅ Created indexes: {self.create_index_count}")
        print(f"⏭️  Skipped (already exist): {self.existing_index_count}")
        print(f"❌ Errors: {self.error_count}")
        print(f"⏱️  Time taken: {elapsed_time:.2f} seconds")
        print("=" * 60)
    
    def close(self):
        """Close database connection"""
        print("\n✅ Migration completed")


def main():
    """Run the migration"""
    migrator = DatabaseIndexMigrator()
    
    try:
        # Get database session
        db = next(get_db())
        
        # Create all indexes
        migrator.create_all_indexes(db)
        
        # Close migration
        migrator.close()
        
        print("\n✅ Index migration completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

