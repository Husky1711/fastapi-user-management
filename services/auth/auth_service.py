from datetime import timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from utils.jwt_config import create_access_token, create_user_token, verify_token, ACCESS_TOKEN_EXPIRE_MINUTES
from services.user_service import UserService
from .refresh_token_service import RefreshTokenService
from models.user_model import User

class AuthService:
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password"""
        return UserService.authenticate_user(db, username, password)
    
    @staticmethod
    def create_tokens_for_user(db: Session, user: User, device_info: str = None, ip_address: str = None, user_agent: str = None) -> Tuple[str, str]:
        """Create both access and refresh tokens for authenticated user"""
        # Create access token with role and organization info
        user_data = {
            "username": user.username,
            "id": user.id,
            "role": user.role,
            "organization_id": user.organization_id,
            "email": user.email
        }
        access_token = create_user_token(user_data)
        
        # Create refresh token (7 days)
        refresh_token, _ = RefreshTokenService.create_refresh_token(
            db=db,
            user=user,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return access_token, refresh_token
    
    @staticmethod
    def get_current_user(db: Session, token: str) -> Optional[User]:
        """Get current user from JWT token"""
        payload = verify_token(token)
        if payload is None:
            return None
        
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        
        if username is None or user_id is None:
            return None
        
        # Get user from database
        return UserService.get_user_by_id(db, user_id)
    
    @staticmethod
    def register_user(db: Session, username: str, password: str, email: str, phone_number: str = None) -> User:
        """Register a new user"""
        # Check if username already exists
        if UserService.check_username_exists(db, username):
            raise ValueError("Username already exists")
        
        # Check if email already exists
        if UserService.check_email_exists(db, email):
            raise ValueError("Email already exists")
        
        # Create new user
        return UserService.create_user(db, username, password, email, phone_number)
    
    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str, device_info: str = None, ip_address: str = None, user_agent: str = None) -> Tuple[str, str]:
        """Refresh access token using refresh token"""
        # Verify refresh token
        user = RefreshTokenService.verify_refresh_token(db, refresh_token)
        if not user:
            raise ValueError("Invalid or expired refresh token")
        
        # Create new access token with role and organization info
        user_data = {
            "username": user.username,
            "id": user.id,
            "role": user.role,
            "organization_id": user.organization_id,
            "email": user.email
        }
        access_token = create_user_token(user_data)
        
        # Rotate refresh token for security
        new_refresh_token, _ = RefreshTokenService.rotate_token(
            db, refresh_token, user, device_info, ip_address, user_agent
        )
        
        return access_token, new_refresh_token
