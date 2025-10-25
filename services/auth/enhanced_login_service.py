#!/usr/bin/env python3
"""
Enhanced Login Service with Session Management
Handles multiple login scenarios and session control
"""

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from .auth_service import AuthService
from .refresh_token_service import RefreshTokenService
from .logout_service import LogoutService
from models.user_model import User, RefreshToken
from utils.loggers import auth_logger, security_logger
from config.settings import settings
from datetime import datetime
import traceback

class EnhancedLoginService:
    """Enhanced login service with session management options"""
    
    @staticmethod
    def login_with_session_control(
        db: Session,
        username: str,
        password: str,
        device_info: str = None,
        ip_address: str = None,
        user_agent: str = None,
        session_strategy: str = "allow_multiple"
    ) -> Dict[str, Any]:
        """
        Login with configurable session management
        
        Args:
            db: Database session
            username: Username
            password: Password
            device_info: Device information
            ip_address: IP address
            user_agent: User agent string
            session_strategy: How to handle existing sessions
                - "allow_multiple": Allow multiple sessions (default)
                - "replace_all": Replace all existing sessions
                - "replace_same_device": Replace sessions from same device
                - "deny_if_exists": Deny login if user already has sessions
                - "limit_sessions": Limit to max sessions per user
        
        Returns:
            Dict with login result and session info
        """
        try:
            # Authenticate user
            user = AuthService.authenticate_user(db, username, password)
            if not user:
                return {
                    "success": False,
                    "error": "Invalid credentials",
                    "error_code": "INVALID_CREDENTIALS"
                }
            
            # Check existing sessions
            existing_sessions = RefreshTokenService.get_user_tokens(db, user.id)
            existing_count = len(existing_sessions)
            
            auth_logger.info(
                f"User {username} has {existing_count} existing sessions",
                user_id=user.id,
                existing_sessions=existing_count,
                session_strategy=session_strategy,
                event_type="login_session_check"
            )
            
            # Handle session strategy
            session_action = EnhancedLoginService._handle_session_strategy(
                db, user, existing_sessions, session_strategy, device_info
            )
            
            if not session_action["allow_login"]:
                return {
                    "success": False,
                    "error": session_action["error"],
                    "error_code": session_action["error_code"],
                    "existing_sessions": existing_count
                }
            
            # Create new tokens
            access_token, refresh_token = AuthService.create_tokens_for_user(
                db, user, device_info, ip_address, user_agent
            )
            
            # Update last login
            from services.users import UserService
            UserService.update_last_login(db, user.id)
            
            # Get updated session count
            new_session_count = len(RefreshTokenService.get_user_tokens(db, user.id))
            
            auth_logger.info(
                f"Login successful for user {username}",
                user_id=user.id,
                session_strategy=session_strategy,
                sessions_created=session_action.get("sessions_created", 0),
                sessions_revoked=session_action.get("sessions_revoked", 0),
                total_sessions=new_session_count,
                event_type="login_success"
            )
            
            return {
                "success": True,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": settings.jwt.access_token_expire_minutes * 60,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "organization_id": user.organization_id
                },
                "session_info": {
                    "strategy_used": session_strategy,
                    "existing_sessions": existing_count,
                    "sessions_revoked": session_action.get("sessions_revoked", 0),
                    "total_sessions": new_session_count,
                    "max_sessions": settings.session.max_sessions_per_user
                }
            }
            
        except Exception as e:
            auth_logger.error(
                f"Login error for user {username}: {str(e)}",
                username=username,
                error=str(e),
                traceback=traceback.format_exc(),
                event_type="login_error"
            )
            return {
                "success": False,
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR"
            }
    
    @staticmethod
    def _handle_session_strategy(
        db: Session,
        user: User,
        existing_sessions: List[RefreshToken],
        strategy: str,
        device_info: str = None
    ) -> Dict[str, Any]:
        """Handle different session management strategies"""
        
        if strategy == "allow_multiple":
            return {"allow_login": True}
        
        elif strategy == "replace_all":
            # Revoke all existing sessions
            revoked_count = RefreshTokenService.revoke_all_user_tokens(db, user.id)
            LogoutService._clear_user_redis_cache(user.id)
            LogoutService._clear_user_rate_limits(user.id)
            
            return {
                "allow_login": True,
                "sessions_revoked": revoked_count,
                "action": "replaced_all_sessions"
            }
        
        elif strategy == "replace_same_device":
            # Revoke sessions from same device
            revoked_count = 0
            if device_info:
                for session in existing_sessions:
                    if session.device_info == device_info:
                        RefreshTokenService.revoke_token(db, session.token_hash)
                        revoked_count += 1
            
            return {
                "allow_login": True,
                "sessions_revoked": revoked_count,
                "action": "replaced_same_device_sessions"
            }
        
        elif strategy == "deny_if_exists":
            if existing_sessions:
                return {
                    "allow_login": False,
                    "error": "User already has active sessions. Please logout first.",
                    "error_code": "SESSION_EXISTS"
                }
            return {"allow_login": True}
        
        elif strategy == "limit_sessions":
            max_sessions = settings.session.max_sessions_per_user
            
            if len(existing_sessions) >= max_sessions:
                # Revoke oldest sessions to make room
                sessions_to_revoke = len(existing_sessions) - max_sessions + 1
                revoked_count = 0
                
                # Sort by creation date and revoke oldest
                sorted_sessions = sorted(existing_sessions, key=lambda x: x.created_at)
                for session in sorted_sessions[:sessions_to_revoke]:
                    RefreshTokenService.revoke_token(db, session.token_hash)
                    revoked_count += 1
                
                return {
                    "allow_login": True,
                    "sessions_revoked": revoked_count,
                    "action": "limited_sessions"
                }
            
            return {"allow_login": True}
        
        else:
            return {"allow_login": True}  # Default to allow
    
    @staticmethod
    def get_user_session_info(db: Session, user_id: int) -> Dict[str, Any]:
        """Get comprehensive session information for a user"""
        try:
            sessions = RefreshTokenService.get_user_tokens(db, user_id)
            
            session_info = []
            for session in sessions:
                session_info.append({
                    "id": session.id,
                    "device_info": session.device_info,
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                    "created_at": session.created_at.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                    "is_current": False  # Would need to compare with current token
                })
            
            return {
                "user_id": user_id,
                "total_sessions": len(sessions),
                "sessions": session_info,
                "max_sessions": settings.session.max_sessions_per_user
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting session info for user {user_id}: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="session_info_error"
            )
            return {"error": "Failed to get session information"}
    
    @staticmethod
    def revoke_other_sessions(db: Session, user_id: int, keep_session_id: int) -> Dict[str, Any]:
        """Revoke all sessions except the specified one"""
        try:
            sessions = RefreshTokenService.get_user_tokens(db, user_id)
            revoked_count = 0
            
            for session in sessions:
                if session.id != keep_session_id:
                    RefreshTokenService.revoke_token(db, session.token_hash)
                    revoked_count += 1
            
            # Clear Redis cache for revoked sessions
            LogoutService._clear_user_redis_cache(user_id)
            LogoutService._clear_user_rate_limits(user_id)
            
            auth_logger.info(
                f"Revoked {revoked_count} other sessions for user {user_id}",
                user_id=user_id,
                sessions_revoked=revoked_count,
                kept_session_id=keep_session_id,
                event_type="revoke_other_sessions"
            )
            
            return {
                "success": True,
                "sessions_revoked": revoked_count,
                "kept_session_id": keep_session_id
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error revoking other sessions for user {user_id}: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="revoke_other_sessions_error"
            )
            return {"success": False, "error": str(e)}

# Add session settings to config if not exists
class SessionSettings:
    """Session management settings"""
    max_sessions_per_user: int = 5
    allow_multiple_sessions: bool = True
    auto_revoke_old_sessions: bool = True
    session_timeout_hours: int = 24
