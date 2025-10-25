from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
from models.user_model import RefreshToken, User
from utils.jwt_config import create_refresh_token, hash_token, verify_refresh_token
import secrets
import hashlib

class RefreshTokenService:
    @staticmethod
    def create_refresh_token(db: Session, user: User, device_info: str = None, ip_address: str = None, user_agent: str = None) -> tuple[str, RefreshToken]:
        """Create a new refresh token"""
        # Generate a secure random token
        token = secrets.token_urlsafe(32)
        
        # Create refresh token JWT
        refresh_jwt = create_refresh_token({
            "sub": user.username,
            "user_id": user.id,
            "token_id": secrets.token_urlsafe(16)
        })
        
        # Hash the token for storage
        token_hash = hash_token(token)
        
        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Create database record
        db_refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(db_refresh_token)
        db.commit()
        db.refresh(db_refresh_token)
        
        return token, db_refresh_token
    
    @staticmethod
    def verify_refresh_token(db: Session, token: str) -> Optional[User]:
        """Verify a refresh token and return the user"""
        # Hash the provided token
        token_hash = hash_token(token)
        
        # Find the token in database
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        ).first()
        
        if not db_token:
            return None
        
        # Get the user
        user = db.query(User).filter(User.id == db_token.user_id).first()
        return user
    
    @staticmethod
    def revoke_token(db: Session, token: str) -> bool:
        """Revoke a refresh token"""
        token_hash = hash_token(token)
        
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False
        ).first()
        
        if db_token:
            db_token.is_revoked = True
            db_token.revoked_at = datetime.utcnow()
            db.commit()
            return True
        
        return False
    
    @staticmethod
    def revoke_all_user_tokens(db: Session, user_id: int) -> int:
        """Revoke all refresh tokens for a user"""
        count = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        ).update({
            "is_revoked": True,
            "revoked_at": datetime.utcnow()
        })
        
        db.commit()
        return count
    
    @staticmethod
    def get_user_tokens(db: Session, user_id: int) -> List[RefreshToken]:
        """Get all active refresh tokens for a user"""
        return db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        ).all()
    
    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """Clean up expired refresh tokens"""
        count = db.query(RefreshToken).filter(
            RefreshToken.expires_at < datetime.utcnow()
        ).delete()
        
        db.commit()
        return count
    
    @staticmethod
    def rotate_token(db: Session, old_token: str, user: User, device_info: str = None, ip_address: str = None, user_agent: str = None) -> tuple[str, RefreshToken]:
        """Rotate refresh token (revoke old, create new)"""
        # Revoke old token
        RefreshTokenService.revoke_token(db, old_token)
        
        # Create new token
        return RefreshTokenService.create_refresh_token(db, user, device_info, ip_address, user_agent)
