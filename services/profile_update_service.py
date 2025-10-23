from sqlalchemy.orm import Session
from models.user_model import User
from utils.database import get_db
from typing import Optional, Dict, Any
from datetime import datetime
from utils.jwt_config import get_password_hash, verify_password
from utils.loggers import auth_logger
from services.password_history_service import PasswordHistoryService
from config.settings import settings

class ProfileUpdateService:
    """Service for handling user profile updates"""
    
    @staticmethod
    def update_user_profile(db: Session, user_id: int, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user profile information
        
        Args:
            db: Database session
            user_id: ID of the user to update
            profile_data: Dictionary containing profile updates
            
        Returns:
            Dictionary with update result
        """
        try:
            # Get user from database
            user = UserService.get_user_by_id(db, user_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            # Track what fields are being updated
            updated_fields = []
            
            # Update email if provided
            if "email" in profile_data and profile_data["email"] is not None:
                new_email = profile_data["email"]
                
                # Check if email is different
                if user.email != new_email:
                    # Check if new email already exists
                    if UserService.check_email_exists(db, new_email):
                        return {
                            "success": False,
                            "error": f"Email '{new_email}' already exists"
                        }
                    
                    user.email = new_email
                    updated_fields.append("email")
            
            # Update phone number if provided
            if "phone_number" in profile_data and profile_data["phone_number"] is not None:
                new_phone = profile_data["phone_number"]
                
                # Check if phone is different
                if user.phone_number != new_phone:
                    user.phone_number = new_phone
                    updated_fields.append("phone_number")
            
            # If no fields were updated
            if not updated_fields:
                return {
                    "success": True,
                    "message": "No changes made to profile",
                    "user": user
                }
            
            # Update timestamp
            user.updated_at = datetime.utcnow()
            
            # Save changes
            db.commit()
            db.refresh(user)
            
            # Log profile update
            auth_logger.info(
                f"Profile updated for user: {user.username}",
                user_id=user.id,
                username=user.username,
                updated_fields=updated_fields,
                event_type="profile_updated"
            )
            
            return {
                "success": True,
                "message": f"Profile updated successfully. Updated fields: {', '.join(updated_fields)}",
                "user": user
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error updating user profile: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="profile_update_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to update profile: {str(e)}"
            }
    
    @staticmethod
    def change_user_password(db: Session, user_id: int, current_password: str, new_password: str) -> Dict[str, Any]:
        """
        Change user password with current password verification
        
        Args:
            db: Database session
            user_id: ID of the user changing password
            current_password: Current password for verification
            new_password: New password
            
        Returns:
            Dictionary with password change result
        """
        try:
            # Get user from database
            user = UserService.get_user_by_id(db, user_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            # Verify current password
            if not verify_password(current_password, user.password):
                # Log failed password change attempt
                auth_logger.warning(
                    f"Failed password change attempt for user: {user.username} - incorrect current password",
                    user_id=user.id,
                    username=user.username,
                    event_type="password_change_failed"
                )
                
                return {
                    "success": False,
                    "error": "Current password is incorrect"
                }
            
            # Check if new password is different
            if verify_password(new_password, user.password):
                return {
                    "success": False,
                    "error": "New password must be different from current password"
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
                    db, user_id, user.password, user_id, "password_change"
                )
            
            # Update password
            hashed_password = get_password_hash(new_password)
            user.password = hashed_password
            user.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(user)
            
            # Log successful password change
            auth_logger.info(
                f"Password changed for user: {user.username}",
                user_id=user.id,
                username=user.username,
                event_type="password_changed"
            )
            
            return {
                "success": True,
                "message": "Password changed successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error changing user password: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="password_change_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to change password: {str(e)}"
            }
    
    @staticmethod
    def get_user_profile(db: Session, user_id: int) -> Dict[str, Any]:
        """
        Get user profile information
        
        Args:
            db: Database session
            user_id: ID of the user
            
        Returns:
            Dictionary with user profile
        """
        try:
            user = UserService.get_user_by_id(db, user_id)
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            return {
                "success": True,
                "user": user
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting user profile: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="profile_get_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get profile: {str(e)}"
            }

# Import UserService at the end to avoid circular imports
from services.user_service import UserService
