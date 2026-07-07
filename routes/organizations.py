from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from schemas.organizations import (
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationMutationResponse,
    OrganizationResponse,
    OrganizationUpdateRequest,
)
from services.auth import AuthService
from services.users.organization_service import OrganizationService
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency

router = APIRouter(prefix="/api/v1", tags=["Organizations"])
security = HTTPBearer()


def require_super_admin(db: Session, token: str):
    user = AuthService.get_current_user(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return user


@router.get("/organizations", response_model=OrganizationListResponse)
async def list_organizations(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """List all organizations (super admin only)."""
    require_super_admin(db, credentials.credentials)
    organizations = OrganizationService.list_organizations(db)
    return {"organizations": organizations}


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """Get organization by ID (super admin only)."""
    require_super_admin(db, credentials.credentials)
    organization = OrganizationService.get_organization(db, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.post("/organizations", response_model=OrganizationMutationResponse)
async def create_organization(
    payload: OrganizationCreateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """Create a new organization (super admin only)."""
    require_super_admin(db, credentials.credentials)
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("super_admin")),
):
    """Update an organization (super admin only)."""
    require_super_admin(db, credentials.credentials)
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
