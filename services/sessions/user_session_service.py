"""
Advanced session tracking for compliance analytics (user_sessions table).

Auth/session counts for dashboards use refresh_tokens (see RefreshTokenService).
Each login creates a linked user_sessions row with refresh_token_id set.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from models.user_model import UserSession, User, RefreshToken
from utils.datetime_utc import utc_now
from utils.loggers import auth_logger
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib
import json
import uuid
import re

class UserSessionService:
    """Service for advanced session tracking and management"""

    @staticmethod
    def create_for_refresh_token(
        db: Session,
        user_id: int,
        refresh_token_row: RefreshToken,
        access_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> Dict[str, Any]:
        """Create a compliance analytics session linked to a refresh token row."""
        ua = user_agent or refresh_token_row.user_agent or "Unknown"
        ip = ip_address or refresh_token_row.ip_address
        parsed_ua = UserSessionService.parse_user_agent(ua)
        device_fingerprint = UserSessionService.generate_device_fingerprint(ua, ip or "")

        return UserSessionService.create_session(
            db=db,
            user_id=user_id,
            access_token_hash=hashlib.sha256(access_token.encode()).hexdigest(),
            refresh_token_id=refresh_token_row.id,
            device_fingerprint=device_fingerprint,
            device_name=f"{parsed_ua['os_name']} {parsed_ua['device_type']}",
            device_type=parsed_ua["device_type"],
            browser_name=parsed_ua["browser_name"],
            browser_version=parsed_ua["browser_version"],
            os_name=parsed_ua["os_name"],
            os_version=parsed_ua["os_version"],
            ip_address=ip,
            expires_at=refresh_token_row.expires_at,
        )

    @staticmethod
    def deactivate_by_refresh_token_id(
        db: Session,
        refresh_token_id: int,
        reason: str = "logout",
    ) -> int:
        """Deactivate user_sessions rows linked to a refresh token."""
        sessions = (
            db.query(UserSession)
            .filter(
                UserSession.refresh_token_id == refresh_token_id,
                UserSession.is_active == True,
            )
            .all()
        )
        for session in sessions:
            session.is_active = False
            session.last_activity = utc_now()

        if sessions:
            db.commit()

        return len(sessions)

    @staticmethod
    def deactivate_by_refresh_token_ids(
        db: Session,
        refresh_token_ids: List[int],
        reason: str = "revoke",
        *,
        commit: bool = True,
    ) -> int:
        """Deactivate user_sessions rows linked to multiple refresh tokens."""
        if not refresh_token_ids:
            return 0

        sessions = (
            db.query(UserSession)
            .filter(
                UserSession.refresh_token_id.in_(refresh_token_ids),
                UserSession.is_active == True,
            )
            .all()
        )
        for session in sessions:
            session.is_active = False
            session.last_activity = utc_now()

        if sessions and commit:
            db.commit()

        return len(sessions)
    
    @staticmethod
    def create_session(
        db: Session,
        user_id: int,
        access_token_hash: str = None,
        refresh_token_id: int = None,
        device_fingerprint: str = None,
        device_name: str = None,
        device_type: str = None,
        browser_name: str = None,
        browser_version: str = None,
        os_name: str = None,
        os_version: str = None,
        ip_address: str = None,
        country: str = None,
        city: str = None,
        expires_at: datetime = None
    ) -> Dict[str, Any]:
        """
        Create a new user session
        
        Args:
            db: Database session
            user_id: ID of the user
            access_token_hash: Hash of the access token
            refresh_token_id: ID of the refresh token
            device_fingerprint: Device fingerprint for security
            device_name: Human-readable device name
            device_type: Type of device (mobile, desktop, tablet)
            browser_name: Browser name
            browser_version: Browser version
            os_name: Operating system name
            os_version: Operating system version
            ip_address: IP address
            country: Country location
            city: City location
            expires_at: Session expiration time
            
        Returns:
            Dictionary with session creation result
        """
        try:
            # Generate unique session ID
            session_id = str(uuid.uuid4())
            
            # Set default expiration if not provided
            if not expires_at:
                expires_at = utc_now() + timedelta(hours=24)
            
            # Create session entry
            session = UserSession(
                user_id=user_id,
                session_id=session_id,
                access_token_hash=access_token_hash,
                refresh_token_id=refresh_token_id,
                device_fingerprint=device_fingerprint,
                device_name=device_name,
                device_type=device_type,
                browser_name=browser_name,
                browser_version=browser_version,
                os_name=os_name,
                os_version=os_version,
                ip_address=ip_address,
                country=country,
                city=city,
                is_active=True,
                last_activity=utc_now(),
                created_at=utc_now(),
                expires_at=expires_at
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            # Log session creation
            auth_logger.info(
                f"User session created: {session_id}",
                user_id=user_id,
                session_id=session_id,
                device_type=device_type,
                ip_address=ip_address,
                event_type="session_created"
            )
            
            return {
                "success": True,
                "session_id": session_id,
                "session": {
                    "id": session.id,
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "device_name": session.device_name,
                    "device_type": session.device_type,
                    "browser_name": session.browser_name,
                    "os_name": session.os_name,
                    "ip_address": session.ip_address,
                    "country": session.country,
                    "city": session.city,
                    "is_active": session.is_active,
                    "last_activity": session.last_activity.isoformat(),
                    "created_at": session.created_at.isoformat(),
                    "expires_at": session.expires_at.isoformat()
                }
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error creating user session: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="session_creation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to create session: {str(e)}"
            }
    
    @staticmethod
    def update_session_activity(
        db: Session,
        session_id: str,
        access_token_hash: str = None
    ) -> Dict[str, Any]:
        """
        Update session activity timestamp
        
        Args:
            db: Database session
            session_id: Session ID to update
            access_token_hash: Optional new access token hash
            
        Returns:
            Dictionary with update result
        """
        try:
            session = db.query(UserSession)\
                .filter(UserSession.session_id == session_id)\
                .filter(UserSession.is_active == True)\
                .first()
            
            if not session:
                return {
                    "success": False,
                    "error": "Session not found or inactive"
                }
            
            # Update activity timestamp
            session.last_activity = utc_now()
            
            # Update access token hash if provided
            if access_token_hash:
                session.access_token_hash = access_token_hash
            
            db.commit()
            
            return {
                "success": True,
                "message": "Session activity updated",
                "last_activity": session.last_activity.isoformat()
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error updating session activity: {str(e)}",
                session_id=session_id,
                error=str(e),
                event_type="session_activity_update_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to update session activity: {str(e)}"
            }
    
    @staticmethod
    def deactivate_session(
        db: Session,
        session_id: str,
        reason: str = "logout"
    ) -> Dict[str, Any]:
        """
        Deactivate a user session
        
        Args:
            db: Database session
            session_id: Session ID to deactivate
            reason: Reason for deactivation
            
        Returns:
            Dictionary with deactivation result
        """
        try:
            session = db.query(UserSession)\
                .filter(UserSession.session_id == session_id)\
                .filter(UserSession.is_active == True)\
                .first()
            
            if not session:
                return {
                    "success": False,
                    "error": "Session not found or already inactive"
                }
            
            # Deactivate session
            session.is_active = False
            session.last_activity = utc_now()
            
            db.commit()
            
            # Log session deactivation
            auth_logger.info(
                f"User session deactivated: {session_id}",
                user_id=session.user_id,
                session_id=session_id,
                reason=reason,
                event_type="session_deactivated"
            )
            
            return {
                "success": True,
                "message": f"Session deactivated: {reason}",
                "session_id": session_id
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error deactivating session: {str(e)}",
                session_id=session_id,
                error=str(e),
                event_type="session_deactivation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to deactivate session: {str(e)}"
            }
    
    @staticmethod
    def deactivate_user_sessions(
        db: Session,
        user_id: int,
        exclude_session_id: str = None,
        reason: str = "logout_all",
        *,
        commit: bool = True,
    ) -> Dict[str, Any]:
        """
        Deactivate all sessions for a user
        
        Args:
            db: Database session
            user_id: User ID
            exclude_session_id: Session ID to exclude from deactivation
            reason: Reason for deactivation
            commit: When False, caller owns the transaction
            
        Returns:
            Dictionary with deactivation result
        """
        try:
            query = db.query(UserSession)\
                .filter(UserSession.user_id == user_id)\
                .filter(UserSession.is_active == True)
            
            if exclude_session_id:
                query = query.filter(UserSession.session_id != exclude_session_id)
            
            sessions = query.all()
            
            deactivated_count = 0
            for session in sessions:
                session.is_active = False
                session.last_activity = utc_now()
                deactivated_count += 1
            
            if commit:
                db.commit()
            
            # Log bulk session deactivation
            auth_logger.info(
                f"User sessions deactivated: {deactivated_count} sessions",
                user_id=user_id,
                deactivated_count=deactivated_count,
                reason=reason,
                event_type="user_sessions_deactivated"
            )
            
            return {
                "success": True,
                "message": f"Deactivated {deactivated_count} sessions",
                "deactivated_count": deactivated_count
            }
            
        except Exception as e:
            if commit:
                db.rollback()
            auth_logger.error(
                f"Error deactivating user sessions: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="user_sessions_deactivation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to deactivate user sessions: {str(e)}"
            }
    
    @staticmethod
    def get_user_sessions(
        db: Session,
        user_id: int,
        include_inactive: bool = False,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get all sessions for a user
        
        Args:
            db: Database session
            user_id: User ID
            include_inactive: Include inactive sessions
            limit: Maximum number of sessions to return
            
        Returns:
            Dictionary with user sessions
        """
        try:
            query = db.query(UserSession)\
                .filter(UserSession.user_id == user_id)
            
            if not include_inactive:
                query = query.filter(UserSession.is_active == True)
            
            sessions = query.order_by(UserSession.last_activity.desc())\
                .limit(limit)\
                .all()
            
            sessions_data = []
            for session in sessions:
                sessions_data.append({
                    "id": session.id,
                    "session_id": session.session_id,
                    "device_name": session.device_name,
                    "device_type": session.device_type,
                    "browser_name": session.browser_name,
                    "browser_version": session.browser_version,
                    "os_name": session.os_name,
                    "os_version": session.os_version,
                    "ip_address": session.ip_address,
                    "country": session.country,
                    "city": session.city,
                    "is_active": session.is_active,
                    "last_activity": session.last_activity.isoformat(),
                    "created_at": session.created_at.isoformat(),
                    "expires_at": session.expires_at.isoformat()
                })
            
            return {
                "success": True,
                "sessions": sessions_data,
                "total_count": len(sessions_data)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting user sessions: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="user_sessions_retrieval_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get user sessions: {str(e)}"
            }
    
    @staticmethod
    def cleanup_expired_sessions(db: Session) -> Dict[str, Any]:
        """
        Clean up expired sessions
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with cleanup result
        """
        try:
            current_time = utc_now()
            
            # Find expired sessions
            expired_sessions = db.query(UserSession)\
                .filter(UserSession.expires_at < current_time)\
                .filter(UserSession.is_active == True)\
                .all()
            
            cleaned_count = 0
            for session in expired_sessions:
                session.is_active = False
                cleaned_count += 1
            
            db.commit()
            
            # Log cleanup
            auth_logger.info(
                f"Expired sessions cleaned up: {cleaned_count} sessions",
                cleaned_count=cleaned_count,
                event_type="expired_sessions_cleanup"
            )
            
            return {
                "success": True,
                "message": f"Cleaned up {cleaned_count} expired sessions",
                "cleaned_count": cleaned_count
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error cleaning up expired sessions: {str(e)}",
                error=str(e),
                event_type="expired_sessions_cleanup_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to cleanup expired sessions: {str(e)}"
            }
    
    @staticmethod
    def get_session_statistics(
        db: Session,
        user_id: int = None,
        user_ids: Optional[List[int]] = None,
        organization_id: int = None
    ) -> Dict[str, Any]:
        """
        Get session statistics
        
        Args:
            db: Database session
            user_id: Filter by user ID
            organization_id: Filter by organization ID
            
        Returns:
            Dictionary with session statistics
        """
        try:
            query = db.query(UserSession)
            needs_user_join = organization_id is not None or user_ids is not None

            if needs_user_join:
                query = query.join(User, UserSession.user_id == User.id)
                if organization_id:
                    query = query.filter(User.organization_id == organization_id)
                if user_ids is not None:
                    if user_ids:
                        query = query.filter(UserSession.user_id.in_(user_ids))
                    else:
                        query = query.filter(False)
            elif user_id:
                query = query.filter(UserSession.user_id == user_id)
            
            # Get total sessions
            total_sessions = query.count()
            
            # Get active sessions
            active_sessions = query.filter(UserSession.is_active == True).count()
            
            # Get sessions by device type
            device_types = query.with_entities(
                UserSession.device_type, func.count(UserSession.id)
            ).group_by(UserSession.device_type).all()
            
            # Get sessions by browser
            browsers = query.with_entities(
                UserSession.browser_name, func.count(UserSession.id)
            ).group_by(UserSession.browser_name).all()
            
            return {
                "success": True,
                "statistics": {
                    "total_sessions": total_sessions,
                    "active_sessions": active_sessions,
                    "inactive_sessions": total_sessions - active_sessions,
                    "device_types": dict(device_types),
                    "browsers": dict(browsers)
                }
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting session statistics: {str(e)}",
                user_id=user_id,
                organization_id=organization_id,
                error=str(e),
                event_type="session_statistics_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get session statistics: {str(e)}"
            }
    
    @staticmethod
    def parse_user_agent(user_agent: str) -> Dict[str, str]:
        """
        Parse user agent string to extract device and browser information
        
        Args:
            user_agent: User agent string
            
        Returns:
            Dictionary with parsed information
        """
        try:
            # Initialize defaults
            device_type = "desktop"
            browser_name = "Unknown"
            browser_version = "Unknown"
            os_name = "Unknown"
            os_version = "Unknown"
            
            # Detect mobile devices
            mobile_patterns = [
                r'Mobile', r'Android', r'iPhone', r'iPad', r'Windows Phone'
            ]
            if any(re.search(pattern, user_agent, re.IGNORECASE) for pattern in mobile_patterns):
                device_type = "mobile"
            
            # Detect tablets
            tablet_patterns = [r'iPad', r'Android.*Tablet']
            if any(re.search(pattern, user_agent, re.IGNORECASE) for pattern in tablet_patterns):
                device_type = "tablet"
            
            # Detect browsers
            browser_patterns = [
                (r'Chrome/(\d+\.\d+)', 'Chrome'),
                (r'Firefox/(\d+\.\d+)', 'Firefox'),
                (r'Safari/(\d+\.\d+)', 'Safari'),
                (r'Edge/(\d+\.\d+)', 'Edge'),
                (r'Opera/(\d+\.\d+)', 'Opera')
            ]
            
            for pattern, browser in browser_patterns:
                match = re.search(pattern, user_agent, re.IGNORECASE)
                if match:
                    browser_name = browser
                    browser_version = match.group(1)
                    break
            
            # Detect operating systems
            os_patterns = [
                (r'Windows NT (\d+\.\d+)', 'Windows'),
                (r'Mac OS X (\d+\.\d+)', 'macOS'),
                (r'Linux', 'Linux'),
                (r'Android (\d+\.\d+)', 'Android'),
                (r'iPhone OS (\d+\.\d+)', 'iOS')
            ]
            
            for pattern, os in os_patterns:
                match = re.search(pattern, user_agent, re.IGNORECASE)
                if match:
                    os_name = os
                    os_version = match.group(1) if match.groups() else "Unknown"
                    break
            
            return {
                "device_type": device_type,
                "browser_name": browser_name,
                "browser_version": browser_version,
                "os_name": os_name,
                "os_version": os_version
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error parsing user agent: {str(e)}",
                user_agent=user_agent,
                error=str(e),
                event_type="user_agent_parsing_error"
            )
            
            return {
                "device_type": "unknown",
                "browser_name": "Unknown",
                "browser_version": "Unknown",
                "os_name": "Unknown",
                "os_version": "Unknown"
            }
    
    @staticmethod
    def generate_device_fingerprint(
        user_agent: str,
        ip_address: str,
        additional_data: str = None
    ) -> str:
        """
        Generate a device fingerprint for security
        
        Args:
            user_agent: User agent string
            ip_address: IP address
            additional_data: Additional data to include
            
        Returns:
            Device fingerprint hash
        """
        try:
            # Parse user agent for consistent fingerprinting
            parsed_ua = UserSessionService.parse_user_agent(user_agent)
            
            # Create fingerprint data
            fingerprint_data = {
                "device_type": parsed_ua["device_type"],
                "browser_name": parsed_ua["browser_name"],
                "os_name": parsed_ua["os_name"],
                "ip_address": ip_address
            }
            
            if additional_data:
                fingerprint_data["additional"] = additional_data
            
            # Generate hash
            fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
            fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
            
            return fingerprint_hash
            
        except Exception as e:
            auth_logger.error(
                f"Error generating device fingerprint: {str(e)}",
                error=str(e),
                event_type="device_fingerprint_error"
            )
            
            # Fallback to simple hash
            fallback_data = f"{user_agent}:{ip_address}"
            return hashlib.sha256(fallback_data.encode()).hexdigest()
