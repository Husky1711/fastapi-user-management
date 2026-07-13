"""Data retention policy admin API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from dependencies.auth import require_permission
from models.user_model import User
from services.core.data_retention_policy_service import DataRetentionPolicyService
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency

router = APIRouter(prefix="/api/v1", tags=["Retention"])


class RetentionPolicyUpsertRequest(BaseModel):
    retention_days: int = Field(..., ge=1, le=3650)
    is_active: bool = True
    description: Optional[str] = Field(None, max_length=255)


@router.get("/retention/policies", response_model=Dict[str, Any])
async def list_retention_policies(
    current_user: User = Depends(
        require_permission(
            "system:maintenance",
            allow_roles=frozenset({"super_admin"}),
        )
    ),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("retention_policies")),
):
    """List configurable retention policies (super_admin)."""
    return DataRetentionPolicyService.list_policies(db)


@router.put("/retention/policies/{table_name}", response_model=Dict[str, Any])
async def upsert_retention_policy(
    table_name: str,
    body: RetentionPolicyUpsertRequest,
    current_user: User = Depends(
        require_permission(
            "system:maintenance",
            allow_roles=frozenset({"super_admin"}),
        )
    ),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("retention_policies_put")),
):
    """Create or update a retention policy for a table."""
    result = DataRetentionPolicyService.upsert_policy(
        db,
        table_name=table_name,
        retention_days=body.retention_days,
        is_active=body.is_active,
        description=body.description,
        updated_by=current_user.id,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return result
