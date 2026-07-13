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

router = APIRouter(prefix="/api/v1", tags=["Groups"])

# ============================================================================
# GROUPS MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/groups", response_model=Dict[str, Any])
async def get_organization_groups(
    current_user: User = Depends(require_permission("groups:read")),
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
    current_user: User = Depends(require_permission("groups:read")),
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
    current_user: User = Depends(require_permission("groups:read")),
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
    request: Request,
    current_user: User = Depends(require_permission("groups:create")),
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
        AuditLogService.log_user_action(
            db=db,
            user_id=current_user.id,
            action="create",
            resource_type="group",
            resource_id=result.get("group", {}).get("id"),
            new_values={"name": body.name, "organization_id": org_id},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
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
    request: Request,
    current_user: User = Depends(require_permission("groups:update")),
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
        AuditLogService.log_user_action(
            db=db,
            user_id=current_user.id,
            action="update",
            resource_type="group",
            resource_id=group_id,
            new_values=body.dict(exclude_unset=True),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
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
    request: Request,
    current_user: User = Depends(require_permission("groups:delete")),
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
        AuditLogService.log_user_action(
            db=db,
            user_id=current_user.id,
            action="delete",
            resource_type="group",
            resource_id=group_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
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
    current_user: User = Depends(require_permission("groups:update")),
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
    current_user: User = Depends(require_permission("groups:update")),
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


@router.get("/groups/{group_id}/permissions", response_model=Dict[str, Any])
async def list_group_permissions(
    group_id: int,
    current_user: User = Depends(require_permission("groups:read")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("group_permissions_list")),
):
    """List catalog permissions granted to a group."""
    try:
        require_group_access(db, current_user, group_id)
        result = UserGroupService.list_permissions(db, group_id)
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"],
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"List group permissions error: {str(e)}",
            group_id=group_id,
            error=str(e),
            event_type="group_permissions_list_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/groups/{group_id}/permissions", response_model=Dict[str, Any])
async def grant_group_permission(
    group_id: int,
    body: GrantGroupPermissionRequest,
    current_user: User = Depends(require_permission("permissions:grant")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("group_permissions_grant")),
):
    """Grant a catalog permission to a group."""
    try:
        require_group_manager(current_user)
        require_group_access(db, current_user, group_id)
        result = UserGroupService.grant_permission(
            db=db,
            group_id=group_id,
            permission_name=body.permission_name,
            granted_by=current_user.id,
        )
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Grant group permission error: {str(e)}",
            group_id=group_id,
            error=str(e),
            event_type="group_permission_grant_endpoint_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/groups/{group_id}/permissions",
    response_model=Dict[str, Any],
)
async def revoke_group_permission(
    group_id: int,
    current_user: User = Depends(require_permission("permissions:revoke")),
    db: Session = Depends(get_db),
    permission_name: str = Query(..., description="Catalog permission name, e.g. users:read"),
    _: None = Depends(RateLimitDependency.check_rate_limit("group_permissions_revoke")),
):
    """Revoke a catalog permission from a group."""
    try:
        require_group_manager(current_user)
        require_group_access(db, current_user, group_id)
        result = UserGroupService.revoke_permission(
            db=db,
            group_id=group_id,
            permission_name=permission_name,
            revoked_by=current_user.id,
        )
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Revoke group permission error: {str(e)}",
            group_id=group_id,
            error=str(e),
            event_type="group_permission_revoke_endpoint_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


