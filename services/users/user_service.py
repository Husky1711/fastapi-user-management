from sqlalchemy.orm import Session
from models.user_model import User
from utils.database import get_db
from typing import Optional, List, Dict, Any
from datetime import datetime
from utils.jwt_config import get_password_hash, verify_password
import secrets
import string
from schemas.login import RoleHierarchyValidator
from utils.loggers import auth_logger

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
    
    @staticmethod
    def generate_secure_password(length: int = 12) -> str:
        """Generate a secure random password"""
        # Define character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special_chars = "!@#$%^&*"
        
        # Ensure at least one character from each set
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(special_chars)
        ]
        
        # Fill the rest with random characters
        all_chars = lowercase + uppercase + digits + special_chars
        for _ in range(length - 4):
            password.append(secrets.choice(all_chars))
        
        # Shuffle the password
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)
    
    @staticmethod
    def create_user_by_admin(db: Session, creator_user: User, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new user by admin with proper validation and permissions
        
        Args:
            db: Database session
            creator_user: User who is creating the new user
            user_data: Dictionary containing user creation data
            
        Returns:
            Dictionary with creation result
        """
        try:
            # Extract data from user_data
            username = user_data.get('username')
            email = user_data.get('email')
            password = user_data.get('password')
            role = user_data.get('role', 'user')
            organization_id = user_data.get('organization_id')
            phone_number = user_data.get('phone_number')
            auto_generate_password = user_data.get('auto_generate_password', True)
            
            # Validate creator permissions
            if not RoleHierarchyValidator.can_create_role(creator_user.role, role):
                return {
                    "success": False,
                    "error": f"Role '{creator_user.role}' cannot create users with role '{role}'",
                    "allowed_roles": RoleHierarchyValidator.get_allowed_roles(creator_user.role)
                }
            
            # Check if username already exists
            if UserService.check_username_exists(db, username):
                return {
                    "success": False,
                    "error": f"Username '{username}' already exists"
                }
            
            # Check if email already exists
            if UserService.check_email_exists(db, email):
                return {
                    "success": False,
                    "error": f"Email '{email}' already exists"
                }
            
            # Handle password
            if auto_generate_password:
                password = UserService.generate_secure_password()
            elif not password:
                return {
                    "success": False,
                    "error": "Password is required when auto_generate_password is False"
                }
            
            # Handle organization assignment
            if organization_id is None:
                # Inherit from creator (unless creator is super_admin)
                if creator_user.role == "super_admin":
                    return {
                        "success": False,
                        "error": "Super admin must specify organization_id"
                    }
                organization_id = creator_user.organization_id
            
            # Validate organization access (super_admin can create in any org)
            if creator_user.role != "super_admin" and organization_id != creator_user.organization_id:
                return {
                    "success": False,
                    "error": f"Cannot create user in organization {organization_id}. Access denied."
                }
            
            # Create the user
            hashed_password = get_password_hash(password)
            new_user = User(
                username=username,
                password=hashed_password,
                email=email,
                role=role,
                organization_id=organization_id,
                phone_number=phone_number or "0000000000",
                status="active"
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            # Log successful creation
            auth_logger.info(
                f"User created by admin: {creator_user.username} created user: {username}",
                creator_id=creator_user.id,
                creator_username=creator_user.username,
                created_user_id=new_user.id,
                created_username=new_user.username,
                created_role=new_user.role,
                organization_id=organization_id,
                event_type="admin_user_creation"
            )
            
            return {
                "success": True,
                "user": new_user,
                "generated_password": password if auto_generate_password else None,
                "message": f"User '{username}' created successfully"
            }
            
        except Exception as e:
            # Log error
            auth_logger.error(
                f"Error creating user by admin: {str(e)}",
                creator_id=creator_user.id,
                creator_username=creator_user.username,
                error=str(e),
                event_type="admin_user_creation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to create user: {str(e)}"
            }
