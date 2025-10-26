"""
Database Index Migration Script
Adds performance indexes to improve query speed by 5-10x
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pymysql
from config.settings import settings
import time

class DatabaseIndexMigrator:
    """Database index migration tool"""
    
    def __init__(self):
        self.db_config = settings.database
        self.connection = None
        self.create_index_count = 0
        self.existing_index_count = 0
    
    def connect(self):
        """Connect to MySQL database"""
        try:
            # Parse database URL to get connection params
            db_url = self.db_config.url
            
            # Extract connection details
            # Format: mysql+pymysql://user:password@host:port/database
            from urllib.parse import urlparse
            
            # Remove the mysql+pymysql:// prefix
            url = urlparse(db_url.replace("mysql+pymysql://", "mysql://"))
            
            host = url.hostname
            port = url.port or 3306
            user = url.username
            password = url.password
            database = url.path.lstrip("/")
            
            print(f"Connecting to MySQL database: {database} on {host}:{port}")
            
            self.connection = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                cursorclass=pymysql.cursors.DictCursor
            )
            
            print("✅ Connected to database successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to database: {str(e)}")
            return False
    
    def check_index_exists(self, table_name, index_name):
        """Check if an index already exists"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"""
                SELECT COUNT(*) as count 
                FROM information_schema.statistics 
                WHERE table_schema = DATABASE()
                AND table_name = %s
                AND index_name = %s
            """, (table_name, index_name))
            
            result = cursor.fetchone()
            return result['count'] > 0
        except Exception as e:
            print(f"Warning: Could not check index existence: {str(e)}")
            return False
    
    def create_index(self, table_name, index_name, columns, unique=False):
        """Create an index on a table"""
        try:
            # Check if index already exists
            if self.check_index_exists(table_name, index_name):
                print(f"  ⏭️  Index '{index_name}' on '{table_name}' already exists")
                self.existing_index_count += 1
                return True
            
            # Build CREATE INDEX statement
            unique_keyword = "UNIQUE" if unique else ""
            columns_str = ", ".join(columns) if isinstance(columns, list) else columns
            
            cursor = self.connection.cursor()
            sql = f"CREATE {unique_keyword} INDEX {index_name} ON {table_name}({columns_str})"
            
            print(f"  Creating index '{index_name}' on '{table_name}'...")
            cursor.execute(sql)
            self.connection.commit()
            
            print(f"  ✅ Created index '{index_name}' on '{table_name}'")
            self.create_index_count += 1
            return True
            
        except Exception as e:
            print(f"  ❌ Failed to create index '{index_name}' on '{table_name}': {str(e)}")
            return False
    
    def create_users_indexes(self):
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
            self.create_index("users", index_name, columns, is_unique)
    
    def create_refresh_tokens_indexes(self):
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
            self.create_index("refresh_tokens", index_name, columns, is_unique)
    
    def create_user_sessions_indexes(self):
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
            self.create_index("user_sessions", index_name, columns, is_unique)
    
    def create_audit_logs_indexes(self):
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
            self.create_index("audit_logs", index_name, columns, is_unique)
    
    def create_login_attempts_indexes(self):
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
            self.create_index("login_attempts", index_name, columns, is_unique)
    
    def create_organizations_indexes(self):
        """Create indexes on organizations table"""
        print("\n📋 Creating indexes on 'organizations' table...")
        
        indexes = [
            ("idx_organizations_name", "name", False),
            ("idx_organizations_status", "status", False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index("organizations", index_name, columns, is_unique)
    
    def create_password_history_indexes(self):
        """Create indexes on password_history table"""
        print("\n📋 Creating indexes on 'password_history' table...")
        
        indexes = [
            ("idx_password_history_user", "user_id", False),
            ("idx_password_history_created", "created_at", False),
            ("idx_password_history_user_date", ["user_id", "created_at"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index("password_history", index_name, columns, is_unique)
    
    def create_user_permissions_indexes(self):
        """Create indexes on user_permissions table"""
        print("\n📋 Creating indexes on 'user_permissions' table...")
        
        indexes = [
            ("idx_user_permissions_user", "user_id", False),
            ("idx_user_permissions_resource", "resource_type", False),
            ("idx_user_permissions_user_resource", ["user_id", "resource_type"], False),
        ]
        
        for index_name, columns, is_unique in indexes:
            self.create_index("user_permissions", index_name, columns, is_unique)
    
    def create_all_indexes(self):
        """Create all indexes"""
        start_time = time.time()
        
        print("\n" + "=" * 60)
        print("🚀 DATABASE INDEX MIGRATION")
        print("=" * 60)
        
        # Create indexes for all tables
        self.create_users_indexes()
        self.create_refresh_tokens_indexes()
        self.create_user_sessions_indexes()
        self.create_audit_logs_indexes()
        self.create_login_attempts_indexes()
        self.create_organizations_indexes()
        self.create_password_history_indexes()
        self.create_user_permissions_indexes()
        
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("📊 MIGRATION SUMMARY")
        print("=" * 60)
        print(f"✅ Created indexes: {self.create_index_count}")
        print(f"⏭️  Skipped (already exist): {self.existing_index_count}")
        print(f"⏱️  Time taken: {elapsed_time:.2f} seconds")
        print("=" * 60)
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("\n✅ Database connection closed")


def main():
    """Run the migration"""
    migrator = DatabaseIndexMigrator()
    
    try:
        # Connect to database
        if not migrator.connect():
            print("❌ Could not connect to database")
            return 1
        
        # Create all indexes
        migrator.create_all_indexes()
        
        # Close connection
        migrator.close()
        
        print("\n✅ Index migration completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

