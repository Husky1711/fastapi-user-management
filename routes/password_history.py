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

router = APIRouter(prefix="/api/v1", tags=["Password History"])

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
