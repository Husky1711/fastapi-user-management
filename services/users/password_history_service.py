from sqlalchemy.orm import Session
from models.user_model import PasswordHistory, User
from utils.datetime_utc import utc_now
from utils.jwt_config import verify_password
from utils.loggers import auth_logger
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib

class PasswordHistoryService:
    """Service for managing password history and preventing password reuse"""
    
    @staticmethod
    def save_password_history(
        db: Session, 
        user_id: int, 
        old_password_hash: str, 
        changed_by: int, 
        change_reason: str
    ) -> Dict[str, Any]:
        """
        Save old password to history before updating to new password
        
        Args:
            db: Database session
            user_id: ID of the user whose password is being changed
            old_password_hash: Current password hash to save in history
            changed_by: ID of the user who initiated the change
            change_reason: Reason for password change (password_change, password_reset, admin_reset)
            
        Returns:
            Dictionary with operation result
        """
        try:
            # Create password history entry
            password_history = PasswordHistory(
                user_id=user_id,
                password_hash=old_password_hash,
                changed_by=changed_by,
                change_reason=change_reason,
                created_at=utc_now()
            )
            
            db.add(password_history)
            db.commit()
            
            auth_logger.info(
                f"Password history saved for user_id: {user_id}",
                user_id=user_id,
                changed_by=changed_by,
                change_reason=change_reason,
                event_type="password_history_saved"
            )
            
            return {
                "success": True,
                "message": "Password history saved successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error saving password history: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="password_history_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to save password history: {str(e)}"
            }
    
    @staticmethod
    def check_password_reuse(
        db: Session, 
        user_id: int, 
        new_password_hash: str, 
        history_limit: int = 5
    ) -> Dict[str, Any]:
        """
        Check if new password matches any of the recent password history
        
        Args:
            db: Database session
            user_id: ID of the user
            new_password_hash: Hash of the new password to check
            history_limit: Number of recent passwords to check (default: 5)
            
        Returns:
            Dictionary with reuse check result
        """
        try:
            # Get recent password history for the user
            recent_passwords = db.query(PasswordHistory)\
                .filter(PasswordHistory.user_id == user_id)\
                .order_by(PasswordHistory.created_at.desc())\
                .limit(history_limit)\
                .all()
            
            # Check if new password matches any recent password
            for password_record in recent_passwords:
                if verify_password(new_password_hash, password_record.password_hash):
                    auth_logger.warning(
                        f"Password reuse detected for user_id: {user_id}",
                        user_id=user_id,
                        matched_history_id=password_record.id,
                        matched_date=password_record.created_at.isoformat(),
                        event_type="password_reuse_detected"
                    )
                    
                    return {
                        "is_reused": True,
                        "message": f"Cannot reuse any of the last {history_limit} passwords",
                        "matched_date": password_record.created_at.isoformat(),
                        "history_count": len(recent_passwords)
                    }
            
            auth_logger.info(
                f"Password reuse check passed for user_id: {user_id}",
                user_id=user_id,
                history_count=len(recent_passwords),
                event_type="password_reuse_check_passed"
            )
            
            return {
                "is_reused": False,
                "message": "Password is not reused",
                "history_count": len(recent_passwords)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error checking password reuse: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="password_reuse_check_error"
            )
            
            return {
                "is_reused": False,  # Default to allowing password if check fails
                "error": f"Failed to check password reuse: {str(e)}"
            }
    
    @staticmethod
    def get_password_history(
        db: Session, 
        user_id: int, 
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get password history for a user
        
        Args:
            db: Database session
            user_id: ID of the user
            limit: Maximum number of history records to return
            
        Returns:
            Dictionary with password history
        """
        try:
            password_history = db.query(PasswordHistory)\
                .filter(PasswordHistory.user_id == user_id)\
                .order_by(PasswordHistory.created_at.desc())\
                .limit(limit)\
                .all()
            
            history_data = []
            for record in password_history:
                history_data.append({
                    "id": record.id,
                    "created_at": record.created_at.isoformat(),
                    "changed_by": record.changed_by,
                    "change_reason": record.change_reason,
                    "password_hash": record.password_hash[:20] + "..."  # Truncated for security
                })
            
            return {
                "success": True,
                "history": history_data,
                "total_count": len(history_data)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting password history: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="password_history_get_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get password history: {str(e)}"
            }
    
    @staticmethod
    def cleanup_old_password_history(
        db: Session, 
        user_id: int, 
        keep_count: int = 10,
        older_than_days: int = 365
    ) -> Dict[str, Any]:
        """
        Clean up old password history records
        
        Args:
            db: Database session
            user_id: ID of the user
            keep_count: Number of recent records to keep
            older_than_days: Delete records older than this many days
            
        Returns:
            Dictionary with cleanup result
        """
        try:
            cutoff_date = utc_now() - timedelta(days=older_than_days)
            
            # Get records to delete (old records beyond keep_count)
            old_records = db.query(PasswordHistory)\
                .filter(PasswordHistory.user_id == user_id)\
                .filter(PasswordHistory.created_at < cutoff_date)\
                .order_by(PasswordHistory.created_at.desc())\
                .offset(keep_count)\
                .all()
            
            deleted_count = len(old_records)
            
            # Delete old records
            for record in old_records:
                db.delete(record)
            
            db.commit()
            
            auth_logger.info(
                f"Password history cleanup completed for user_id: {user_id}",
                user_id=user_id,
                deleted_count=deleted_count,
                event_type="password_history_cleanup"
            )
            
            return {
                "success": True,
                "message": f"Cleaned up {deleted_count} old password history records",
                "deleted_count": deleted_count
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error cleaning up password history: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="password_history_cleanup_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to cleanup password history: {str(e)}"
            }
    
    @staticmethod
    def get_password_policy_stats(db: Session, user_id: int) -> Dict[str, Any]:
        """
        Get password policy statistics for a user
        
        Args:
            db: Database session
            user_id: ID of the user
            
        Returns:
            Dictionary with password policy stats
        """
        try:
            # Get total password changes
            total_changes = db.query(PasswordHistory)\
                .filter(PasswordHistory.user_id == user_id)\
                .count()
            
            # Get recent changes (last 30 days)
            thirty_days_ago = utc_now() - timedelta(days=30)
            recent_changes = db.query(PasswordHistory)\
                .filter(PasswordHistory.user_id == user_id)\
                .filter(PasswordHistory.created_at >= thirty_days_ago)\
                .count()
            
            # Get last password change date
            last_change = db.query(PasswordHistory)\
                .filter(PasswordHistory.user_id == user_id)\
                .order_by(PasswordHistory.created_at.desc())\
                .first()
            
            last_change_date = last_change.created_at if last_change else None
            
            return {
                "success": True,
                "stats": {
                    "total_password_changes": total_changes,
                    "recent_changes_30_days": recent_changes,
                    "last_change_date": last_change_date.isoformat() if last_change_date else None,
                    "password_age_days": (utc_now() - last_change_date).days if last_change_date else None
                }
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting password policy stats: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="password_policy_stats_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get password policy stats: {str(e)}"
            }
