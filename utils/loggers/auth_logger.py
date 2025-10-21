#!/usr/bin/env python3
"""
Authentication Logger
Specialized logger for authentication-related events
"""

from utils.logger import BaseLogger
from typing import Optional

class AuthLogger(BaseLogger):
    """Logger for authentication events"""
    
    def __init__(self):
        super().__init__('auth')
    
    def login_attempt(
        self,
        username: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log login attempt"""
        self.info(
            f"Login attempt for username: {username}",
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="login_attempt"
        )
    
    def login_success(
        self,
        user_id: int,
        username: str,
        ip_address: str,
        duration_ms: float,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log successful login"""
        self.info(
            f"Login successful for user {username} (ID: {user_id})",
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            duration_ms=duration_ms,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="login_success"
        )
    
    def login_failure(
        self,
        username: str,
        ip_address: str,
        reason: str,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log failed login"""
        self.warning(
            f"Login failed for username: {username}, reason: {reason}",
            username=username,
            ip_address=ip_address,
            reason=reason,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="login_failure"
        )
    
    def signup_attempt(
        self,
        username: str,
        email: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log signup attempt"""
        self.info(
            f"Signup attempt for username: {username}, email: {email}",
            username=username,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="signup_attempt"
        )
    
    def signup_success(
        self,
        user_id: int,
        username: str,
        email: str,
        ip_address: str,
        duration_ms: float,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log successful signup"""
        self.info(
            f"Signup successful for user {username} (ID: {user_id})",
            user_id=user_id,
            username=username,
            email=email,
            ip_address=ip_address,
            duration_ms=duration_ms,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="signup_success"
        )
    
    def signup_failure(
        self,
        username: str,
        email: str,
        ip_address: str,
        reason: str,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log failed signup"""
        self.warning(
            f"Signup failed for username: {username}, email: {email}, reason: {reason}",
            username=username,
            email=email,
            ip_address=ip_address,
            reason=reason,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="signup_failure"
        )
    
    def token_created(
        self,
        user_id: int,
        token_type: str,
        ip_address: str,
        device_info: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log token creation"""
        self.info(
            f"Token created for user {user_id}, type: {token_type}",
            user_id=user_id,
            token_type=token_type,
            ip_address=ip_address,
            device_info=device_info,
            correlation_id=correlation_id,
            event_type="token_created"
        )
    
    def token_refreshed(
        self,
        user_id: int,
        ip_address: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log token refresh"""
        self.info(
            f"Token refreshed for user {user_id}",
            user_id=user_id,
            ip_address=ip_address,
            correlation_id=correlation_id,
            event_type="token_refreshed"
        )
    
    def token_revoked(
        self,
        user_id: int,
        token_type: str,
        ip_address: str,
        reason: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log token revocation"""
        self.info(
            f"Token revoked for user {user_id}, type: {token_type}, reason: {reason}",
            user_id=user_id,
            token_type=token_type,
            ip_address=ip_address,
            reason=reason,
            correlation_id=correlation_id,
            event_type="token_revoked"
        )
    
    def invalid_token(
        self,
        token: str,
        ip_address: str,
        reason: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log invalid token attempt"""
        self.warning(
            f"Invalid token attempt, reason: {reason}",
            token_hash=hash(token),  # Log hash instead of actual token
            ip_address=ip_address,
            reason=reason,
            correlation_id=correlation_id,
            event_type="invalid_token"
        )
    
    def password_change(
        self,
        user_id: int,
        ip_address: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log password change"""
        self.info(
            f"Password changed for user {user_id}",
            user_id=user_id,
            ip_address=ip_address,
            correlation_id=correlation_id,
            event_type="password_change"
        )
    
    def account_locked(
        self,
        user_id: int,
        username: str,
        ip_address: str,
        reason: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log account lockout"""
        self.warning(
            f"Account locked for user {username} (ID: {user_id}), reason: {reason}",
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            reason=reason,
            correlation_id=correlation_id,
            event_type="account_locked"
        )

# Create global instance
auth_logger = AuthLogger()
