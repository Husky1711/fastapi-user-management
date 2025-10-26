#!/usr/bin/env python3
"""
Database Backup Script
Automated daily MySQL database backup with compression and rotation
"""

import os
import sys
import subprocess
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config.settings import settings
from utils.email_service import get_email_service
from utils.loggers import api_logger


class DatabaseBackupManager:
    """Manage database backups with automated rotation"""
    
    def __init__(self):
        self.db_name = "fastapi_users"
        self.db_user = "root"
        self.db_password = "Sandhya@332"
        self.db_host = "localhost"
        self.db_port = "3306"
        self.backup_dir = Path(project_root) / "backups"
        self.retention_days = 30
        
    def create_backup(self) -> tuple[bool, str]:
        """
        Create a compressed database backup
        
        Returns:
            tuple: (success, backup_file_path)
        """
        try:
            # Create backup directory if it doesn't exist
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_file = self.backup_dir / f"backup_{timestamp}.sql"
            compressed_file = self.backup_dir / f"backup_{timestamp}.sql.gz"
            
            # Run mysqldump
            cmd = [
                "mysqldump",
                f"--host={self.db_host}",
                f"--port={self.db_port}",
                f"--user={self.db_user}",
                f"--password={self.db_password}",
                "--single-transaction",
                "--routines",
                "--triggers",
                self.db_name
            ]
            
            api_logger.info(
                f"Starting database backup",
                db_name=self.db_name,
                timestamp=timestamp,
                event_type="backup_started"
            )
            
            # Execute mysqldump and compress
            with open(backup_file, 'w') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            if result.returncode != 0:
                api_logger.error(
                    f"mysqldump failed: {result.stderr}",
                    error=result.stderr,
                    event_type="backup_failed"
                )
                return False, ""
            
            # Compress backup file
            with open(backup_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove uncompressed file
            backup_file.unlink()
            
            # Get file size
            file_size = compressed_file.stat().st_size / (1024 * 1024)  # MB
            
            api_logger.info(
                f"Database backup completed successfully",
                backup_file=str(compressed_file),
                file_size_mb=round(file_size, 2),
                timestamp=timestamp,
                event_type="backup_completed"
            )
            
            return True, str(compressed_file)
            
        except Exception as e:
            api_logger.error(
                f"Backup failed: {str(e)}",
                error=str(e),
                event_type="backup_error"
            )
            return False, ""
    
    def cleanup_old_backups(self) -> int:
        """
        Delete backups older than retention period
        
        Returns:
            int: Number of backups deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            deleted_count = 0
            
            # Find all backup files
            for backup_file in self.backup_dir.glob("backup_*.sql.gz"):
                # Parse timestamp from filename
                timestamp_str = backup_file.stem.split('_')[1:3]  # ['2025-10-26', '020000']
                try:
                    backup_date = datetime.strptime('_'.join(timestamp_str), "%Y-%m-%d_%H%M%S")
                    
                    if backup_date < cutoff_date:
                        backup_file.unlink()
                        deleted_count += 1
                        api_logger.info(
                            f"Deleted old backup: {backup_file.name}",
                            backup_file=str(backup_file),
                            event_type="backup_cleanup"
                        )
                except ValueError:
                    # Skip files with invalid names
                    continue
            
            if deleted_count > 0:
                api_logger.info(
                    f"Cleaned up {deleted_count} old backups",
                    deleted_count=deleted_count,
                    retention_days=self.retention_days,
                    event_type="backup_cleanup_completed"
                )
            
            return deleted_count
            
        except Exception as e:
            api_logger.error(
                f"Cleanup failed: {str(e)}",
                error=str(e),
                event_type="backup_cleanup_error"
            )
            return 0
    
    def get_backup_stats(self) -> dict:
        """Get backup statistics"""
        try:
            backup_files = list(self.backup_dir.glob("backup_*.sql.gz"))
            
            if not backup_files:
                return {
                    "total_backups": 0,
                    "total_size_mb": 0,
                    "oldest_backup": None,
                    "newest_backup": None
                }
            
            total_size = sum(f.stat().st_size for f in backup_files) / (1024 * 1024)  # MB
            
            # Get oldest and newest backups
            backup_files.sort(key=lambda f: f.stat().st_mtime)
            oldest = backup_files[0]
            newest = backup_files[-1]
            
            return {
                "total_backups": len(backup_files),
                "total_size_mb": round(total_size, 2),
                "oldest_backup": oldest.name,
                "newest_backup": newest.name,
                "retention_days": self.retention_days
            }
            
        except Exception as e:
            api_logger.error(
                f"Failed to get backup stats: {str(e)}",
                error=str(e),
                event_type="backup_stats_error"
            )
            return {}
    
    def send_backup_notification(self, success: bool, backup_file: str = ""):
        """Send email notification about backup status"""
        try:
            if not settings.email.enable_emails:
                return
            
            email_service = get_email_service()
            admin_email = "psaiprasad1728@gmail.com"
            
            if success:
                stats = self.get_backup_stats()
                subject = f"✅ Database Backup Successful - {datetime.now().strftime('%Y-%m-%d')}"
                body = f"""
Database backup completed successfully!

Backup File: {backup_file}
Backup Size: {stats.get('total_size_mb', 0)} MB
Total Backups: {stats.get('total_backups', 0)}
Retention: {self.retention_days} days

The database has been backed up successfully.
                """
            else:
                subject = f"❌ Database Backup Failed - {datetime.now().strftime('%Y-%m-%d')}"
                body = f"""
Database backup failed!

Please check the backup logs for more details.
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Action required: Manual backup may be needed.
                """
            
            email_service.send_email(
                to_email=admin_email,
                subject=subject,
                html_content=f"<pre>{body}</pre>",
                plain_text_content=body
            )
            
        except Exception as e:
            # Don't fail backup if email fails
            api_logger.error(
                f"Failed to send backup notification: {str(e)}",
                error=str(e),
                event_type="backup_notification_error"
            )


def main():
    """Main backup function"""
    print("🔄 DATABASE BACKUP STARTING")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    manager = DatabaseBackupManager()
    
    # Create backup
    print("\n1. Creating database backup...")
    success, backup_file = manager.create_backup()
    
    if success:
        print(f"✅ Backup created: {backup_file}")
        
        # Cleanup old backups
        print("\n2. Cleaning up old backups...")
        deleted_count = manager.cleanup_old_backups()
        print(f"✅ Deleted {deleted_count} old backups")
        
        # Get statistics
        print("\n3. Backup statistics:")
        stats = manager.get_backup_stats()
        print(f"   Total backups: {stats.get('total_backups', 0)}")
        print(f"   Total size: {stats.get('total_size_mb', 0)} MB")
        print(f"   Oldest: {stats.get('oldest_backup', 'N/A')}")
        print(f"   Newest: {stats.get('newest_backup', 'N/A')}")
        
        # Send notification
        print("\n4. Sending notification...")
        manager.send_backup_notification(success=True, backup_file=backup_file)
        print("✅ Notification sent")
        
        print("\n🎉 Backup process completed successfully!")
        return 0
    else:
        print("❌ Backup failed!")
        
        # Send failure notification
        manager.send_backup_notification(success=False)
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
