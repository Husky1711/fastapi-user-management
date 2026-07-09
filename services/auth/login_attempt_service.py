"""
Login Attempt Tracking Service
Tracks failed login attempts and implements account lockout
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.user_model import User, LoginAttempt
from services.auth.auth_service import AuthService
from utils.loggers import security_logger
from config.settings import settings


class LoginAttemptService:
    """Service for tracking login attempts and managing account lockouts"""
    
    @staticmethod
    def record_login_attempt(
        db: Session,
        username: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        failure_reason: str = None,
        user_id: int = None
    ) -> None:
        """
        Record a login attempt
        
        Args:
            db: Database session
            username: Username attempted
            ip_address: IP address of the attempt
            user_agent: User agent string
            success: Whether login was successful
            failure_reason: Reason for failure
            user_id: User ID if user found
        """
        try:
            attempt = LoginAttempt(
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                failure_reason=failure_reason
            )
            db.add(attempt)
            db.commit()
            
            security_logger.info(
                "Login attempt recorded",
                username=username,
                success=success,
                ip_address=ip_address,
                event_type="login_attempt"
            )
            
        except Exception as e:
            security_logger.error(
                f"Failed to record login attempt: {str(e)}",
                username=username,
                error=str(e),
                event_type="login_attempt_error"
            )
            db.rollback()
    
    @staticmethod
    def increment_failed_attempts(
        db: Session,
        user: User
    ) -> Optional[datetime]:
        """
        Increment failed login attempts and check for lockout
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            Optional[datetime]: Lockout expiration time if locked
        """
        try:
            user.failed_login_attempts += 1
            
            # Calculate lockout time if needed
            lockout_time = None
            if user.failed_login_attempts >= settings.security.max_login_attempts:
                lockout_time = datetime.utcnow() + timedelta(
                    minutes=settings.security.lockout_duration_minutes
                )
                user.locked_until = lockout_time
                
                security_logger.warning(
                    "Account locked due to too many failed attempts",
                    user_id=user.id,
                    username=user.username,
                    failed_attempts=user.failed_login_attempts,
                    lockout_until=lockout_time.isoformat(),
                    event_type="account_locked"
                )
            
            db.commit()
            return lockout_time
            
        except Exception as e:
            security_logger.error(
                f"Failed to increment failed attempts: {str(e)}",
                user_id=user.id,
                error=str(e),
                event_type="failed_attempts_error"
            )
            db.rollback()
            return None
    
    @staticmethod
    def reset_failed_attempts(db: Session, user: User) -> None:
        """
        Reset failed login attempts on successful login
        
        Args:
            db: Database session
            user: User object
        """
        try:
            if user.failed_login_attempts > 0:
                user.failed_login_attempts = 0
                user.locked_until = None
                db.commit()
                
                security_logger.info(
                    "Failed attempts reset",
                    user_id=user.id,
                    username=user.username,
                    event_type="failed_attempts_reset"
                )
        except Exception as e:
            security_logger.error(
                f"Failed to reset failed attempts: {str(e)}",
                user_id=user.id,
                error=str(e),
                event_type="reset_attempts_error"
            )
            db.rollback()
    
    @staticmethod
    def is_account_locked(user: User) -> bool:
        """
        Check if account is locked
        
        Args:
            user: User object
            
        Returns:
            bool: True if locked, False otherwise
        """
        if user.locked_until is None:
            return False
        
        return datetime.utcnow() < user.locked_until
    
    @staticmethod
    def get_lockout_info(user: User) -> Dict[str, Any]:
        """
        Get account lockout information
        
        Args:
            user: User object
            
        Returns:
            Dict with lockout status and info
        """
        is_locked = LoginAttemptService.is_account_locked(user)
        
        result = {
            "is_locked": is_locked,
            "failed_attempts": user.failed_login_attempts,
            "max_attempts": settings.security.max_login_attempts,
            "remaining_attempts": max(0, settings.security.max_login_attempts - user.failed_login_attempts)
        }
        
        if is_locked:
            result["locked_until"] = user.locked_until.isoformat()
            # Calculate remaining lockout time
            remaining_minutes = max(0, int((user.locked_until - datetime.utcnow()).total_seconds() / 60))
            result["remaining_lockout_minutes"] = remaining_minutes
        else:
            result["locked_until"] = None
            result["remaining_lockout_minutes"] = 0
        
        return result
    
    @staticmethod
    def unlock_account(db: Session, user: User, unlocked_by: int = None) -> bool:
        """
        Manually unlock an account
        
        Args:
            db: Database session
            user: User object
            unlocked_by: User ID of admin performing unlock
            
        Returns:
            bool: True if successful
        """
        try:
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()
            
            security_logger.info(
                "Account unlocked manually",
                user_id=user.id,
                username=user.username,
                unlocked_by=unlocked_by,
                event_type="account_unlocked"
            )
            
            return True
            
        except Exception as e:
            security_logger.error(
                f"Failed to unlock account: {str(e)}",
                user_id=user.id,
                error=str(e),
                event_type="unlock_error"
            )
            db.rollback()
            return False
    
    @staticmethod
    def get_recent_attempts(
        db: Session,
        username: str = None,
        ip_address: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent login attempts
        
        Args:
            db: Database session
            username: Filter by username
            ip_address: Filter by IP address
            limit: Number of results to return
            
        Returns:
            List of attempt records
        """
        try:
            query = db.query(LoginAttempt).order_by(desc(LoginAttempt.created_at))
            
            if username:
                query = query.filter(LoginAttempt.username == username)
            
            if ip_address:
                query = query.filter(LoginAttempt.ip_address == ip_address)
            
            attempts = query.limit(limit).all()
            
            return [
                {
                    "username": attempt.username,
                    "ip_address": attempt.ip_address,
                    "success": attempt.success,
                    "failure_reason": attempt.failure_reason,
                    "created_at": attempt.created_at.isoformat() if attempt.created_at else None
                }
                for attempt in attempts
            ]
            
        except Exception as e:
            security_logger.error(
                f"Failed to get recent attempts: {str(e)}",
                error=str(e),
                event_type="get_attempts_error"
            )
            return []
    
    @staticmethod
    def authenticate_with_lockout(
        db: Session,
        username: str,
        password: str,
        ip_address: str,
        user_agent: str,
    ) -> Dict[str, Any]:
        """
        Shared login path: lockout check, credential verify, attempt tracking.

        Returns dict with success=True and user, or success=False with error_code
        (ACCOUNT_LOCKED | INVALID_CREDENTIALS).
        """
        user_row = db.query(User).filter(User.username == username).first()

        LoginAttemptService.record_login_attempt(
            db=db,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason="Pending authentication",
            user_id=user_row.id if user_row else None,
        )

        if user_row and LoginAttemptService.is_account_locked(user_row):
            LoginAttemptService.record_login_attempt(
                db=db,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="Account locked",
                user_id=user_row.id,
            )
            return {
                "success": False,
                "error_code": "ACCOUNT_LOCKED",
                "error": "Account locked",
                "lockout_info": LoginAttemptService.get_lockout_info(user_row),
            }

        user = AuthService.authenticate_user(db, username, password)
        if not user:
            user_row = db.query(User).filter(User.username == username).first()
            if user_row:
                LoginAttemptService.increment_failed_attempts(db, user_row)

            LoginAttemptService.record_login_attempt(
                db=db,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="Invalid credentials",
                user_id=user_row.id if user_row else None,
            )
            return {
                "success": False,
                "error_code": "INVALID_CREDENTIALS",
                "error": "Invalid credentials",
            }

        LoginAttemptService.reset_failed_attempts(db, user)
        LoginAttemptService.record_login_attempt(
            db=db,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            user_id=user.id,
        )
        return {"success": True, "user": user}
