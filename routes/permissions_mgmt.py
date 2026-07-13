from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json

from models.user_model import User
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
    GrantGroupPermissionRequest,
    UpdateApiKeyRequest,
    UpdateGroupRequest,
)
from utils.rate_limit_dependency import RateLimitDependency
from dependencies.auth import CurrentUser, require_permission, require_roles
from utils.database import get_db
from utils.loggers import auth_logger

router = APIRouter(prefix="/api/v1", tags=["Permissions"])

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
    db: Session = Depends(get_db),
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
        permissions = UserPermissionService.get_standard_permissions(db)
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
    current_user: User = Depends(require_permission("permissions:read")),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    _: None = Depends(RateLimitDependency.check_rate_limit("permission_statistics"))
):
    """
    Get permission statistics and analytics
    
    **Access Control:**
    - Staff roles, or a `permissions:read` grant
    - Scoped to the caller's organization unless super_admin
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

