"""User listing and admin user management."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from models.user_model import User
from routes.auth_common import create_api_router, security
from schemas.login import (
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    AdminUpdateUserRequest,
    AdminUpdateUserResponse,
    UserResponse,
)
from services.auth import AuthService
from services.users import UserService
from utils.database import get_db
from utils.loggers import auth_logger
from utils.production_logging import CorrelationIDGenerator
from utils.rate_limit_dependency import RateLimitDependency

router = create_api_router(tags=["Users"])

@router.get("/users")
async def get_all_users(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("users_list"))
):
    """Get users based on current user's role and organization"""
    # Verify JWT token and get user info
    user = AuthService.get_current_user(db, credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Use database user as source of truth (JWT claims can be stale after role changes)
    current_user_role = user.role
    current_user_org_id = user.organization_id
    current_user_id = user.id
    
    # Get users based on role
    users = UserService.get_users_by_role_and_organization(
        db, current_user_role, current_user_org_id
    )
    
    # Format response based on role
    def user_row(user_obj: User) -> Dict[str, Any]:
        row = UserService.serialize_user(db, user_obj)
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "role": row["role"],
            "status": row["status"],
            "phone_number": row["phone_number"],
            "manager_id": row["manager_id"],
            "manager_username": row["manager_username"],
        }

    if current_user_role == "super_admin":
        # Super admin sees all users grouped by organization
        response = {}
        for user in users:
            org_id = user.organization_id
            if org_id not in response:
                response[org_id] = {"organization_id": org_id, "users": []}
            response[org_id]["users"].append(user_row(user))
        return response
    elif current_user_role in ("admin", "organization_admin"):
        # Admins and org admins see manageable users from their organization
        return {
            "organization_id": current_user_org_id,
            "users": [user_row(user) for user in users]
        }
    else:
        # Regular user sees only themselves
        row = user_row(user)
        return {"user": row}

@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("user_detail"))
):
    """Get specific user by ID based on current user's role and organization"""
    # Import cache service
    from services.core import cache_service
    
    # Verify JWT token and get user info
    user = AuthService.get_current_user(db, credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check cache first
    cached_profile = cache_service.get_user_profile(user_id)
    if cached_profile:
        # Return cached profile
        return cached_profile
    
    # Use database user as source of truth (JWT claims can be stale after role changes)
    current_user_role = user.role
    current_user_org_id = user.organization_id
    current_user_id = user.id
    
    # Get specific user based on role
    specific_user = UserService.get_user_by_role_and_organization(
        db, user_id, current_user_role, current_user_org_id, current_user_id
    )
    
    if specific_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or access denied"
        )
    
    # Prepare response data
    user_data = UserService.serialize_user(db, specific_user, include_timestamps=True)
    
    # Cache the profile for future requests
    cache_service.set_user_profile(user_id, user_data)
    
    return user_data

@router.patch("/users/{user_id}", response_model=AdminUpdateUserResponse)
async def update_user_by_admin(
    user_id: int,
    updates: AdminUpdateUserRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("profile_update")),
):
    """Update a manageable user (role, status, contact info, reporting manager)."""
    from services.core import cache_service

    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)

    current_user = AuthService.get_current_user(db, credentials.credentials)
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if current_user.role == "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Users cannot update other users. Admin privileges required.",
        )

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
    cache_service.invalidate_user_profile(updated_user.id)

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
    credentials: HTTPAuthorizationCredentials = Depends(security),
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
        # Get current user from JWT token
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user has permission to create users
        if current_user.role == "user":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Users cannot create other users. Admin privileges required."
            )
        
        # Convert Pydantic model to dictionary
        user_data_dict = user_data.dict()
        
        # Use the service to create the user
        result = UserService.create_user_by_admin(db, current_user, user_data_dict)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Send welcome email to new user
        email_sent = False
        try:
            from utils.email_service import get_email_service
            email_service = get_email_service()
            
            created_user = result["user"]
            temp_password = result.get("generated_password")
            
            email_service.send_welcome_email(
                to_email=created_user.email,
                username=created_user.username,
                temp_password=temp_password
            )
            email_sent = True
        except Exception as e:
            auth_logger.error(
                f"Failed to send welcome email: {str(e)}",
                user_id=created_user.id if 'created_user' in locals() else None,
                email=created_user.email if 'created_user' in locals() else None,
                error=str(e),
                event_type="welcome_email_error"
            )
        
        # Prepare response
        created_user = result["user"]
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
