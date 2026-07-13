"""Profile and password self-service endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from models.user_model import Organization, User
from dependencies.auth import CurrentUser
from routes.auth_common import create_api_router
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
from services.users import PasswordResetService, ProfileUpdateService
from config.settings import settings
from utils.database import get_db
from utils.loggers import auth_logger
from utils.production_logging import CorrelationIDGenerator
from utils.rate_limit_dependency import RateLimitDependency

router = create_api_router(tags=["Profile"])

@router.post("/password/reset-request", response_model=PasswordResetResponse)
async def request_password_reset(
    request_data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(
        RateLimitDependency.check_rate_limit("password_reset_request", require_auth=False)
    ),
):
    """
    Request password reset for a user
    
    **Flow:**
    1. User provides email address
    2. System stores a hashed reset token in MySQL (Redis mirrors for latency)
    3. Email sent with reset link when EMAIL__ENABLE_EMAILS is on
    4. User clicks link and submits new password
    
    **Security Features:**
    - Rate limiting (IP + per-email buckets)
    - Token expiration (15 minutes)
    - Secure token generation (only hash stored)
    - No email enumeration (same response for valid/invalid emails)
    """
    # Prefer middleware request ID; fall back to a fresh correlation ID.
    correlation_id = getattr(request.state, "request_id", None) or CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)

    from services.core import RateLimitService
    from utils.redis_config import RedisClient
    from utils.api_errors import APIHTTPException
    import time as _time

    if settings.rate_limit.enable_email_limits and RedisClient.test_connection():
        email_allowed, email_remaining = RateLimitService.check_email_rate_limit(
            str(request_data.email), "password_reset_request"
        )
        if not email_allowed:
            retry_after = RateLimitService.get_retry_after(email_remaining)
            try:
                from utils.metrics import metrics

                metrics.inc_rate_limit()
            except Exception:
                pass
            raise APIHTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for email. Try again in {retry_after} seconds.",
                error_code="RATE_LIMIT_EXCEEDED",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Reset": str(int(_time.time()) + retry_after),
                },
            )

    try:
        client_ip = request.client.host if request.client else None
        result = PasswordResetService.request_password_reset(
            db, request_data.email, requested_ip=client_ip
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return PasswordResetResponse(
            success=True,
            message=result["message"],
            reset_token=result.get("reset_token"),
            expires_in_minutes=result["expires_in_minutes"],
            correlation_id=correlation_id,
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
    _: None = Depends(
        RateLimitDependency.check_rate_limit("password_reset_confirm", require_auth=False)
    ),
):
    """
    Confirm password reset with token and new password
    
    **Flow:**
    1. User submits reset token and new password
    2. System validates hashed token from the database
    3. System verifies token hasn't expired or been used
    4. System updates user password
    5. System marks the reset token as used
    
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
async def validate_reset_token(
    token: str,
    db: Session = Depends(get_db),
):
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
        result = PasswordResetService.validate_reset_token(db, token)
        
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

@router.post("/email/verify")
async def verify_email(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("email_verify", require_auth=False)),
):
    """Confirm email ownership with a verification token."""
    from services.users.email_verification_service import EmailVerificationService

    token = (body or {}).get("token")
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="token is required",
        )
    result = EmailVerificationService.verify_token(db, token)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )
    return result


@router.post("/email/resend-verification")
async def resend_email_verification(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(
        RateLimitDependency.check_rate_limit("email_resend_verification", require_auth=False)
    ),
):
    """Resend verification email (does not reveal whether the account exists)."""
    from services.users.email_verification_service import EmailVerificationService

    email = (body or {}).get("email")
    if not email or not isinstance(email, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email is required",
        )
    return EmailVerificationService.resend_for_email(db, email.strip())


# User Profile Management Endpoints
@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user: CurrentUser,
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
    current_user: CurrentUser,
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
        # Convert Pydantic model to dictionary
        profile_data_dict = profile_data.dict(exclude_unset=True)
        
        # Use the service to update profile
        result = ProfileUpdateService.update_user_profile(db, current_user.id, profile_data_dict)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
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
    current_user: CurrentUser,
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
