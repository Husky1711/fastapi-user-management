from sqlalchemy.orm import Session
from sqlalchemy import func
from models.user_model import ApiKey, User, Organization
from utils.loggers import auth_logger
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import secrets
import hashlib
import json
import uuid

class ApiKeyService:
    """Service for API key management and authentication"""
    
    # Define standard API key permissions
    STANDARD_API_PERMISSIONS = {
        # Read-only permissions
        "read:users": "Read user information",
        "read:organizations": "Read organization information",
        "read:sessions": "Read session information",
        "read:audit": "Read audit logs",
        "read:reports": "Read reports",
        
        # Write permissions
        "write:users": "Create and update users",
        "write:organizations": "Create and update organizations",
        "write:sessions": "Manage sessions",
        "write:audit": "Write audit logs",
        
        # Admin permissions
        "admin:system": "System administration",
        "admin:security": "Security management",
        "admin:config": "Configuration management",
        
        # Special permissions
        "webhook:send": "Send webhooks",
        "integration:sync": "Data synchronization",
        "backup:create": "Create backups",
        "restore:execute": "Execute restores"
    }
    
    @staticmethod
    def generate_api_key(
        key_name: str,
        permissions: List[str] = None,
        rate_limit_per_minute: int = 100,
        rate_limit_per_hour: int = 1000,
        expires_at: datetime = None
    ) -> Dict[str, str]:
        """
        Generate a new API key
        
        Args:
            key_name: Name/description for the API key
            permissions: List of permissions for the key
            rate_limit_per_minute: Rate limit per minute
            rate_limit_per_hour: Rate limit per hour
            expires_at: When the key expires (optional)
            
        Returns:
            Dictionary with generated key information
        """
        try:
            # Generate secure random key
            key_value = secrets.token_urlsafe(32)
            
            # Generate key prefix for identification
            key_prefix = secrets.token_urlsafe(8)
            
            # Create hash for storage
            key_hash = hashlib.sha256(key_value.encode()).hexdigest()
            
            # Set default permissions if none provided
            if not permissions:
                permissions = ["read:users", "read:organizations"]
            
            # Validate permissions
            for permission in permissions:
                if permission not in ApiKeyService.STANDARD_API_PERMISSIONS:
                    return {
                        "success": False,
                        "error": f"Invalid permission: {permission}"
                    }
            
            return {
                "success": True,
                "key_value": key_value,
                "key_prefix": key_prefix,
                "key_hash": key_hash,
                "permissions": permissions,
                "rate_limit_per_minute": rate_limit_per_minute,
                "rate_limit_per_hour": rate_limit_per_hour,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error generating API key: {str(e)}",
                key_name=key_name,
                error=str(e),
                event_type="api_key_generation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to generate API key: {str(e)}"
            }
    
    @staticmethod
    def create_api_key(
        db: Session,
        user_id: int,
        organization_id: int,
        key_name: str,
        permissions: List[str] = None,
        rate_limit_per_minute: int = 100,
        rate_limit_per_hour: int = 1000,
        expires_at: datetime = None,
        created_by: int = None
    ) -> Dict[str, Any]:
        """
        Create and store a new API key
        
        Args:
            db: Database session
            user_id: ID of the user creating the key
            organization_id: ID of the organization
            key_name: Name/description for the API key
            permissions: List of permissions for the key
            rate_limit_per_minute: Rate limit per minute
            rate_limit_per_hour: Rate limit per hour
            expires_at: When the key expires (optional)
            created_by: ID of the user creating the key
            
        Returns:
            Dictionary with API key creation result
        """
        try:
            # Generate the API key
            key_data = ApiKeyService.generate_api_key(
                key_name=key_name,
                permissions=permissions,
                rate_limit_per_minute=rate_limit_per_minute,
                rate_limit_per_hour=rate_limit_per_hour,
                expires_at=expires_at
            )
            
            if not key_data["success"]:
                return key_data
            
            # Create API key record
            api_key = ApiKey(
                user_id=user_id,
                organization_id=organization_id,
                key_name=key_name,
                key_hash=key_data["key_hash"],
                key_prefix=key_data["key_prefix"],
                permissions=json.dumps(key_data["permissions"]),
                rate_limit_per_minute=rate_limit_per_minute,
                rate_limit_per_hour=rate_limit_per_hour,
                last_used_at=None,
                expires_at=expires_at,
                is_active=True,
                created_at=datetime.utcnow(),
                created_by=created_by or user_id
            )
            
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
            
            # Log API key creation
            auth_logger.info(
                f"API key created: {key_name}",
                api_key_id=api_key.id,
                user_id=user_id,
                organization_id=organization_id,
                permissions=key_data["permissions"],
                event_type="api_key_created"
            )
            
            return {
                "success": True,
                "api_key_id": api_key.id,
                "key_value": key_data["key_value"],  # Only returned once during creation
                "key_prefix": key_data["key_prefix"],
                "permissions": key_data["permissions"],
                "rate_limit_per_minute": rate_limit_per_minute,
                "rate_limit_per_hour": rate_limit_per_hour,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": api_key.created_at.isoformat(),
                "message": f"API key '{key_name}' created successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error creating API key: {str(e)}",
                user_id=user_id,
                key_name=key_name,
                error=str(e),
                event_type="api_key_creation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to create API key: {str(e)}"
            }
    
    @staticmethod
    def validate_api_key(
        db: Session,
        key_value: str,
        required_permission: str = None
    ) -> Dict[str, Any]:
        """
        Validate an API key and check permissions
        
        Args:
            db: Database session
            key_value: The API key value to validate
            required_permission: Required permission to check
            
        Returns:
            Dictionary with validation result
        """
        try:
            # Hash the provided key
            key_hash = hashlib.sha256(key_value.encode()).hexdigest()
            
            # Find the API key
            api_key = db.query(ApiKey)\
                .filter(ApiKey.key_hash == key_hash)\
                .filter(ApiKey.is_active == True)\
                .first()
            
            if not api_key:
                return {
                    "success": False,
                    "error": "Invalid API key",
                    "has_permission": False
                }
            
            # Check if key is expired
            if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                return {
                    "success": False,
                    "error": "API key has expired",
                    "has_permission": False
                }
            
            # Update last used timestamp
            api_key.last_used_at = datetime.utcnow()
            db.commit()
            
            # Parse permissions
            permissions = json.loads(api_key.permissions) if api_key.permissions else []
            
            # Check required permission if specified
            has_permission = True
            if required_permission:
                has_permission = required_permission in permissions
            
            # Log API key usage
            auth_logger.info(
                f"API key validated: {api_key.key_name}",
                api_key_id=api_key.id,
                user_id=api_key.user_id,
                organization_id=api_key.organization_id,
                required_permission=required_permission,
                has_permission=has_permission,
                event_type="api_key_validated"
            )
            
            return {
                "success": True,
                "api_key_id": api_key.id,
                "user_id": api_key.user_id,
                "organization_id": api_key.organization_id,
                "key_name": api_key.key_name,
                "permissions": permissions,
                "has_permission": has_permission,
                "rate_limit_per_minute": api_key.rate_limit_per_minute,
                "rate_limit_per_hour": api_key.rate_limit_per_hour,
                "last_used_at": api_key.last_used_at.isoformat(),
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error validating API key: {str(e)}",
                error=str(e),
                event_type="api_key_validation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to validate API key: {str(e)}",
                "has_permission": False
            }
    
    @staticmethod
    def revoke_api_key(
        db: Session,
        api_key_id: int,
        revoked_by: int = None
    ) -> Dict[str, Any]:
        """
        Revoke an API key
        
        Args:
            db: Database session
            api_key_id: ID of the API key to revoke
            revoked_by: ID of the user revoking the key
            
        Returns:
            Dictionary with revocation result
        """
        try:
            # Find the API key
            api_key = db.query(ApiKey)\
                .filter(ApiKey.id == api_key_id)\
                .filter(ApiKey.is_active == True)\
                .first()
            
            if not api_key:
                return {
                    "success": False,
                    "error": "API key not found or already revoked"
                }
            
            # Revoke the API key
            api_key.is_active = False
            
            db.commit()
            
            # Log API key revocation
            auth_logger.info(
                f"API key revoked: {api_key.key_name}",
                api_key_id=api_key_id,
                user_id=api_key.user_id,
                organization_id=api_key.organization_id,
                revoked_by=revoked_by,
                event_type="api_key_revoked"
            )
            
            return {
                "success": True,
                "message": f"API key '{api_key.key_name}' revoked successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error revoking API key: {str(e)}",
                api_key_id=api_key_id,
                error=str(e),
                event_type="api_key_revocation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to revoke API key: {str(e)}"
            }
    
    @staticmethod
    def get_user_api_keys(
        db: Session,
        user_id: int,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Get all API keys for a user
        
        Args:
            db: Database session
            user_id: ID of the user
            include_inactive: Include inactive keys
            
        Returns:
            Dictionary with user API keys
        """
        try:
            query = db.query(ApiKey)\
                .filter(ApiKey.user_id == user_id)
            
            if not include_inactive:
                query = query.filter(ApiKey.is_active == True)
            
            api_keys = query.order_by(ApiKey.created_at.desc()).all()
            
            keys_data = []
            for key in api_keys:
                keys_data.append({
                    "id": key.id,
                    "key_name": key.key_name,
                    "key_prefix": key.key_prefix,
                    "permissions": json.loads(key.permissions) if key.permissions else [],
                    "rate_limit_per_minute": key.rate_limit_per_minute,
                    "rate_limit_per_hour": key.rate_limit_per_hour,
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                    "is_active": key.is_active,
                    "created_at": key.created_at.isoformat(),
                    "created_by": key.created_by
                })
            
            return {
                "success": True,
                "api_keys": keys_data,
                "total_count": len(keys_data)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting user API keys: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="user_api_keys_retrieval_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get user API keys: {str(e)}"
            }
    
    @staticmethod
    def get_organization_api_keys(
        db: Session,
        organization_id: int,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Get all API keys for an organization
        
        Args:
            db: Database session
            organization_id: ID of the organization
            include_inactive: Include inactive keys
            
        Returns:
            Dictionary with organization API keys
        """
        try:
            query = db.query(ApiKey, User)\
                .join(User, ApiKey.user_id == User.id)\
                .filter(ApiKey.organization_id == organization_id)
            
            if not include_inactive:
                query = query.filter(ApiKey.is_active == True)
            
            api_keys = query.order_by(ApiKey.created_at.desc()).all()
            
            keys_data = []
            for key, user in api_keys:
                keys_data.append({
                    "id": key.id,
                    "key_name": key.key_name,
                    "key_prefix": key.key_prefix,
                    "user_id": key.user_id,
                    "username": user.username,
                    "permissions": json.loads(key.permissions) if key.permissions else [],
                    "rate_limit_per_minute": key.rate_limit_per_minute,
                    "rate_limit_per_hour": key.rate_limit_per_hour,
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                    "is_active": key.is_active,
                    "created_at": key.created_at.isoformat(),
                    "created_by": key.created_by
                })
            
            return {
                "success": True,
                "api_keys": keys_data,
                "total_count": len(keys_data)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting organization API keys: {str(e)}",
                organization_id=organization_id,
                error=str(e),
                event_type="organization_api_keys_retrieval_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get organization API keys: {str(e)}"
            }
    
    @staticmethod
    def update_api_key(
        db: Session,
        api_key_id: int,
        key_name: str = None,
        permissions: List[str] = None,
        rate_limit_per_minute: int = None,
        rate_limit_per_hour: int = None,
        expires_at: datetime = None,
        updated_by: int = None
    ) -> Dict[str, Any]:
        """
        Update an API key
        
        Args:
            db: Database session
            api_key_id: ID of the API key to update
            key_name: New name (optional)
            permissions: New permissions (optional)
            rate_limit_per_minute: New rate limit per minute (optional)
            rate_limit_per_hour: New rate limit per hour (optional)
            expires_at: New expiration time (optional)
            updated_by: ID of the user updating the key
            
        Returns:
            Dictionary with update result
        """
        try:
            # Find the API key
            api_key = db.query(ApiKey)\
                .filter(ApiKey.id == api_key_id)\
                .filter(ApiKey.is_active == True)\
                .first()
            
            if not api_key:
                return {
                    "success": False,
                    "error": "API key not found or inactive"
                }
            
            # Update fields
            if key_name is not None:
                api_key.key_name = key_name
            
            if permissions is not None:
                # Validate permissions
                for permission in permissions:
                    if permission not in ApiKeyService.STANDARD_API_PERMISSIONS:
                        return {
                            "success": False,
                            "error": f"Invalid permission: {permission}"
                        }
                api_key.permissions = json.dumps(permissions)
            
            if rate_limit_per_minute is not None:
                api_key.rate_limit_per_minute = rate_limit_per_minute
            
            if rate_limit_per_hour is not None:
                api_key.rate_limit_per_hour = rate_limit_per_hour
            
            if expires_at is not None:
                api_key.expires_at = expires_at
            
            db.commit()
            
            # Log API key update
            auth_logger.info(
                f"API key updated: {api_key.key_name}",
                api_key_id=api_key_id,
                updated_by=updated_by,
                event_type="api_key_updated"
            )
            
            return {
                "success": True,
                "message": f"API key '{api_key.key_name}' updated successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error updating API key: {str(e)}",
                api_key_id=api_key_id,
                error=str(e),
                event_type="api_key_update_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to update API key: {str(e)}"
            }
    
    @staticmethod
    def get_api_key_statistics(
        db: Session,
        organization_id: int = None,
        user_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Get API key statistics
        
        Args:
            db: Database session
            organization_id: Filter by organization
            
        Returns:
            Dictionary with API key statistics
        """
        try:
            query = db.query(ApiKey)
            
            if organization_id:
                query = query.filter(ApiKey.organization_id == organization_id)
            if user_ids is not None:
                if user_ids:
                    query = query.filter(ApiKey.user_id.in_(user_ids))
                else:
                    query = query.filter(False)
            
            # Get total API keys
            total_keys = query.count()
            
            # Get active API keys
            active_keys = query.filter(ApiKey.is_active == True).count()
            
            # Get expired API keys
            expired_keys = query.filter(ApiKey.expires_at < datetime.utcnow()).count()
            
            # Get recently used keys (last 24 hours)
            recent_usage = query.filter(ApiKey.last_used_at > datetime.utcnow() - timedelta(hours=24)).count()
            
            return {
                "success": True,
                "statistics": {
                    "total_keys": total_keys,
                    "active_keys": active_keys,
                    "inactive_keys": total_keys - active_keys,
                    "expired_keys": expired_keys,
                    "recent_usage": recent_usage
                }
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting API key statistics: {str(e)}",
                organization_id=organization_id,
                error=str(e),
                event_type="api_key_statistics_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get API key statistics: {str(e)}"
            }
    
    @staticmethod
    def cleanup_expired_api_keys(db: Session) -> Dict[str, Any]:
        """
        Clean up expired API keys
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with cleanup result
        """
        try:
            current_time = datetime.utcnow()
            
            # Find expired API keys
            expired_keys = db.query(ApiKey)\
                .filter(ApiKey.expires_at < current_time)\
                .filter(ApiKey.is_active == True)\
                .all()
            
            cleaned_count = 0
            for key in expired_keys:
                key.is_active = False
                cleaned_count += 1
            
            db.commit()
            
            # Log cleanup
            auth_logger.info(
                f"Expired API keys cleaned up: {cleaned_count} keys",
                cleaned_count=cleaned_count,
                event_type="expired_api_keys_cleanup"
            )
            
            return {
                "success": True,
                "message": f"Cleaned up {cleaned_count} expired API keys",
                "cleaned_count": cleaned_count
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error cleaning up expired API keys: {str(e)}",
                error=str(e),
                event_type="expired_api_keys_cleanup_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to cleanup expired API keys: {str(e)}"
            }
    
    @staticmethod
    def get_standard_api_permissions() -> Dict[str, str]:
        """
        Get list of standard API permissions
        
        Returns:
            Dictionary of standard API permissions
        """
        return ApiKeyService.STANDARD_API_PERMISSIONS.copy()
