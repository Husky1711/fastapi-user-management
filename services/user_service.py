from sqlalchemy.orm import Session
from models.user_model import User
from utils.database import get_db
from typing import Optional, List
from datetime import datetime
from utils.jwt_config import get_password_hash, verify_password

class UserService:
    @staticmethod
    def create_user(db: Session, username: str, password: str, email: str, phone_number: str = None) -> User:
        """Create a new user in the database"""
        hashed_password = get_password_hash(password)
        db_user = User(
            username=username,
            password=hashed_password,
            email=email,
            phone_number=phone_number or "0000000000"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """Get user by username"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination"""
        return db.query(User).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_users_by_role_and_organization(db: Session, current_user_role: str, current_user_org_id: int, skip: int = 0, limit: int = 100) -> List[User]:
        """Get users filtered by role and organization"""
        query = db.query(User)
        
        if current_user_role == "super_admin":
            # Super admin can see all users from all organizations
            return query.offset(skip).limit(limit).all()
        elif current_user_role == "admin":
            # Admin can see users from their organization only
            return query.filter(User.organization_id == current_user_org_id).offset(skip).limit(limit).all()
        else:
            # Regular user can only see themselves
            return []
    
    @staticmethod
    def get_user_by_role_and_organization(db: Session, user_id: int, current_user_role: str, current_user_org_id: int, current_user_id: int) -> Optional[User]:
        """Get a specific user filtered by role and organization"""
        if current_user_role == "super_admin":
            # Super admin can see any user
            return db.query(User).filter(User.id == user_id).first()
        elif current_user_role == "admin":
            # Admin can see users from their organization
            return db.query(User).filter(
                User.id == user_id,
                User.organization_id == current_user_org_id
            ).first()
        else:
            # Regular user can only see themselves
            if user_id == current_user_id:
                return db.query(User).filter(User.id == user_id).first()
            return None
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        user = UserService.get_user_by_username(db, username)
        if not user:
            return None
        
        if not verify_password(password, user.password):
            return None
        
        return user
    
    @staticmethod
    def check_username_exists(db: Session, username: str) -> bool:
        """Check if username already exists"""
        return UserService.get_user_by_username(db, username) is not None
    
    @staticmethod
    def check_email_exists(db: Session, email: str) -> bool:
        """Check if email already exists"""
        return UserService.get_user_by_email(db, email) is not None
    
    @staticmethod
    def update_last_login(db: Session, user_id: int) -> bool:
        """Update user's last login timestamp"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.last_login = datetime.utcnow()
            db.commit()
            return True
        return False
