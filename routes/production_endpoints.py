from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

from services.audit import AuditLogService
from services.sessions import UserSessionService
from services.permissions import UserPermissionService
from services.permissions import UserGroupService
from services.permissions import ApiKeyService
from services.users import PasswordHistoryService
from services.users.compliance_access import (
    filter_members_by_scope,
    manageable_user_ids,
    require_api_key_record_access,
    require_group_access,
    require_group_manager,
    require_user_data_access,
    resolve_organization_filter,
    scope_user_ids_for_query,
)
from schemas.compliance import (
    AddGroupMemberRequest,
    CreateApiKeyRequest,
    CreateGroupRequest,
    UpdateApiKeyRequest,
    UpdateGroupRequest,
)
from utils.rate_limit_dependency import RateLimitDependency
from dependencies.auth import CurrentUser
from utils.database import get_db
from utils.loggers import auth_logger

# Create router for production endpoints
router = APIRouter(prefix="/api/v1", tags=["Production Features"])


# ============================================================================
# AUDIT LOGGING ENDPOINTS
# ============================================================================

@router.get("/audit/logs", response_model=Dict[str, Any])
async def get_audit_logs(
    current_user: CurrentUser,
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
        # Parse dates if provided
        start_datetime = None
        end_datetime = None
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Apply organization and role-based user scope
        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        scoped_user_ids = scope_user_ids_for_query(db, current_user, user_id)
        
        # Get audit logs
        result = AuditLogService.get_audit_logs(
            db=db,
            user_ids=scoped_user_ids,
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
    current_user: CurrentUser,
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
        # Parse dates if provided
        start_datetime = None
        end_datetime = None
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        scoped_user_ids = scope_user_ids_for_query(db, current_user, None)
        
        # Get audit statistics
        result = AuditLogService.get_audit_statistics(
            db=db,
            organization_id=filter_organization_id,
            user_ids=scoped_user_ids,
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
    current_user: CurrentUser,
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
        # Apply organization filter for non-super admins
        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        scoped_user_ids = scope_user_ids_for_query(db, current_user, None)
        
        # Get session statistics
        result = UserSessionService.get_session_statistics(
            db=db,
            organization_id=filter_organization_id,
            user_ids=scoped_user_ids,
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
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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
        target_user_id = user_id or current_user.id
        require_user_data_access(db, current_user, target_user_id)
        
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
    _current_user: CurrentUser,
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
    current_user: CurrentUser,
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
        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        scoped_user_ids = scope_user_ids_for_query(db, current_user, None)
        
        result = UserPermissionService.get_permission_statistics(
            db=db,
            organization_id=filter_organization_id,
            user_ids=scoped_user_ids,
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
    current_user: CurrentUser,
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
        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        
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
    current_user: CurrentUser,
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
        require_group_access(db, current_user, group_id)
        scoped_user_ids = manageable_user_ids(
            db, current_user.role, current_user.organization_id, current_user.id
        )
        
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

        if "members" in result:
            result["members"] = filter_members_by_scope(result["members"], scoped_user_ids)
        
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
    current_user: CurrentUser,
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
        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        scoped_user_ids = scope_user_ids_for_query(db, current_user, None)
        
        result = UserGroupService.get_group_statistics(
            db=db,
            organization_id=filter_organization_id,
            user_ids=scoped_user_ids,
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

@router.post("/groups", response_model=Dict[str, Any])
async def create_organization_group(
    body: CreateGroupRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("groups_create")),
):
    """Create a user group in the viewer's organization (staff roles only)."""
    try:
        require_group_manager(current_user)

        org_id = body.organization_id if current_user.role == "super_admin" else current_user.organization_id
        if org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="organization_id is required",
            )
        if current_user.role != "super_admin" and body.organization_id not in (None, current_user.organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create groups in another organization",
            )

        result = UserGroupService.create_group(
            db=db,
            organization_id=org_id,
            name=body.name,
            description=body.description,
            created_by=current_user.id,
        )
        if not result["success"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Create group endpoint error: {str(e)}",
            error=str(e),
            event_type="group_create_endpoint_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.patch("/groups/{group_id}", response_model=Dict[str, Any])
async def update_organization_group(
    group_id: int,
    body: UpdateGroupRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("groups_update")),
):
    """Update a user group (staff roles only)."""
    try:
        require_group_manager(current_user)
        require_group_access(db, current_user, group_id)

        result = UserGroupService.update_group(
            db=db,
            group_id=group_id,
            name=body.name,
            description=body.description,
            updated_by=current_user.id,
        )
        if not result["success"]:
            status_code = status.HTTP_404_NOT_FOUND if "not found" in result["error"].lower() else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Update group endpoint error: {str(e)}",
            group_id=group_id,
            error=str(e),
            event_type="group_update_endpoint_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.delete("/groups/{group_id}", response_model=Dict[str, Any])
async def delete_organization_group(
    group_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("groups_delete")),
):
    """Soft-delete a user group (staff roles only)."""
    try:
        require_group_manager(current_user)
        require_group_access(db, current_user, group_id)

        result = UserGroupService.delete_group(
            db=db,
            group_id=group_id,
            deleted_by=current_user.id,
        )
        if not result["success"]:
            status_code = status.HTTP_404_NOT_FOUND if "not found" in result["error"].lower() else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Delete group endpoint error: {str(e)}",
            group_id=group_id,
            error=str(e),
            event_type="group_delete_endpoint_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/groups/{group_id}/members", response_model=Dict[str, Any])
async def add_group_member(
    group_id: int,
    body: AddGroupMemberRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("group_members_add")),
):
    """Add a user to a group (staff roles only)."""
    try:
        require_group_manager(current_user)
        require_group_access(db, current_user, group_id)
        require_user_data_access(db, current_user, body.user_id)

        result = UserGroupService.add_user_to_group(
            db=db,
            group_id=group_id,
            user_id=body.user_id,
            added_by=current_user.id,
            expires_at=body.expires_at,
        )
        if not result["success"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Add group member endpoint error: {str(e)}",
            group_id=group_id,
            error=str(e),
            event_type="group_member_add_endpoint_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.delete("/groups/{group_id}/members/{user_id}", response_model=Dict[str, Any])
async def remove_group_member(
    group_id: int,
    user_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("group_members_remove")),
):
    """Remove a user from a group (staff roles only)."""
    try:
        require_group_manager(current_user)
        require_group_access(db, current_user, group_id)
        require_user_data_access(db, current_user, user_id)

        result = UserGroupService.remove_user_from_group(
            db=db,
            group_id=group_id,
            user_id=user_id,
            removed_by=current_user.id,
        )
        if not result["success"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Remove group member endpoint error: {str(e)}",
            group_id=group_id,
            user_id=user_id,
            error=str(e),
            event_type="group_member_remove_endpoint_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

# ============================================================================
# API KEYS MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/api-keys", response_model=Dict[str, Any])
async def get_user_api_keys(
    current_user: CurrentUser,
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
        target_user_id = user_id or current_user.id
        require_user_data_access(db, current_user, target_user_id)
        
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
    _current_user: CurrentUser,
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
    current_user: CurrentUser,
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
        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        scoped_user_ids = scope_user_ids_for_query(db, current_user, None)
        
        result = ApiKeyService.get_api_key_statistics(
            db=db,
            organization_id=filter_organization_id,
            user_ids=scoped_user_ids,
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

@router.post("/api-keys", response_model=Dict[str, Any])
async def create_user_api_key(
    body: CreateApiKeyRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("api_keys_create")),
):
    """Issue a new API key. Returns the secret once."""
    try:
        target_user_id = body.user_id or current_user.id
        target_user = require_user_data_access(db, current_user, target_user_id)

        result = ApiKeyService.create_api_key(
            db=db,
            user_id=target_user.id,
            organization_id=target_user.organization_id,
            key_name=body.key_name,
            permissions=body.permissions,
            rate_limit_per_minute=body.rate_limit_per_minute,
            rate_limit_per_hour=body.rate_limit_per_hour,
            expires_at=body.expires_at,
            created_by=current_user.id,
        )
        if not result["success"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Create API key endpoint error: {str(e)}",
            error=str(e),
            event_type="api_key_create_endpoint_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.patch("/api-keys/{api_key_id}", response_model=Dict[str, Any])
async def update_user_api_key(
    api_key_id: int,
    body: UpdateApiKeyRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("api_keys_update")),
):
    """Update API key metadata (not the secret)."""
    try:
        require_api_key_record_access(db, current_user, api_key_id)

        result = ApiKeyService.update_api_key(
            db=db,
            api_key_id=api_key_id,
            key_name=body.key_name,
            permissions=body.permissions,
            rate_limit_per_minute=body.rate_limit_per_minute,
            rate_limit_per_hour=body.rate_limit_per_hour,
            expires_at=body.expires_at,
            updated_by=current_user.id,
        )
        if not result["success"]:
            status_code = status.HTTP_404_NOT_FOUND if "not found" in result["error"].lower() else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Update API key endpoint error: {str(e)}",
            api_key_id=api_key_id,
            error=str(e),
            event_type="api_key_update_endpoint_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.delete("/api-keys/{api_key_id}", response_model=Dict[str, Any])
async def revoke_user_api_key(
    api_key_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("api_keys_revoke")),
):
    """Revoke an API key."""
    try:
        require_api_key_record_access(db, current_user, api_key_id)

        result = ApiKeyService.revoke_api_key(
            db=db,
            api_key_id=api_key_id,
            revoked_by=current_user.id,
        )
        if not result["success"]:
            status_code = status.HTTP_404_NOT_FOUND if "not found" in result["error"].lower() else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Revoke API key endpoint error: {str(e)}",
            api_key_id=api_key_id,
            error=str(e),
            event_type="api_key_revoke_endpoint_error",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

# ============================================================================
# PASSWORD HISTORY ENDPOINTS
# ============================================================================

@router.get("/password/history", response_model=Dict[str, Any])
async def get_password_history(
    current_user: CurrentUser,
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
        target_user_id = user_id or current_user.id
        require_user_data_access(db, current_user, target_user_id)
        
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
    current_user: CurrentUser,
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
        target_user_id = user_id or current_user.id
        require_user_data_access(db, current_user, target_user_id)
        
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
