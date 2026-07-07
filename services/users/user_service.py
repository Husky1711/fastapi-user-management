from sqlalchemy.orm import Session
from models.user_model import User
from utils.database import get_db
from typing import Optional, List, Dict, Any
from datetime import datetime
from utils.jwt_config import get_password_hash, needs_password_rehash, verify_password
import secrets
import string
import re
from schemas.login import RoleHierarchyValidator
from services.users.role_scope import can_view_user, can_edit_user, filter_users_for_viewer, is_manager_role
from models.user_model import Organization
from utils.loggers import auth_logger

class UserService:
    _USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{3,30}$")
    _EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
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
        if current_user_role == "user":
            return []

        query = filter_users_for_viewer(db.query(User), current_user_role, current_user_org_id)
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_user_by_role_and_organization(db: Session, user_id: int, current_user_role: str, current_user_org_id: int, current_user_id: int) -> Optional[User]:
        """Get a specific user filtered by role and organization"""
        if current_user_role == "super_admin":
            return db.query(User).filter(User.id == user_id).first()

        if current_user_role == "user":
            if user_id == current_user_id:
                return db.query(User).filter(User.id == user_id).first()
            return None

        target = db.query(User).filter(
            User.id == user_id,
            User.organization_id == current_user_org_id,
        ).first()
        if target is None:
            return None
        if not can_view_user(current_user_role, target.role):
            return None
        return target
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        # Get user from database
        user = UserService.get_user_by_username(db, username)
        if not user:
            return None
        
        # Verify password (bcrypt; legacy SHA-256 supported for migration)
        if not verify_password(password, user.password):
            return None

        if needs_password_rehash(user.password):
            user.password = get_password_hash(password)
            db.commit()
        
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
    def serialize_user(db: Session, user: User, include_timestamps: bool = False) -> Dict[str, Any]:
        """Build API-friendly user payload with org and manager details."""
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        manager_username = None
        if user.manager_id:
            manager = db.query(User).filter(User.id == user.manager_id).first()
            manager_username = manager.username if manager else None

        payload: Dict[str, Any] = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
            "organization_name": org.name if org else None,
            "status": user.status,
            "phone_number": user.phone_number,
            "manager_id": user.manager_id,
            "manager_username": manager_username,
        }
        if include_timestamps:
            payload["created_at"] = user.created_at
            payload["last_login"] = user.last_login
        return payload

    @staticmethod
    def validate_manager_assignment(
        db: Session,
        editor: User,
        target_user: User,
        manager_id: Optional[int],
    ) -> Optional[str]:
        if manager_id is None:
            return None
        if manager_id == target_user.id:
            return "User cannot be their own manager"

        manager = db.query(User).filter(User.id == manager_id).first()
        if manager is None:
            return "Manager not found"
        if not is_manager_role(manager.role):
            return "Manager must be an admin or organization admin"
        if manager.organization_id != target_user.organization_id:
            return "Manager must be in the same organization"
        if target_user.role != "user":
            return "Only regular users can have a reporting manager"

        if editor.role == "admin":
            if manager_id != editor.id:
                return "Admins can only assign themselves as manager"
        elif editor.role == "organization_admin":
            if manager.role not in ("admin", "organization_admin"):
                return "Users can only be assigned to an admin or organization admin"
            if not can_view_user(editor.role, manager.role):
                return "Cannot assign this manager"
        elif editor.role != "super_admin":
            return "Insufficient permissions to assign a manager"

        return None

    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username using basic length/character rules"""
        if not username:
            return False
        return bool(UserService._USERNAME_REGEX.match(username))

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email using a lightweight regex"""
        if not email:
            return False
        return bool(UserService._EMAIL_REGEX.match(email))

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
            manager_id = user_data.get('manager_id')
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
                status="active",
            )

            db.add(new_user)
            db.flush()

            if manager_id is not None:
                manager_error = UserService.validate_manager_assignment(
                    db, creator_user, new_user, manager_id
                )
                if manager_error:
                    db.rollback()
                    return {"success": False, "error": manager_error}
                new_user.manager_id = manager_id

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

    @staticmethod
    def update_user_by_admin(
        db: Session,
        editor: User,
        target_user_id: int,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a manageable user with role-based validation."""
        try:
            if editor.role == "user":
                return {"success": False, "error": "Users cannot update other users"}

            target = UserService.get_user_by_role_and_organization(
                db,
                target_user_id,
                editor.role,
                editor.organization_id,
                editor.id,
            )
            if target is None:
                return {"success": False, "error": "User not found or access denied"}

            if not can_edit_user(editor.role, target.role):
                return {
                    "success": False,
                    "error": f"Role '{editor.role}' cannot edit users with role '{target.role}'",
                }

            if target.id == editor.id:
                return {
                    "success": False,
                    "error": "Use profile settings to update your own account",
                }

            new_role = updates.get("role", target.role)
            if "role" in updates and new_role != target.role:
                if not RoleHierarchyValidator.can_create_role(editor.role, new_role):
                    return {
                        "success": False,
                        "error": f"Role '{editor.role}' cannot assign role '{new_role}'",
                        "allowed_roles": RoleHierarchyValidator.get_allowed_roles(editor.role),
                    }

            new_org_id = updates.get("organization_id", target.organization_id)
            if "organization_id" in updates and new_org_id != target.organization_id:
                if editor.role != "super_admin":
                    return {
                        "success": False,
                        "error": "Only super admins can change organization",
                    }

            if "email" in updates and updates["email"] != target.email:
                if UserService.check_email_exists(db, updates["email"]):
                    return {
                        "success": False,
                        "error": f"Email '{updates['email']}' already exists",
                    }
                target.email = updates["email"]

            if "phone_number" in updates:
                target.phone_number = updates["phone_number"] or "0000000000"

            if "status" in updates:
                target.status = updates["status"]

            if "role" in updates:
                target.role = new_role
                if new_role != "user":
                    target.manager_id = None

            if "organization_id" in updates:
                target.organization_id = new_org_id

            effective_role = target.role
            if "manager_id" in updates:
                manager_id = updates["manager_id"]
                if manager_id is not None and effective_role != "user":
                    return {
                        "success": False,
                        "error": "Only regular users can have a reporting manager",
                    }
                manager_error = UserService.validate_manager_assignment(
                    db, editor, target, manager_id
                )
                if manager_error:
                    return {"success": False, "error": manager_error}
                target.manager_id = manager_id

            target.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(target)

            auth_logger.info(
                f"User updated by admin: {editor.username} updated user: {target.username}",
                editor_id=editor.id,
                editor_username=editor.username,
                target_user_id=target.id,
                target_username=target.username,
                updates=list(updates.keys()),
                event_type="admin_user_update",
            )

            return {
                "success": True,
                "user": target,
                "message": f"User '{target.username}' updated successfully",
            }
        except Exception as e:
            db.rollback()
            auth_logger.error(
                f"Error updating user by admin: {str(e)}",
                editor_id=editor.id,
                editor_username=editor.username,
                target_user_id=target_user_id,
                error=str(e),
                event_type="admin_user_update_error",
            )
            return {"success": False, "error": f"Failed to update user: {str(e)}"}
