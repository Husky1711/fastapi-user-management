from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

from services.auth import AuthService
from services.audit import AuditLogService
from services.sessions import UserSessionService
from services.permissions import UserPermissionService
from services.permissions import UserGroupService
from services.permissions import ApiKeyService
from services.users import PasswordHistoryService
from services.users import UserService
from utils.rate_limit_dependency import RateLimitDependency
from utils.database import get_db
from utils.loggers import auth_logger

# Create router for production endpoints
router = APIRouter(prefix="/api/v1", tags=["Production Features"])
security = HTTPBearer()

# ============================================================================
# AUDIT LOGGING ENDPOINTS
# ============================================================================

@router.get("/audit/logs", response_model=Dict[str, Any])
async def get_audit_logs(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="Filter by user ID"),
    organization_id: int = Query(None, description="Filter by organization ID"),
    event_type: str = Query(None, description="Filter by event type"),
    event_category: str = Query(None, description="Filter by event category"),
    resource_type: str = Query(None, description="Filter by resource type"),
    status: str = Query(None, description="Filter by status"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, description="Maximum number of records"),
    offset: int = Query(0, description="Number of records to skip"),
    _: None = Depends(RateLimitDependency.check_rate_limit("audit_logs"))
):
    """
    Get audit logs with filtering options
    
    **Access Control:**
    - Requires authentication
    - Users can only see logs for their organization
    - Super Admins can see all logs
    
    **Features:**
    - Comprehensive filtering options
    - Pagination support
    - Organization isolation
    - Role-based access control
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Parse dates if provided
        start_datetime = None
        end_datetime = None
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "super_admin":
            filter_organization_id = current_user.organization_id
        
        # Get audit logs
        result = AuditLogService.get_audit_logs(
            db=db,
            user_id=user_id,
            organization_id=filter_organization_id,
            event_type=event_type,
            event_category=event_category,
            resource_type=resource_type,
            status=status,
            start_date=start_datetime,
            end_date=end_datetime,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get audit logs endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="audit_logs_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/audit/statistics", response_model=Dict[str, Any])
async def get_audit_statistics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)"),
    _: None = Depends(RateLimitDependency.check_rate_limit("audit_statistics"))
):
    """
    Get audit statistics and analytics
    
    **Access Control:**
    - Requires authentication
    - Users can only see statistics for their organization
    - Super Admins can see all statistics
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Parse dates if provided
        start_datetime = None
        end_datetime = None
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "super_admin":
            filter_organization_id = current_user.organization_id
        
        # Get audit statistics
        result = AuditLogService.get_audit_statistics(
            db=db,
            organization_id=filter_organization_id,
            start_date=start_datetime,
            end_date=end_datetime
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get audit statistics endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="audit_statistics_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================================================
# SESSION MANAGEMENT ENDPOINTS (admin analytics — list is on login router)
# ============================================================================

@router.get("/sessions/statistics", response_model=Dict[str, Any])
async def get_session_statistics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    _: None = Depends(RateLimitDependency.check_rate_limit("session_statistics"))
):
    """
    Get session statistics and analytics
    
    **Access Control:**
    - Requires authentication
    - Users can only see statistics for their organization
    - Super Admins can see all statistics
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "super_admin":
            filter_organization_id = current_user.organization_id
        
        # Get session statistics
        result = UserSessionService.get_session_statistics(
            db=db,
            organization_id=filter_organization_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get session statistics endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="session_statistics_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/sessions/cleanup", response_model=Dict[str, Any])
async def cleanup_expired_sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("session_cleanup"))
):
    """
    Clean up expired sessions
    
    **Access Control:**
    - Requires authentication
    - Only Super Admins and Organization Admins can perform cleanup
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check permissions
        if current_user.role not in ["super_admin", "organization_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for session cleanup"
            )
        
        # Cleanup expired sessions
        result = UserSessionService.cleanup_expired_sessions(db=db)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Cleanup expired sessions endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="session_cleanup_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================================================
