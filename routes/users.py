"""User listing and admin user management."""

from typing import Any, Dict, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from models.user_model import User
from dependencies.auth import CurrentUser, require_permission
from routes.auth_common import create_api_router
from schemas.login import (
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    AdminUpdateUserRequest,
    AdminUpdateUserResponse,
    UserResponse,
)
from schemas.users import (
    OrganizationUsersListResponse,
    SelfUserListResponse,
    UserListItem,
)
from services.users import UserService
from services.audit import AuditLogService
from utils.database import get_db
from utils.loggers import auth_logger
from utils.production_logging import CorrelationIDGenerator
from utils.rate_limit_dependency import RateLimitDependency

router = create_api_router(tags=["Users"])


def _user_list_item(db: Session, user_obj: User) -> UserListItem:
    row = UserService.serialize_user(db, user_obj)
    return UserListItem(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        role=row["role"],
        status=row["status"],
        phone_number=row["phone_number"],
        manager_id=row["manager_id"],
        manager_username=row["manager_username"],
    )


@router.get(
    "/users",
    response_model=Union[
        OrganizationUsersListResponse,
        SelfUserListResponse,
        Dict[str, OrganizationUsersListResponse],
    ],
    response_model_exclude_unset=True,
)
async def get_all_users(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("users_list")),
):
    """Get users based on current user's role and organization"""
    current_user_role = current_user.role
    current_user_org_id = current_user.organization_id

    users = UserService.get_users_by_role_and_organization(
        db, current_user_role, current_user_org_id
    )

    if current_user_role == "super_admin":
        # Super admin sees all users grouped by organization id (string keys in JSON)
        response: Dict[str, OrganizationUsersListResponse] = {}
        for user in users:
            org_key = str(user.organization_id)
            if org_key not in response:
                response[org_key] = OrganizationUsersListResponse(
                    organization_id=user.organization_id,
                    users=[],
                )
            response[org_key].users.append(_user_list_item(db, user))
        return response

    if current_user_role in ("admin", "organization_admin"):
        return OrganizationUsersListResponse(
            organization_id=current_user_org_id,
            users=[_user_list_item(db, user) for user in users],
        )

    return SelfUserListResponse(user=_user_list_item(db, current_user))

@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("user_detail"))
):
    """Get specific user by ID based on current user's role and organization"""
    from services.core import cache_service

    current_user_role = current_user.role
    current_user_org_id = current_user.organization_id
    current_user_id = current_user.id

    specific_user = UserService.get_user_by_role_and_organization(
        db, user_id, current_user_role, current_user_org_id, current_user_id
    )

    if specific_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or access denied",
        )

    cached_profile = cache_service.get_user_profile(user_id)
    if cached_profile:
        return cached_profile

    user_data = UserService.serialize_user(db, specific_user, include_timestamps=True)
    cache_service.set_user_profile(user_id, user_data)

    return user_data

@router.patch("/users/{user_id}", response_model=AdminUpdateUserResponse)
async def update_user_by_admin(
    user_id: int,
    updates: AdminUpdateUserRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:update")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("profile_update")),
):
    """Update a manageable user (role, status, contact info, reporting manager)."""
    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)

    update_data = updates.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    result = UserService.update_user_by_admin(db, current_user, user_id, update_data)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    updated_user = result["user"]

    AuditLogService.log_user_action(
        db=db,
        user_id=current_user.id,
        action="update",
        resource_type="user",
        resource_id=updated_user.id,
        new_values=update_data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        correlation_id=correlation_id,
        metadata={"target_username": updated_user.username},
    )

    user_response = UserResponse(
        **UserService.serialize_user(db, updated_user, include_timestamps=True),
    )

    return AdminUpdateUserResponse(
        success=True,
        message=result["message"],
        user=user_response,
        correlation_id=correlation_id,
    )
@router.post("/admin/users/create", response_model=AdminCreateUserResponse)
async def create_user_by_admin(
    user_data: AdminCreateUserRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:create")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("admin_create_user"))
):
    """
    Create a new user by admin with proper role-based permissions
    
    **Who can use this endpoint:**
    - Super Admin: Can create users in any organization
    - Organization Admin: Can create users in their organization
    - Admin: Can create users in their organization (with role restrictions)
    - User: Cannot create users (403 Forbidden)
    
    **Role Hierarchy:**
    - Super Admin â†’ Can create: Organization Admin, Admin, User
    - Organization Admin â†’ Can create: Admin, User
    - Admin â†’ Can create: User only
    - User â†’ Cannot create anyone
    
    **Features:**
    - Auto-generate secure passwords
    - Organization inheritance
    - Role-based validation
    - Comprehensive logging
    - Rate limiting
    """
    # Generate correlation ID
    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)
    
    try:
        # Create path is gated by require_permission("users:create") (staff or grant)
        # Convert Pydantic model to dictionary
        user_data_dict = user_data.dict()
        
        # Use the service to create the user
        result = UserService.create_user_by_admin(db, current_user, user_data_dict)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Send welcome email when requested and EMAIL__ENABLE_EMAILS is on
        email_sent = False
        created_user = result["user"]
        if user_data.send_welcome_email:
            try:
                from utils.email_service import get_email_service

                email_service = get_email_service()
                temp_password = result.get("generated_password")
                email_sent = bool(
                    email_service.send_welcome_email(
                        to_email=created_user.email,
                        username=created_user.username,
                        temp_password=temp_password,
                    )
                )
            except Exception as e:
                auth_logger.error(
                    f"Failed to send welcome email: {str(e)}",
                    user_id=created_user.id,
                    email=created_user.email,
                    error=str(e),
                    event_type="welcome_email_error",
                )
        AuditLogService.log_user_action(
            db=db,
            user_id=current_user.id,
            action="create",
            resource_type="user",
            resource_id=created_user.id,
            new_values={
                "username": created_user.username,
                "email": created_user.email,
                "role": created_user.role,
                "organization_id": created_user.organization_id,
            },
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            correlation_id=correlation_id,
        )

        user_response = UserResponse(
            **UserService.serialize_user(db, created_user, include_timestamps=True),
        )
        
        return AdminCreateUserResponse(
            success=True,
            message=result["message"],
            user=user_response,
            generated_password=result.get("generated_password"),
            email_sent=email_sent,
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Admin user creation endpoint error: {str(e)}",
            creator_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            correlation_id=correlation_id,
            event_type="admin_user_creation_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete("/users/{user_id}")
async def soft_delete_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_permission("users:delete")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("admin_create_user")),
):
    """Soft-delete a manageable user (revokes refresh sessions)."""
    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)

    result = UserService.soft_delete_user(db, current_user, user_id)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    AuditLogService.log_user_action(
        db=db,
        user_id=current_user.id,
        action="delete",
        resource_type="user",
        resource_id=user_id,
        new_values={"deleted": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        correlation_id=correlation_id,
    )

    return {
        "success": True,
        "message": result["message"],
        "user_id": user_id,
        "correlation_id": correlation_id,
    }
