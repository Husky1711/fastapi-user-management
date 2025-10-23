from sqlalchemy.orm import Session
from models.user_model import User
from utils.database import get_db
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from utils.jwt_config import get_password_hash, verify_password
import secrets
import string
from utils.loggers import auth_logger
from utils.redis_config import RedisClient
import json
from services.password_history_service import PasswordHistoryService
from config.settings import settings

class PasswordResetService:
    """Service for handling password reset functionality"""
    
    @staticmethod
    def generate_reset_token() -> str:
        """Generate a secure reset token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def request_password_reset(db: Session, email: str) -> Dict[str, Any]:
        """
        Request password reset for a user
        
        Args:
            db: Database session
            email: User's email address
            
        Returns:
            Dictionary with reset request result
        """
        try:
            # Find user by email
            user = UserService.get_user_by_email(db, email)
            if not user:
                # Don't reveal if email exists or not for security
                return {
                    "success": True,
                    "message": "If the email exists, a password reset link has been sent",
                    "reset_token": None,
                    "expires_in_minutes": 15
                }
            
            # Generate reset token
            reset_token = PasswordResetService.generate_reset_token()
            
            # Store token in Redis with expiration (15 minutes)
            redis_client = RedisClient.get_client()
            token_key = f"password_reset:{reset_token}"
            token_data = {
                "user_id": user.id,
                "email": user.email,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat()
            }
            
            # Store in Redis with 15 minute expiration
            redis_client.setex(
                token_key,
                900,  # 15 minutes in seconds
                json.dumps(token_data)
            )
            
            # Log the reset request
            auth_logger.info(
                f"Password reset requested for user: {user.username}",
                user_id=user.id,
                username=user.username,
                email=user.email,
                reset_token=reset_token[:8] + "...",  # Log partial token for security
                event_type="password_reset_requested"
            )
            
            # TODO: Send email with reset link
            # For now, we'll return the token for testing
            
            return {
                "success": True,
                "message": "Password reset link has been sent to your email",
                "reset_token": reset_token,  # Remove this in production
                "expires_in_minutes": 15
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error requesting password reset: {str(e)}",
                email=email,
                error=str(e),
                event_type="password_reset_request_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to process password reset request: {str(e)}"
            }
    
    @staticmethod
    def confirm_password_reset(db: Session, token: str, new_password: str) -> Dict[str, Any]:
        """
        Confirm password reset with token and new password
        
        Args:
            db: Database session
            token: Reset token
            new_password: New password
            
        Returns:
            Dictionary with reset confirmation result
        """
        try:
            # Get token from Redis
            redis_client = RedisClient.get_client()
            token_key = f"password_reset:{token}"
            token_data_str = redis_client.get(token_key)
            
            if not token_data_str:
                return {
                    "success": False,
                    "error": "Invalid or expired reset token"
                }
            
            # Parse token data
            token_data = json.loads(token_data_str)
            user_id = token_data.get("user_id")
            email = token_data.get("email")
            
            if not user_id:
                return {
                    "success": False,
                    "error": "Invalid reset token"
                }
            
            # Get user from database
            user = UserService.get_user_by_id(db, user_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            # Verify email matches
            if user.email != email:
                return {
                    "success": False,
                    "error": "Token email mismatch"
                }
            
            # Check password reuse if history is enabled
            if settings.password_policy.enable_password_history:
                reuse_check = PasswordHistoryService.check_password_reuse(
                    db, user_id, new_password, settings.password_policy.password_history_limit
                )
                
                if reuse_check.get("is_reused", False):
                    return {
                        "success": False,
                        "error": reuse_check.get("message", "Cannot reuse recent passwords")
                    }
            
            # Save current password to history before updating
            if settings.password_policy.enable_password_history:
                PasswordHistoryService.save_password_history(
                    db, user_id, user.password, user_id, "password_reset"
                )
            
            # Update password
            hashed_password = get_password_hash(new_password)
            user.password = hashed_password
            user.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(user)
            
            # Delete the reset token from Redis
            redis_client.delete(token_key)
            
            # Log successful password reset
            auth_logger.info(
                f"Password reset completed for user: {user.username}",
                user_id=user.id,
                username=user.username,
                email=user.email,
                event_type="password_reset_completed"
            )
            
            return {
                "success": True,
                "message": "Password has been reset successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error confirming password reset: {str(e)}",
                token=token[:8] + "..." if token else None,
                error=str(e),
                event_type="password_reset_confirm_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to reset password: {str(e)}"
            }
    
    @staticmethod
    def validate_reset_token(token: str) -> Dict[str, Any]:
        """
        Validate a reset token without consuming it
        
        Args:
            token: Reset token to validate
            
        Returns:
            Dictionary with validation result
        """
        try:
            redis_client = RedisClient.get_client()
            token_key = f"password_reset:{token}"
            token_data_str = redis_client.get(token_key)
            
            if not token_data_str:
                return {
                    "valid": False,
                    "error": "Invalid or expired reset token"
                }
            
            token_data = json.loads(token_data_str)
            
            return {
                "valid": True,
                "email": token_data.get("email"),
                "expires_at": token_data.get("expires_at")
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error validating reset token: {str(e)}",
                token=token[:8] + "..." if token else None,
                error=str(e),
                event_type="password_reset_validation_error"
            )
            
            return {
                "valid": False,
                "error": f"Failed to validate token: {str(e)}"
            }

# Import UserService at the end to avoid circular imports
from services.user_service import UserService
