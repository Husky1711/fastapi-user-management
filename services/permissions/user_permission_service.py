from sqlalchemy.orm import Session
from sqlalchemy import func
from models.user_model import UserPermission, User, UserGroup, UserGroupMembership
from utils.loggers import auth_logger
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

class UserPermissionService:
    """Service for granular user permissions management"""
    
    # Define standard permissions
    STANDARD_PERMISSIONS = {
        # User Management
        "users:create": "Create new users",
        "users:read": "View user information",
        "users:update": "Update user information",
        "users:delete": "Delete users",
        "users:list": "List all users",
        
        # Organization Management
        "organizations:create": "Create new organizations",
        "organizations:read": "View organization information",
        "organizations:update": "Update organization information",
        "organizations:delete": "Delete organizations",
        "organizations:list": "List all organizations",
        
        # Session Management
        "sessions:read": "View user sessions",
        "sessions:revoke": "Revoke user sessions",
        "sessions:list": "List all sessions",
        
        # Audit & Logs
        "audit:read": "View audit logs",
        "audit:export": "Export audit logs",
        "audit:statistics": "View audit statistics",
        
        # API Management
        "api_keys:create": "Create API keys",
        "api_keys:read": "View API keys",
        "api_keys:update": "Update API keys",
        "api_keys:delete": "Delete API keys",
        "api_keys:list": "List API keys",
        
        # System Administration
        "system:config": "Modify system configuration",
        "system:maintenance": "Perform system maintenance",
        "system:backup": "Create system backups",
        "system:restore": "Restore system backups",
        
        # Reports & Analytics
        "reports:generate": "Generate reports",
        "reports:export": "Export reports",
        "analytics:view": "View analytics dashboard",
        
        # Security
        "security:monitor": "Monitor security events",
        "security:alerts": "Manage security alerts",
        "security:incidents": "Handle security incidents"
    }
    
    @staticmethod
    def grant_permission(
        db: Session,
        user_id: int,
        permission_name: str,
        resource_type: str = None,
        resource_id: int = None,
        granted_by: int = None,
        expires_at: datetime = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Grant a permission to a user
        
        Args:
            db: Database session
            user_id: ID of the user to grant permission to
            permission_name: Name of the permission
            resource_type: Type of resource (optional)
            resource_id: ID of specific resource (optional)
            granted_by: ID of user granting the permission
            expires_at: When the permission expires (optional)
            metadata: Additional metadata
            
        Returns:
            Dictionary with grant result
        """
        try:
            # Check if permission already exists
            existing = db.query(UserPermission)\
                .filter(UserPermission.user_id == user_id)\
                .filter(UserPermission.permission_name == permission_name)\
                .filter(UserPermission.resource_type == resource_type)\
                .filter(UserPermission.resource_id == resource_id)\
                .filter(UserPermission.is_active == True)\
                .first()
            
            if existing:
                return {
                    "success": False,
                    "error": "Permission already exists for this user and resource"
                }
            
            # Create new permission
            permission = UserPermission(
                user_id=user_id,
                permission_name=permission_name,
                resource_type=resource_type,
                resource_id=resource_id,
                granted_by=granted_by,
                granted_at=datetime.utcnow(),
                expires_at=expires_at,
                is_active=True
            )
            
            db.add(permission)
            db.commit()
            db.refresh(permission)
            
            # Log permission grant
            auth_logger.info(
                f"Permission granted: {permission_name} to user {user_id}",
                user_id=user_id,
                permission_name=permission_name,
                resource_type=resource_type,
                resource_id=resource_id,
                granted_by=granted_by,
                event_type="permission_granted"
            )
            
            return {
                "success": True,
                "permission_id": permission.id,
                "message": f"Permission '{permission_name}' granted successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error granting permission: {str(e)}",
                user_id=user_id,
                permission_name=permission_name,
                error=str(e),
                event_type="permission_grant_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to grant permission: {str(e)}"
            }
    
    @staticmethod
    def revoke_permission(
        db: Session,
        user_id: int,
        permission_name: str,
        resource_type: str = None,
        resource_id: int = None,
        revoked_by: int = None
    ) -> Dict[str, Any]:
        """
        Revoke a permission from a user
        
        Args:
            db: Database session
            user_id: ID of the user to revoke permission from
            permission_name: Name of the permission
            resource_type: Type of resource (optional)
            resource_id: ID of specific resource (optional)
            revoked_by: ID of user revoking the permission
            
        Returns:
            Dictionary with revoke result
        """
        try:
            # Find the permission
            permission = db.query(UserPermission)\
                .filter(UserPermission.user_id == user_id)\
                .filter(UserPermission.permission_name == permission_name)\
                .filter(UserPermission.resource_type == resource_type)\
                .filter(UserPermission.resource_id == resource_id)\
                .filter(UserPermission.is_active == True)\
                .first()
            
            if not permission:
                return {
                    "success": False,
                    "error": "Permission not found or already revoked"
                }
            
            # Revoke the permission
            permission.is_active = False
            permission.expires_at = datetime.utcnow()
            
            db.commit()
            
            # Log permission revocation
            auth_logger.info(
                f"Permission revoked: {permission_name} from user {user_id}",
                user_id=user_id,
                permission_name=permission_name,
                resource_type=resource_type,
                resource_id=resource_id,
                revoked_by=revoked_by,
                event_type="permission_revoked"
            )
            
            return {
                "success": True,
                "message": f"Permission '{permission_name}' revoked successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error revoking permission: {str(e)}",
                user_id=user_id,
                permission_name=permission_name,
                error=str(e),
                event_type="permission_revoke_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to revoke permission: {str(e)}"
            }
    
    @staticmethod
    def check_permission(
        db: Session,
        user_id: int,
        permission_name: str,
        resource_type: str = None,
        resource_id: int = None
    ) -> Dict[str, Any]:
        """
        Check if a user has a specific permission
        
        Args:
            db: Database session
            user_id: ID of the user
            permission_name: Name of the permission to check
            resource_type: Type of resource (optional)
            resource_id: ID of specific resource (optional)
            
        Returns:
            Dictionary with permission check result
        """
        try:
            # Check direct permissions
            permission = db.query(UserPermission)\
                .filter(UserPermission.user_id == user_id)\
                .filter(UserPermission.permission_name == permission_name)\
                .filter(UserPermission.resource_type == resource_type)\
                .filter(UserPermission.resource_id == resource_id)\
                .filter(UserPermission.is_active == True)\
                .filter(UserPermission.expires_at > datetime.utcnow())\
                .first()
            
            if permission:
                return {
                    "success": True,
                    "has_permission": True,
                    "permission_type": "direct",
                    "granted_at": permission.granted_at.isoformat(),
                    "expires_at": permission.expires_at.isoformat() if permission.expires_at else None
                }
            
            # Check group permissions
            group_permissions = db.query(UserPermission)\
                .join(UserGroupMembership, UserPermission.user_id == UserGroupMembership.user_id)\
                .filter(UserGroupMembership.user_id == user_id)\
                .filter(UserGroupMembership.is_active == True)\
                .filter(UserPermission.permission_name == permission_name)\
                .filter(UserPermission.resource_type == resource_type)\
                .filter(UserPermission.resource_id == resource_id)\
                .filter(UserPermission.is_active == True)\
                .filter(UserPermission.expires_at > datetime.utcnow())\
                .first()
            
            if group_permissions:
                return {
                    "success": True,
                    "has_permission": True,
                    "permission_type": "group",
                    "granted_at": group_permissions.granted_at.isoformat(),
                    "expires_at": group_permissions.expires_at.isoformat() if group_permissions.expires_at else None
                }
            
            return {
                "success": True,
                "has_permission": False,
                "permission_type": None
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error checking permission: {str(e)}",
                user_id=user_id,
                permission_name=permission_name,
                error=str(e),
                event_type="permission_check_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to check permission: {str(e)}"
            }
    
    @staticmethod
    def get_user_permissions(
        db: Session,
        user_id: int,
        include_expired: bool = False,
        resource_type: str = None
    ) -> Dict[str, Any]:
        """
        Get all permissions for a user
        
        Args:
            db: Database session
            user_id: ID of the user
            include_expired: Include expired permissions
            resource_type: Filter by resource type
            
        Returns:
            Dictionary with user permissions
        """
        try:
            query = db.query(UserPermission)\
                .filter(UserPermission.user_id == user_id)
            
            if not include_expired:
                query = query.filter(UserPermission.expires_at > datetime.utcnow())
            
            if resource_type:
                query = query.filter(UserPermission.resource_type == resource_type)
            
            permissions = query.filter(UserPermission.is_active == True)\
                .order_by(UserPermission.granted_at.desc())\
                .all()
            
            permissions_data = []
            for perm in permissions:
                permissions_data.append({
                    "id": perm.id,
                    "permission_name": perm.permission_name,
                    "resource_type": perm.resource_type,
                    "resource_id": perm.resource_id,
                    "granted_by": perm.granted_by,
                    "granted_at": perm.granted_at.isoformat(),
                    "expires_at": perm.expires_at.isoformat() if perm.expires_at else None,
                    "is_active": perm.is_active
                })
            
            return {
                "success": True,
                "permissions": permissions_data,
                "total_count": len(permissions_data)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting user permissions: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="user_permissions_retrieval_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get user permissions: {str(e)}"
            }
    
    @staticmethod
    def get_permission_statistics(
        db: Session,
        organization_id: int = None,
        user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Get permission statistics
        
        Args:
            db: Database session
            organization_id: Filter by organization
            
        Returns:
            Dictionary with permission statistics
        """
        try:
            query = db.query(UserPermission)
            
            if organization_id or user_ids is not None:
                query = query.join(User, UserPermission.user_id == User.id)
                if organization_id:
                    query = query.filter(User.organization_id == organization_id)
                if user_ids is not None:
                    if user_ids:
                        query = query.filter(UserPermission.user_id.in_(user_ids))
                    else:
                        query = query.filter(False)
            
            # Get total permissions
            total_permissions = query.count()
            
            # Get active permissions
            active_permissions = query.filter(UserPermission.is_active == True).count()
            
            # Get permissions by type
            permission_types = query.with_entities(
                UserPermission.permission_name, func.count(UserPermission.id)
            ).group_by(UserPermission.permission_name).all()
            
            # Get permissions by resource type
            resource_types = query.with_entities(
                UserPermission.resource_type, func.count(UserPermission.id)
            ).group_by(UserPermission.resource_type).all()
            
            return {
                "success": True,
                "statistics": {
                    "total_permissions": total_permissions,
                    "active_permissions": active_permissions,
                    "inactive_permissions": total_permissions - active_permissions,
                    "permission_types": dict(permission_types),
                    "resource_types": dict(resource_types)
                }
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting permission statistics: {str(e)}",
                organization_id=organization_id,
                error=str(e),
                event_type="permission_statistics_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get permission statistics: {str(e)}"
            }
    
    @staticmethod
    def cleanup_expired_permissions(db: Session) -> Dict[str, Any]:
        """
        Clean up expired permissions
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with cleanup result
        """
        try:
            current_time = datetime.utcnow()
            
            # Find expired permissions
            expired_permissions = db.query(UserPermission)\
                .filter(UserPermission.expires_at < current_time)\
                .filter(UserPermission.is_active == True)\
                .all()
            
            cleaned_count = 0
            for permission in expired_permissions:
                permission.is_active = False
                cleaned_count += 1
            
            db.commit()
            
            # Log cleanup
            auth_logger.info(
                f"Expired permissions cleaned up: {cleaned_count} permissions",
                cleaned_count=cleaned_count,
                event_type="expired_permissions_cleanup"
            )
            
            return {
                "success": True,
                "message": f"Cleaned up {cleaned_count} expired permissions",
                "cleaned_count": cleaned_count
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error cleaning up expired permissions: {str(e)}",
                error=str(e),
                event_type="expired_permissions_cleanup_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to cleanup expired permissions: {str(e)}"
            }
    
    @staticmethod
    def get_standard_permissions() -> Dict[str, str]:
        """
        Get list of standard permissions
        
        Returns:
            Dictionary of standard permissions
        """
        return UserPermissionService.STANDARD_PERMISSIONS.copy()
    
    @staticmethod
    def validate_permission_name(permission_name: str) -> bool:
        """
        Validate permission name format
        
        Args:
            permission_name: Permission name to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Permission name should be in format "resource:action"
        parts = permission_name.split(":")
        if len(parts) != 2:
            return False
        
        resource, action = parts
        if not resource or not action:
            return False
        
        # Check if it's a standard permission
        if permission_name in UserPermissionService.STANDARD_PERMISSIONS:
            return True
        
        # Allow custom permissions with basic validation
        return len(resource) > 0 and len(action) > 0
