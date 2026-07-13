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

router = APIRouter(prefix="/api/v1", tags=["API Keys"])

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
    current_user: User = Depends(require_permission("api_keys:read")),
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
    request: Request,
    current_user: User = Depends(require_permission("api_keys:create")),
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
        AuditLogService.log_user_action(
            db=db,
            user_id=current_user.id,
            action="create",
            resource_type="api_key",
            resource_id=result.get("api_key_id"),
            new_values={"key_name": body.key_name, "user_id": target_user.id},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
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
    request: Request,
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
        AuditLogService.log_user_action(
            db=db,
            user_id=current_user.id,
            action="update",
            resource_type="api_key",
            resource_id=api_key_id,
            new_values=body.dict(exclude_unset=True),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
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
    request: Request,
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
        AuditLogService.log_user_action(
            db=db,
            user_id=current_user.id,
            action="delete",
            resource_type="api_key",
            resource_id=api_key_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
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

