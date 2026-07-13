#!/usr/bin/env python3
"""
Database backup — mysqldump with compression and retention rotation.

Credentials: DATABASE_URL / DB_URL via config.settings (no hardcoded passwords).
See docs/BACKUP_RESTORE.md for RPO/RTO and restore steps.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from config.settings import settings  # noqa: E402
from utils.email_service import get_email_service  # noqa: E402
from utils.loggers import api_logger  # noqa: E402


def _mysql_dump_config(url: str) -> dict[str, str]:
    """Parse SQLAlchemy-style MySQL URL into mysqldump connection fields."""
    parsed = urlparse(url)
    if parsed.scheme not in {"mysql", "mysql+pymysql", "mysql+mysqldb"}:
        raise ValueError(
            f"backup_database.py supports MySQL URLs only; got scheme={parsed.scheme!r}"
        )
    database = (parsed.path or "").lstrip("/").split("?")[0]
    if not database:
        raise ValueError("DATABASE_URL must include a database name path")
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 3306),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
    }


class DatabaseBackupManager:
    """Manage database backups with automated rotation."""

    def __init__(self) -> None:
        cfg = _mysql_dump_config(settings.get_database_url())
        self.db_host = cfg["host"]
        self.db_port = cfg["port"]
        self.db_user = cfg["user"]
        self.db_password = cfg["password"]
        self.db_name = cfg["database"]
        self.backup_dir = Path(
            os.getenv("BACKUP_DIR", str(Path(project_root) / "backups"))
        )
        self.retention_days = int(
            os.getenv("BACKUP_RETENTION_DAYS", "30")
        )

    def create_backup(self) -> tuple[bool, str]:
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_file = self.backup_dir / f"backup_{timestamp}.sql"
            compressed_file = self.backup_dir / f"backup_{timestamp}.sql.gz"

            cmd = [
                "mysqldump",
                f"--host={self.db_host}",
                f"--port={self.db_port}",
                f"--user={self.db_user}",
                f"--password={self.db_password}",
                "--single-transaction",
                "--routines",
                "--triggers",
                self.db_name,
            ]

            api_logger.info(
                "Starting database backup",
                db_name=self.db_name,
                timestamp=timestamp,
                event_type="backup_started",
            )

            with open(backup_file, "w", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )

            if result.returncode != 0:
                api_logger.error(
                    f"mysqldump failed: {result.stderr}",
                    error=result.stderr,
                    event_type="backup_failed",
                )
                if backup_file.exists():
                    backup_file.unlink()
                return False, ""

            with open(backup_file, "rb") as f_in:
                with gzip.open(compressed_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            backup_file.unlink()

            file_size = compressed_file.stat().st_size / (1024 * 1024)
            api_logger.info(
                "Database backup completed successfully",
                backup_file=str(compressed_file),
                file_size_mb=round(file_size, 2),
                timestamp=timestamp,
                event_type="backup_completed",
            )
            return True, str(compressed_file)

        except Exception as e:
            api_logger.error(
                f"Backup failed: {str(e)}",
                error=str(e),
                event_type="backup_error",
            )
            return False, ""

    def cleanup_old_backups(self) -> int:
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            deleted_count = 0
            for backup_file in self.backup_dir.glob("backup_*.sql.gz"):
                timestamp_str = backup_file.stem.split("_")[1:3]
                try:
                    backup_date = datetime.strptime(
                        "_".join(timestamp_str), "%Y-%m-%d_%H%M%S"
                    )
                except ValueError:
                    continue
                if backup_date < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    api_logger.info(
                        f"Deleted old backup: {backup_file.name}",
                        backup_file=str(backup_file),
                        event_type="backup_cleanup",
                    )
            if deleted_count:
                api_logger.info(
                    f"Cleaned up {deleted_count} old backups",
                    deleted_count=deleted_count,
                    retention_days=self.retention_days,
                    event_type="backup_cleanup_completed",
                )
            return deleted_count
        except Exception as e:
            api_logger.error(
                f"Cleanup failed: {str(e)}",
                error=str(e),
                event_type="backup_cleanup_error",
            )
            return 0

    def get_backup_stats(self) -> dict:
        try:
            backup_files = list(self.backup_dir.glob("backup_*.sql.gz"))
            if not backup_files:
                return {
                    "total_backups": 0,
                    "total_size_mb": 0,
                    "oldest_backup": None,
                    "newest_backup": None,
                    "retention_days": self.retention_days,
                }
            total_size = sum(f.stat().st_size for f in backup_files) / (1024 * 1024)
            backup_files.sort(key=lambda f: f.stat().st_mtime)
            return {
                "total_backups": len(backup_files),
                "total_size_mb": round(total_size, 2),
                "oldest_backup": backup_files[0].name,
                "newest_backup": backup_files[-1].name,
                "retention_days": self.retention_days,
            }
        except Exception as e:
            api_logger.error(
                f"Failed to get backup stats: {str(e)}",
                error=str(e),
                event_type="backup_stats_error",
            )
            return {}

    def send_backup_notification(self, success: bool, backup_file: str = "") -> None:
        try:
            if not settings.email.enable_emails:
                return
            notify = (
                os.getenv("BACKUP__NOTIFY_EMAIL")
                or os.getenv("BACKUP_NOTIFY_EMAIL")
                or settings.email.from_email
            )
            if not notify:
                return
            email_service = get_email_service()
            if success:
                stats = self.get_backup_stats()
                subject = f"Database Backup Successful - {datetime.now().strftime('%Y-%m-%d')}"
                body = (
                    "Database backup completed successfully!\n\n"
                    f"Backup File: {backup_file}\n"
                    f"Backup Size: {stats.get('total_size_mb', 0)} MB\n"
                    f"Total Backups: {stats.get('total_backups', 0)}\n"
                    f"Retention: {self.retention_days} days\n"
                )
            else:
                subject = f"Database Backup Failed - {datetime.now().strftime('%Y-%m-%d')}"
                body = (
                    "Database backup failed!\n\n"
                    f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    "Action required: Manual backup may be needed.\n"
                )
            email_service.send_email(
                to_email=notify,
                subject=subject,
                html_content=f"<pre>{body}</pre>",
                plain_text_content=body,
            )
        except Exception as e:
            api_logger.error(
                f"Backup notification failed: {str(e)}",
                error=str(e),
                event_type="backup_notify_error",
            )

    def run(self) -> int:
        success, path = self.create_backup()
        if success:
            self.cleanup_old_backups()
        self.send_backup_notification(success, path)
        return 0 if success else 1


def main() -> int:
    return DatabaseBackupManager().run()


if __name__ == "__main__":
    raise SystemExit(main())
