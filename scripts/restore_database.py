#!/usr/bin/env python3
"""
Database Restore Script
Restore database from backup file
"""

import os
import sys
import subprocess
import gzip
import shutil
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config.settings import settings
from utils.loggers import api_logger


class DatabaseRestoreManager:
    """Manage database restoration from backups"""
    
    def __init__(self):
        self.db_name = "fastapi_users"
        self.db_user = "root"
        self.db_password = "Sandhya@332"
        self.db_host = "localhost"
        self.db_port = "3306"
        self.backup_dir = Path(project_root) / "backups"
    
    def list_backups(self) -> list:
        """List all available backups"""
        try:
            backup_files = list(self.backup_dir.glob("backup_*.sql.gz"))
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            backups = []
            for backup_file in backup_files:
                file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
                backup_date = datetime.fromtimestamp(backup_file.stat().st_mtime)
                
                backups.append({
                    "file": backup_file.name,
                    "path": str(backup_file),
                    "size_mb": round(file_size, 2),
                    "date": backup_date.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            return backups
            
        except Exception as e:
            api_logger.error(
                f"Failed to list backups: {str(e)}",
                error=str(e),
                event_type="backup_list_error"
            )
            return []
    
    def restore_backup(self, backup_file: str, drop_existing: bool = False) -> bool:
        """
        Restore database from backup file
        
        Args:
            backup_file: Path to backup file (can be .sql.gz or .sql)
            drop_existing: Drop existing database before restore
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            backup_path = Path(backup_file)
            
            if not backup_path.exists():
                # Try to find in backup directory
                backup_path = self.backup_dir / backup_file
                if not backup_path.exists():
                    api_logger.error(
                        f"Backup file not found: {backup_file}",
                        backup_file=str(backup_file),
                        event_type="backup_not_found"
                    )
                    return False
            
            # Decompress if needed
            sql_file = backup_path
            if backup_path.suffix == '.gz':
                # Extract to temporary file
                temp_sql = backup_path.with_suffix('')
                
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(temp_sql, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                sql_file = temp_sql
                temp_created = True
            else:
                temp_created = False
            
            api_logger.info(
                f"Starting database restore from: {backup_path.name}",
                backup_file=str(backup_path),
                db_name=self.db_name,
                event_type="restore_started"
            )
            
            # Drop database if requested
            if drop_existing:
                drop_cmd = [
                    "mysql",
                    f"--host={self.db_host}",
                    f"--port={self.db_port}",
                    f"--user={self.db_user}",
                    f"--password={self.db_password}",
                    "-e",
                    f"DROP DATABASE IF EXISTS {self.db_name}"
                ]
                subprocess.run(drop_cmd, capture_output=True)
            
            # Restore database
            cmd = [
                "mysql",
                f"--host={self.db_host}",
                f"--port={self.db_port}",
                f"--user={self.db_user}",
                f"--password={self.db_password}",
                self.db_name
            ]
            
            with open(sql_file, 'r', encoding='utf-8') as f:
                result = subprocess.run(
                    cmd,
                    stdin=f,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            # Clean up temporary file if created
            if temp_created:
                sql_file.unlink()
            
            if result.returncode != 0:
                api_logger.error(
                    f"Restore failed: {result.stderr}",
                    error=result.stderr,
                    backup_file=str(backup_path),
                    event_type="restore_failed"
                )
                return False
            
            api_logger.info(
                f"Database restore completed successfully",
                backup_file=str(backup_path),
                db_name=self.db_name,
                event_type="restore_completed"
            )
            
            return True
            
        except Exception as e:
            api_logger.error(
                f"Restore failed: {str(e)}",
                error=str(e),
                event_type="restore_error"
            )
            return False
    
    def verify_backup(self, backup_file: str) -> bool:
        """
        Verify backup file integrity
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            bool: True if backup is valid, False otherwise
        """
        try:
            backup_path = Path(backup_file)
            
            if not backup_path.exists():
                return False
            
            # Check file size
            if backup_path.stat().st_size == 0:
                return False
            
            # Try to decompress and check
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rb') as f:
                    # Try to read first few bytes
                    f.read(100)
            
            return True
            
        except Exception as e:
            api_logger.error(
                f"Backup verification failed: {str(e)}",
                error=str(e),
                event_type="backup_verification_failed"
            )
            return False


def main():
    """Main restore function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Restore database from backup")
    parser.add_argument("backup_file", nargs="?", help="Backup file to restore")
    parser.add_argument("--list", action="store_true", help="List all backups")
    parser.add_argument("--drop", action="store_true", help="Drop existing database before restore")
    
    args = parser.parse_args()
    
    manager = DatabaseRestoreManager()
    
    if args.list or not args.backup_file:
        print("📋 AVAILABLE BACKUPS")
        print("=" * 60)
        backups = manager.list_backups()
        
        if not backups:
            print("No backups found!")
            return 1
        
        for i, backup in enumerate(backups, 1):
            print(f"\n{i}. {backup['file']}")
            print(f"   Date: {backup['date']}")
            print(f"   Size: {backup['size_mb']} MB")
        
        return 0
    
    # Restore backup
    print("🔄 DATABASE RESTORE STARTING")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backup file: {args.backup_file}")
    print(f"Database: {manager.db_name}")
    
    if args.drop:
        print("\n⚠️  WARNING: Existing database will be dropped!")
    
    # Verify backup
    print("\n1. Verifying backup file...")
    if not manager.verify_backup(args.backup_file):
        print("❌ Backup file is invalid or corrupted!")
        return 1
    
    print("✅ Backup file is valid")
    
    # Restore
    print("\n2. Restoring database...")
    success = manager.restore_backup(args.backup_file, drop_existing=args.drop)
    
    if success:
        print("✅ Database restored successfully!")
        return 0
    else:
        print("❌ Database restore failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