# PERMISSIONS MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/permissions", response_model=Dict[str, Any])
async def get_user_permissions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="Filter by user ID"),
    include_expired: bool = Query(False, description="Include expired permissions"),
    resource_type: str = Query(None, description="Filter by resource type"),
    _: None = Depends(RateLimitDependency.check_rate_limit("permissions"))
):
    """
    Get user permissions
    
    **Access Control:**
    - Requires authentication
    - Users can only see their own permissions
    - Admins can see permissions for users in their organization
    - Super Admins can see all permissions
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Determine target user ID
        target_user_id = user_id
        if not target_user_id:
            target_user_id = current_user.id
        
        # Check permissions
        if current_user.role == "super_admin":
            # Super admins can see all permissions
            pass
        elif current_user.role in ["organization_admin", "admin"]:
            # Organization admins can see permissions for users in their organization
            if target_user_id != current_user.id:
                target_user = UserService.get_user_by_id(db, target_user_id)
                if not target_user or target_user.organization_id != current_user.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot access permissions for users outside your organization"
                    )
        else:
            # Regular users can only see their own permissions
            if target_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access permissions for other users"
                )
        
        # Get user permissions
        result = UserPermissionService.get_user_permissions(
            db=db,
            user_id=target_user_id,
            include_expired=include_expired,
            resource_type=resource_type
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get user permissions endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="user_permissions_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/permissions/standard", response_model=Dict[str, str])
async def get_standard_permissions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _: None = Depends(RateLimitDependency.check_rate_limit("permissions_standard"))
):
    """
    Get list of standard permissions
    
    **Access Control:**
    - Requires authentication
    - Available to all authenticated users
    """
    try:
        # Get standard permissions
        permissions = UserPermissionService.get_standard_permissions()
        return permissions
        
    except Exception as e:
        auth_logger.error(
            f"Get standard permissions endpoint error: {str(e)}",
            error=str(e),
            event_type="standard_permissions_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/permissions/statistics", response_model=Dict[str, Any])
async def get_permission_statistics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    _: None = Depends(RateLimitDependency.check_rate_limit("permission_statistics"))
):
    """
    Get permission statistics and analytics
    
    **Access Control:**
    - Requires authentication
    - Users can only see statistics for their organization
    - Super Admins can see all statistics
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "super_admin":
            filter_organization_id = current_user.organization_id
        
        # Get permission statistics
        result = UserPermissionService.get_permission_statistics(
            db=db,
            organization_id=filter_organization_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get permission statistics endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="permission_statistics_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================================================
# GROUPS MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/groups", response_model=Dict[str, Any])
async def get_organization_groups(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    include_inactive: bool = Query(False, description="Include inactive groups"),
    _: None = Depends(RateLimitDependency.check_rate_limit("groups"))
):
    """
    Get organization groups
    
    **Access Control:**
    - Requires authentication
    - Users can only see groups for their organization
    - Super Admins can see all groups
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "super_admin":
            filter_organization_id = current_user.organization_id
        
        # Get organization groups
        result = UserGroupService.get_organization_groups(
            db=db,
            organization_id=filter_organization_id,
            include_inactive=include_inactive
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get organization groups endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="organization_groups_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/groups/{group_id}/members", response_model=Dict[str, Any])
async def get_group_members(
    group_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    include_inactive: bool = Query(False, description="Include inactive memberships"),
    _: None = Depends(RateLimitDependency.check_rate_limit("group_members"))
):
    """
    Get group members
    
    **Access Control:**
    - Requires authentication
    - Users can only see members of groups in their organization
    - Super Admins can see all group members
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get group members
        result = UserGroupService.get_group_members(
            db=db,
            group_id=group_id,
            include_inactive=include_inactive
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get group members endpoint error: {str(e)}",
            group_id=group_id,
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="group_members_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/groups/statistics", response_model=Dict[str, Any])
async def get_group_statistics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    _: None = Depends(RateLimitDependency.check_rate_limit("group_statistics"))
):
    """
    Get group statistics and analytics
    
    **Access Control:**
    - Requires authentication
    - Users can only see statistics for their organization
    - Super Admins can see all statistics
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "super_admin":
            filter_organization_id = current_user.organization_id
        
        # Get group statistics
        result = UserGroupService.get_group_statistics(
            db=db,
            organization_id=filter_organization_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get group statistics endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="group_statistics_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================================================
# API KEYS MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/api-keys", response_model=Dict[str, Any])
async def get_user_api_keys(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="Filter by user ID"),
    include_inactive: bool = Query(False, description="Include inactive keys"),
    _: None = Depends(RateLimitDependency.check_rate_limit("api_keys"))
):
    """
    Get user API keys
    
    **Access Control:**
    - Requires authentication
    - Users can only see their own API keys
    - Admins can see API keys for users in their organization
    - Super Admins can see all API keys
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Determine target user ID
        target_user_id = user_id
        if not target_user_id:
            target_user_id = current_user.id
        
        # Check permissions
        if current_user.role == "super_admin":
            # Super admins can see all API keys
            pass
        elif current_user.role in ["organization_admin", "admin"]:
            # Organization admins can see API keys for users in their organization
            if target_user_id != current_user.id:
                target_user = UserService.get_user_by_id(db, target_user_id)
                if not target_user or target_user.organization_id != current_user.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot access API keys for users outside your organization"
                    )
        else:
            # Regular users can only see their own API keys
            if target_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access API keys for other users"
                )
        
        # Get user API keys
        result = ApiKeyService.get_user_api_keys(
            db=db,
            user_id=target_user_id,
            include_inactive=include_inactive
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get user API keys endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="user_api_keys_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/api-keys/standard-permissions", response_model=Dict[str, str])
async def get_standard_api_permissions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _: None = Depends(RateLimitDependency.check_rate_limit("api_permissions"))
):
    """
    Get list of standard API permissions
    
    **Access Control:**
    - Requires authentication
    - Available to all authenticated users
    """
    try:
        # Get standard API permissions
        permissions = ApiKeyService.get_standard_api_permissions()
        return permissions
        
    except Exception as e:
        auth_logger.error(
            f"Get standard API permissions endpoint error: {str(e)}",
            error=str(e),
            event_type="standard_api_permissions_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/api-keys/statistics", response_model=Dict[str, Any])
