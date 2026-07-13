"""Consent + security incident API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_permission
from models.user_model import User
from services.core.consent_incident_service import ConsentService, SecurityIncidentService
from services.users.compliance_access import require_user_data_access, resolve_organization_filter
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency

router = APIRouter(prefix="/api/v1", tags=["Compliance"])


class ConsentRequest(BaseModel):
    consent_type: str = Field(..., min_length=2, max_length=100)
    granted: bool = True
    source: Optional[str] = Field(None, max_length=100)
    details: Optional[str] = None


@router.get("/consents", response_model=Dict[str, Any])
async def list_my_consents(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None),
    _: None = Depends(RateLimitDependency.check_rate_limit("consents_list")),
):
    target_id = user_id or current_user.id
    require_user_data_access(db, current_user, target_id)
    return ConsentService.list_for_user(db, target_id)


@router.post("/consents", response_model=Dict[str, Any])
async def upsert_consent(
    body: ConsentRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("consents_write")),
):
    if body.granted:
        return ConsentService.grant(
            db,
            current_user.id,
            body.consent_type,
            organization_id=current_user.organization_id,
            source=body.source or "self_service",
            details=body.details,
        )
    return ConsentService.revoke(
        db,
        current_user.id,
        body.consent_type,
        source=body.source or "self_service",
    )


@router.get("/security/incidents", response_model=Dict[str, Any])
async def list_security_incidents(
    current_user: User = Depends(require_permission("security:incidents")),
    db: Session = Depends(get_db),
    organization_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    incident_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    _: None = Depends(RateLimitDependency.check_rate_limit("security_incidents")),
):
    org_id = resolve_organization_filter(current_user, organization_id)
    if user_id is not None:
        require_user_data_access(db, current_user, user_id)
    return SecurityIncidentService.list_incidents(
        db,
        organization_id=org_id,
        user_id=user_id,
        incident_type=incident_type,
        limit=limit,
    )
