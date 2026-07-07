"""Profile and password self-service endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from models.user_model import Organization, User
from routes.auth_common import create_api_router, security
from schemas.login import (
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordResetConfirm,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    UserProfileUpdate,
    UserProfileUpdateResponse,
    UserResponse,
)
from services.audit import AuditLogService
from services.auth import AuthService
from services.users import PasswordResetService, ProfileUpdateService
from utils.database import get_db
from utils.loggers import auth_logger
from utils.production_logging import CorrelationIDGenerator
from utils.rate_limit_dependency import RateLimitDependency

router = create_api_router(tags=["Profile"])

@router.post("/password/reset-request", response_model=PasswordResetResponse)
async def request_password_reset(
    request_data: PasswordResetRequest,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("password_reset_request"))
):
    """
    Request password reset for a user
    
    **Flow:**
    1. User provides email address
    2. System generates secure reset token
    3. Token stored in Redis with 15-minute expiration
    4. Email sent with reset link (TODO: implement email service)
    5. User clicks link and submits new password
    
    **Security Features:**
    - Rate limiting (5 requests per minute)
    - Token expiration (15 minutes)
    - Secure token generation
    - No email enumeration (same response for valid/invalid emails)
    """
    # Generate correlation ID
    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)
    
    try:
        # Use the service to handle password reset request
        result = PasswordResetService.request_password_reset(db, request_data.email)
        
        # Send password reset email if user exists
        if result["success"] and result.get("reset_token"):
            try:
                from utils.email_service import get_email_service
                email_service = get_email_service()
                
                # Get username from database
                user = db.query(User).filter(User.email == request_data.email).first()
                if user:
                    email_service.send_password_reset_email(
                        to_email=request_data.email,
                        reset_token=result["reset_token"],
                        username=user.username
                    )
            except Exception as e:
                auth_logger.error(
                    f"Failed to send password reset email: {str(e)}",
                    email=request_data.email,
                    error=str(e),
                    event_type="password_reset_email_error"
                )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return PasswordResetResponse(
            success=True,
            message=result["message"],
            reset_token=result.get("reset_token"),  # Remove in production
            expires_in_minutes=result["expires_in_minutes"],
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Password reset request endpoint error: {str(e)}",
            email=request_data.email,
            error=str(e),
            correlation_id=correlation_id,
            event_type="password_reset_request_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/password/reset", response_model=PasswordResetConfirmResponse)
async def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("password_reset_confirm"))
):
    """
    Confirm password reset with token and new password
    
    **Flow:**
    1. User submits reset token and new password
    2. System validates token from Redis
    3. System verifies token hasn't expired
    4. System updates user password
    5. System invalidates reset token
    
    **Security Features:**
    - Token validation and expiration check
    - Password complexity requirements
    - Token invalidation after use
    - Rate limiting (5 requests per minute)
    """
    # Generate correlation ID
    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)
    
    try:
        # Use the service to handle password reset confirmation
        result = PasswordResetService.confirm_password_reset(
            db, reset_data.token, reset_data.new_password
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return PasswordResetConfirmResponse(
            success=True,
            message=result["message"],
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Password reset confirmation endpoint error: {str(e)}",
            token=reset_data.token[:8] + "..." if reset_data.token else None,
            error=str(e),
            correlation_id=correlation_id,
            event_type="password_reset_confirm_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/password/reset/validate/{token}")
async def validate_reset_token(token: str):
    """
    Validate a password reset token without consuming it
    
    **Use Case:**
    - Frontend can check if token is valid before showing reset form
    - Prevents users from submitting invalid tokens
    
    **Response:**
    - 200: Token is valid
    - 400: Token is invalid or expired
    """
    try:
        result = PasswordResetService.validate_reset_token(token)
        
        if not result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return {
            "valid": True,
            "email": result["email"],
            "expires_at": result["expires_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Token validation endpoint error: {str(e)}",
            token=token[:8] + "..." if token else None,
            error=str(e),
            event_type="token_validation_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# User Profile Management Endpoints
@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
    # Rate limiting removed - profile endpoint is read-only, no risk of abuse
):
    """
    Get current user's profile information
    
    **Returns:**
    - User ID, username, email, role
    - Organization ID, status, phone number
    - Created date, last login
    """
    try:
        # Get current user from JWT token
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        organization_name = None
        if current_user.organization_id:
            org = db.query(Organization).filter(
                Organization.id == current_user.organization_id
            ).first()
            organization_name = org.name if org else None

        return UserResponse(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
            role=current_user.role,
            organization_id=current_user.organization_id,
            organization_name=organization_name,
            status=current_user.status,
            phone_number=current_user.phone_number,
            created_at=current_user.created_at,
            last_login=current_user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get profile endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="get_profile_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/profile", response_model=UserProfileUpdateResponse)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("profile_update"))
):
    """
    Update current user's profile information
    
    **Updatable Fields:**
    - Email address (with uniqueness check)
    - Phone number
    
    **Security Features:**
    - JWT authentication required
    - Rate limiting (10 requests per minute)
    - Email uniqueness validation
    - Audit logging
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
        
        # Convert Pydantic model to dictionary
        profile_data_dict = profile_data.dict(exclude_unset=True)
        
        # Use the service to update profile
        result = ProfileUpdateService.update_user_profile(db, current_user.id, profile_data_dict)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Invalidate profile cache after update
        from services.core import cache_service
        cache_service.invalidate_user_profile(current_user.id)
        
        # Prepare response
        updated_user = result["user"]
        user_response = UserResponse(
            id=updated_user.id,
            username=updated_user.username,
            email=updated_user.email,
            role=updated_user.role,
            organization_id=updated_user.organization_id,
            status=updated_user.status,
            phone_number=updated_user.phone_number,
            created_at=updated_user.created_at,
            last_login=updated_user.last_login
        )
        
        return UserProfileUpdateResponse(
            success=True,
            message=result["message"],
            user=user_response,
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Update profile endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            correlation_id=correlation_id,
            event_type="update_profile_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/password/change", response_model=PasswordChangeResponse)
async def change_password(
    password_data: PasswordChangeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("password_change"))
):
    """
    Change user password with current password verification
    
    **Flow:**
    1. User provides current password and new password
    2. System verifies current password
    3. System validates new password complexity
    4. System updates password in database
    5. System logs password change event
    
    **Security Features:**
    - Current password verification
    - Password complexity requirements
    - Rate limiting (5 requests per minute)
    - Audit logging
    - Password history check (new password must be different)
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
        
        # Use the service to change password
        result = ProfileUpdateService.change_user_password(
            db, current_user.id, password_data.current_password, password_data.new_password
        )
        
        if not result["success"]:
            # Log failed password change attempt
            AuditLogService.log_user_action(
                db=db,
                user_id=current_user.id,
                action="password_change",
                resource_type="user",
                resource_id=current_user.id,
                status="failure",
                error_message=result["error"],
                request_id=correlation_id,
                correlation_id=correlation_id,
                metadata={
                    "reason": result["error"],
                    "change_type": "self_service"
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Log successful password change
        AuditLogService.log_user_action(
            db=db,
            user_id=current_user.id,
            action="password_change",
            resource_type="user",
            resource_id=current_user.id,
            status="success",
            request_id=correlation_id,
            correlation_id=correlation_id,
            metadata={
                "change_type": "self_service",
                "password_history_saved": True
            }
        )
        
        return PasswordChangeResponse(
            success=True,
            message=result["message"],
            correlation_id=correlation_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Change password endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            correlation_id=correlation_id,
            event_type="change_password_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
