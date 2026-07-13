from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, SuperAdminUser, require_permission
from models.user_model import User
from schemas.organizations import (
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationMutationResponse,
    OrganizationResponse,
    OrganizationSettingMutationResponse,
    OrganizationSettingsResponse,
    OrganizationSettingUpsertRequest,
    OrganizationUpdateRequest,
)
from services.users.organization_service import OrganizationService
from services.users.organization_settings_service import OrganizationSettingsService
from utils.api_errors import APIHTTPException
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency

router = APIRouter(prefix="/api/v1", tags=["Organizations"])


def _assert_org_settings_access(user: User, organization_id: int) -> None:
    if user.role == "super_admin":
        return
    if user.role in ("admin", "organization_admin") and user.organization_id == organization_id:
        return
    raise APIHTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot manage settings for this organization",
        error_code="ORG_SETTINGS_DENIED",
    )


@router.get("/organizations", response_model=OrganizationListResponse)
async def list_organizations(
    _current_user: SuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """List all organizations (super admin only)."""
    organizations = OrganizationService.list_organizations(db)
    return {"organizations": organizations}


@router.get("/organizations/me/settings", response_model=OrganizationSettingsResponse)
async def list_my_organization_settings(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("org_settings_me")),
):
    """List settings for the caller's organization (any authenticated user)."""
    return OrganizationSettingsService.list_settings(db, current_user.organization_id)


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: int,
    _current_user: SuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """Get organization by ID (super admin only)."""
    organization = OrganizationService.get_organization(db, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.post("/organizations", response_model=OrganizationMutationResponse)
async def create_organization(
    payload: OrganizationCreateRequest,
    _current_user: SuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """Create a new organization (super admin only)."""
    result = OrganizationService.create_organization(
        db,
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return OrganizationMutationResponse(
        success=True,
        message=result["message"],
        organization=result["organization"],
    )


@router.patch("/organizations/{organization_id}", response_model=OrganizationMutationResponse)
async def update_organization(
    organization_id: int,
    payload: OrganizationUpdateRequest,
    _current_user: SuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """Update an organization (super admin only)."""
    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    result = OrganizationService.update_organization(db, organization_id, updates)
    if not result["success"]:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if result["error"] == "Organization not found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=result["error"])

    return OrganizationMutationResponse(
        success=True,
        message=result["message"],
        organization=result["organization"],
    )


@router.delete("/organizations/{organization_id}", response_model=OrganizationMutationResponse)
async def delete_organization(
    organization_id: int,
    current_user: SuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """Soft-delete an empty organization (super admin only)."""
    result = OrganizationService.soft_delete_organization(
        db, organization_id, deleted_by=current_user.id
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return OrganizationMutationResponse(
        success=True,
        message=result["message"],
        organization=None,
    )


@router.get(
    "/organizations/{organization_id}/settings",
    response_model=OrganizationSettingsResponse,
)
async def list_organization_settings(
    organization_id: int,
    current_user: User = Depends(require_permission("organizations:read")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("org_settings_list")),
):
    """List per-tenant settings (org staff for own org, or super admin)."""
    _assert_org_settings_access(current_user, organization_id)
    return OrganizationSettingsService.list_settings(db, organization_id)


@router.put(
    "/organizations/{organization_id}/settings/{setting_key}",
    response_model=OrganizationSettingMutationResponse,
)
async def upsert_organization_setting(
    organization_id: int,
    setting_key: str,
    payload: OrganizationSettingUpsertRequest,
    current_user: User = Depends(require_permission("organizations:update")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("org_settings_put")),
):
    """Create or update a single organization setting."""
    _assert_org_settings_access(current_user, organization_id)
    result = OrganizationSettingsService.set_setting(
        db,
        organization_id=organization_id,
        key=setting_key,
        value=payload.value,
        updated_by=current_user.id,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return OrganizationSettingMutationResponse(
        success=True,
        organization_id=organization_id,
        setting_key=setting_key,
        setting_value=result["setting_value"],
    )


@router.delete(
    "/organizations/{organization_id}/settings/{setting_key}",
    response_model=OrganizationSettingMutationResponse,
)
async def delete_organization_setting(
    organization_id: int,
    setting_key: str,
    current_user: User = Depends(require_permission("organizations:update")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("org_settings_delete")),
):
    """Delete an organization setting."""
    _assert_org_settings_access(current_user, organization_id)
    result = OrganizationSettingsService.delete_setting(
        db,
        organization_id=organization_id,
        key=setting_key,
        deleted_by=current_user.id,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return OrganizationSettingMutationResponse(
        success=True,
        organization_id=organization_id,
        setting_key=setting_key,
        message="Setting deleted",
    )
