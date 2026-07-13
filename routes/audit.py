"""Audit log endpoints (extracted from production_endpoints)."""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from dependencies.auth import require_permission
from models.user_model import User
from services.audit import AuditLogService
from services.users.compliance_access import (
    resolve_organization_filter,
    scope_user_ids_for_query,
)
from utils.database import get_db
from utils.loggers import auth_logger
from utils.rate_limit_dependency import RateLimitDependency

router = APIRouter(prefix="/api/v1", tags=["Audit"])


@router.get("/audit/logs", response_model=Dict[str, Any])
async def get_audit_logs(
    current_user: User = Depends(require_permission("audit:read")),
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
    _: None = Depends(RateLimitDependency.check_rate_limit("audit_logs")),
):
    """Get audit logs with filtering options."""
    try:
        start_datetime = None
        end_datetime = None
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        scoped_user_ids = scope_user_ids_for_query(db, current_user, user_id)

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
            offset=offset,
        )
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
            f"Get audit logs endpoint error: {str(e)}",
            user_id=current_user.id if "current_user" in locals() else None,
            error=str(e),
            event_type="audit_logs_endpoint_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/audit/statistics", response_model=Dict[str, Any])
async def get_audit_statistics(
    current_user: User = Depends(require_permission("audit:statistics")),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)"),
    _: None = Depends(RateLimitDependency.check_rate_limit("audit_statistics")),
):
    """Get audit statistics and analytics."""
    try:
        start_datetime = None
        end_datetime = None
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        filter_organization_id = resolve_organization_filter(current_user, organization_id)
        scoped_user_ids = scope_user_ids_for_query(db, current_user, None)

        result = AuditLogService.get_audit_statistics(
            db=db,
            organization_id=filter_organization_id,
            user_ids=scoped_user_ids,
            start_date=start_datetime,
            end_date=end_datetime,
        )
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
            f"Get audit statistics endpoint error: {str(e)}",
            user_id=current_user.id if "current_user" in locals() else None,
            error=str(e),
            event_type="audit_statistics_endpoint_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