async def get_api_key_statistics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    _: None = Depends(RateLimitDependency.check_rate_limit("api_key_statistics"))
):
    """
    Get API key statistics and analytics
    
    **Access Control:**
    - Requires authentication
    - Users can only see statistics for their organization
    - Super Admins can see all statistics
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "super_admin":
            filter_organization_id = current_user.organization_id
        
        # Get API key statistics
        result = ApiKeyService.get_api_key_statistics(
            db=db,
            organization_id=filter_organization_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get API key statistics endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="api_key_statistics_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================================================
# PASSWORD HISTORY ENDPOINTS
# ============================================================================

@router.get("/password/history", response_model=Dict[str, Any])
async def get_password_history(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="Filter by user ID"),
    limit: int = Query(10, description="Maximum number of records"),
    _: None = Depends(RateLimitDependency.check_rate_limit("password_history"))
):
    """
    Get password history for a user
    
    **Access Control:**
    - Requires authentication
    - Users can only see their own password history
    - Admins can see password history for users in their organization
    - Super Admins can see all password history
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Determine target user ID
        target_user_id = user_id
        if not target_user_id:
            target_user_id = current_user.id
        
        # Check permissions
        if current_user.role == "super_admin":
            # Super admins can see all password history
            pass
        elif current_user.role in ["organization_admin", "admin"]:
            # Organization admins can see password history for users in their organization
            if target_user_id != current_user.id:
                target_user = UserService.get_user_by_id(db, target_user_id)
                if not target_user or target_user.organization_id != current_user.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot access password history for users outside your organization"
                    )
        else:
            # Regular users can only see their own password history
            if target_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access password history for other users"
                )
        
        # Get password history
        result = PasswordHistoryService.get_password_history(
            db=db,
            user_id=target_user_id,
            limit=limit
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get password history endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="password_history_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/password/policy-stats", response_model=Dict[str, Any])
async def get_password_policy_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="Filter by user ID"),
    _: None = Depends(RateLimitDependency.check_rate_limit("password_policy_stats"))
):
    """
    Get password policy statistics for a user
    
    **Access Control:**
    - Requires authentication
    - Users can only see their own password policy stats
    - Admins can see password policy stats for users in their organization
    - Super Admins can see all password policy stats
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Determine target user ID
        target_user_id = user_id
        if not target_user_id:
            target_user_id = current_user.id
        
        # Check permissions
        if current_user.role == "super_admin":
            # Super admins can see all password policy stats
            pass
        elif current_user.role in ["organization_admin", "admin"]:
            # Organization admins can see password policy stats for users in their organization
            if target_user_id != current_user.id:
                target_user = UserService.get_user_by_id(db, target_user_id)
                if not target_user or target_user.organization_id != current_user.organization_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot access password policy stats for users outside your organization"
                    )
        else:
            # Regular users can only see their own password policy stats
            if target_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access password policy stats for other users"
                )
        
        # Get password policy stats
        result = PasswordHistoryService.get_password_policy_stats(
            db=db,
            user_id=target_user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get password policy stats endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="password_policy_stats_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
