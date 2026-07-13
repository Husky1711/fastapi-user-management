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

router = APIRouter(prefix="/api/v1", tags=["Sessions Admin"])

# ============================================================================
# SESSION MANAGEMENT ENDPOINTS (admin analytics — list is on login router)
# ============================================================================

@router.get("/sessions/statistics", response_model=Dict[str, Any])
async def get_session_statistics(
    current_user: User = Depends(require_permission("sessions:read")),
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
    current_user: User = Depends(require_permission("sessions:revoke")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("session_cleanup"))
):
    """
    Clean up expired sessions and related retention tables.
    
    **Access Control:** Super Admin or Organization Admin
    """
    try:
        from services.core.retention_service import RetentionService

        return RetentionService.run_all(db)
        
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


@router.post("/maintenance/cleanup", response_model=Dict[str, Any])
async def run_maintenance_cleanup(
    current_user: User = Depends(
        require_permission(
            "system:maintenance",
            allow_roles=frozenset({"super_admin"}),
        )
    ),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("session_cleanup")),
):
    """Super-admin retention purge across sessions, tokens, history, and invites."""
    from services.core.retention_service import RetentionService

    return RetentionService.run_all(db)

