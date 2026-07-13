"""Authentication endpoints: login, signup, refresh, logout."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config.settings import settings
from routes.auth_common import create_api_router, security
from schemas.login import RefreshTokenRequest, UserResponse, UserSigninRequest, UserSignupRequest, Login2FARequest, TwoFactorRequiredResponse
from services.audit import AuditLogService
from services.auth import AuthService, EnhancedLoginService, LogoutService, RefreshTokenService
from services.auth.login_2fa_service import Login2FAService
from services.auth.login_attempt_service import LoginAttemptService
from services.users import UserService
from utils.datetime_utc import utc_now
from utils.api_errors import APIHTTPException
from utils.cookie_auth import (
    build_auth_token_response,
    build_logout_response,
    clear_refresh_cookie,
    get_refresh_token_from_request,
    require_csrf_header,
    resolve_refresh_token,
)
from utils.database import get_db
from utils.loggers import auth_logger
from utils.production_logging import CorrelationIDGenerator
from utils.rate_limit_dependency import RateLimitDependency
from utils.request_ip import get_client_ip

router = create_api_router(tags=["Authentication"])

@router.post("/login")
async def login(
    credentials: UserSigninRequest, 
    request: Request, 
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("login", require_auth=False))
):
    """Login endpoint - returns access and refresh tokens"""
    # Generate correlation ID
    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)
    
    # Get request info
    ip_address = get_client_ip(request)
    user_agent = request.headers.get('user-agent', 'Unknown')
    
    # Log login attempt
    auth_logger.login_attempt(
        username=credentials.username,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    
    try:
        auth_result = LoginAttemptService.authenticate_with_lockout(
            db=db,
            username=credentials.username,
            password=credentials.password,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if not auth_result["success"]:
            if auth_result.get("error_code") == "ACCOUNT_LOCKED":
                lockout_info = auth_result.get("lockout_info") or {}
                auth_logger.login_failure(
                    username=credentials.username,
                    ip_address=ip_address,
                    reason="Account locked",
                    user_agent=user_agent,
                    correlation_id=correlation_id,
                )
                raise APIHTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account locked. Try again after {lockout_info.get('remaining_lockout_minutes', 0)} minutes.",
                    error_code="ACCOUNT_LOCKED",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            if auth_result.get("error_code") == "ACCOUNT_DISABLED":
                auth_logger.login_failure(
                    username=credentials.username,
                    ip_address=ip_address,
                    reason="Account disabled",
                    user_agent=user_agent,
                    correlation_id=correlation_id,
                )
                raise APIHTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is disabled",
                    error_code="ACCOUNT_DISABLED",
                )

            auth_logger.login_failure(
                username=credentials.username,
                ip_address=ip_address,
                reason="Invalid credentials",
                user_agent=user_agent,
                correlation_id=correlation_id,
            )
            raise APIHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                error_code="INVALID_CREDENTIALS",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = auth_result["user"]
        device_info = f"{user_agent}"

        if Login2FAService.enrollment_required(db, user):
            auth_logger.warning(
                "Login blocked: org requires 2FA enrollment",
                user_id=user.id,
                username=user.username,
                ip_address=ip_address,
                correlation_id=correlation_id,
                event_type="login_2fa_enrollment_required",
            )
            raise APIHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Two-factor authentication enrollment is required for this organization",
                error_code="2FA_ENROLLMENT_REQUIRED",
            )

        if Login2FAService.requires_2fa(user):
            challenge_token = Login2FAService.create_challenge(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                device_info=device_info,
            )
            auth_logger.info(
                "2FA challenge issued",
                user_id=user.id,
                username=user.username,
                ip_address=ip_address,
                correlation_id=correlation_id,
                event_type="login_2fa_required",
            )
            return Login2FAService.build_challenge_response(challenge_token)

        # Create both tokens
        access_token, refresh_token = AuthService.create_tokens_for_user(
            db, user, device_info, ip_address, user_agent
        )
        
        # Update last login
        UserService.update_last_login(db, user.id)
        
        # Log successful login
        auth_logger.login_success(
            user_id=user.id,
            username=user.username,
            ip_address=ip_address,
            duration_ms=0,  # Could be calculated if needed
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        
        # Create audit log for successful login
        AuditLogService.log_authentication_event(
            db=db,
            event_type="login",
            user_id=user.id,
            username=user.username,
            email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=correlation_id,
            correlation_id=correlation_id,
            status="success",
            metadata={
                "device_info": device_info,
                "token_type": "access_refresh"
            }
        )
        
        return build_auth_token_response(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt.access_token_expire_minutes * 60,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Log unexpected error
        auth_logger.error(
            f"Unexpected error during login: {str(e)}",
            username=credentials.username,
            ip_address=ip_address,
            error=str(e),
            correlation_id=correlation_id,
            event_type="login_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/login/2fa")
async def login_with_2fa(
    payload: Login2FARequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("login", require_auth=False)),
):
    """Complete login after password verification when 2FA is enabled."""
    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)

    try:
        user, access_token, refresh_token, error = Login2FAService.complete_login(
            db=db,
            challenge_token=payload.challenge_token,
            totp_code=payload.totp_code,
            correlation_id=correlation_id,
        )
        if error:
            raise APIHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error,
                error_code="INVALID_2FA_CODE",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return build_auth_token_response(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt.access_token_expire_minutes * 60,
        )
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Unexpected error during 2FA login: {str(e)}",
            error=str(e),
            correlation_id=correlation_id,
            event_type="login_2fa_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

@router.post("/signup", response_model=UserResponse)
async def signup(
    user: UserSignupRequest, 
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("signup", require_auth=False))
):
    """Signup endpoint - register a new user"""
    if not settings.security.allow_public_signup:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )

    # Generate correlation ID
    correlation_id = CorrelationIDGenerator.generate()
    CorrelationIDGenerator.set(correlation_id)
    
    # Get request info
    ip_address = get_client_ip(request)
    user_agent = request.headers.get('user-agent', 'Unknown')
    
    # Log signup attempt
    auth_logger.signup_attempt(
        username=user.username,
        email=user.email,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    
    try:
        # Register the new user
        new_user = AuthService.register_user(
            db=db,
            username=user.username,
            password=user.password,
            email=user.email,
            organization_id=user.organization_id,
        )
        
        # Log successful signup
        auth_logger.signup_success(
            user_id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            ip_address=ip_address,
            duration_ms=0,  # Could be calculated if needed
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        
        # Send verification email (welcome after verified is preferred; keep both soft)
        try:
            from services.users.email_verification_service import EmailVerificationService

            issued = EmailVerificationService.issue_token(db, new_user)
            EmailVerificationService.send_verification_email(new_user, issued["_token"])
        except Exception as e:
            auth_logger.error(
                f"Failed to issue verification email: {str(e)}",
                user_id=new_user.id,
                email=new_user.email,
                error=str(e),
                event_type="email_verification_issue_error",
            )

        try:
            from utils.email_service import get_email_service
            email_service = get_email_service()
            # Welcome is soft/best-effort; gated by EMAIL__ENABLE_EMAILS inside EmailService
            email_service.send_welcome_email(
                to_email=new_user.email,
                username=new_user.username,
                temp_password=None
            )
        except Exception as e:
            # Log email error but don't fail signup
            auth_logger.error(
                f"Failed to send welcome email: {str(e)}",
                user_id=new_user.id,
                email=new_user.email,
                error=str(e),
                event_type="email_send_error"
            )
        
        # Return user info (without password)
        response = UserResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            role=new_user.role,
            organization_id=new_user.organization_id,
            status=new_user.status,
            phone_number=new_user.phone_number,
            created_at=new_user.created_at,
            last_login=new_user.last_login
        )
        return response
        
    except ValueError as e:
        # Log failed signup
        auth_logger.signup_failure(
            username=user.username,
            email=user.email,
            ip_address=ip_address,
            reason=str(e),
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Log unexpected error
        auth_logger.error(
            f"Unexpected error during signup: {str(e)}",
            username=user.username,
            email=user.email,
            ip_address=ip_address,
            error=str(e),
            correlation_id=correlation_id,
            event_type="signup_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/refresh")
async def refresh_token(
    request: Request,
    refresh_data: Optional[RefreshTokenRequest] = Body(None),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("refresh", require_auth=False)),
    __: None = Depends(require_csrf_header),
):
    """Refresh access token using httpOnly cookie or legacy JSON body."""
    try:
        refresh_token_value = resolve_refresh_token(
            request,
            refresh_data.refresh_token if refresh_data else None,
        )
        if not refresh_token_value:
            raise APIHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token required",
                error_code="INVALID_REFRESH_TOKEN",
                headers={"WWW-Authenticate": "Bearer"},
            )

        device_info = f"{request.headers.get('user-agent', 'Unknown')}"
        ip_address = get_client_ip(request)
        user_agent = request.headers.get('user-agent', 'Unknown')
        
        access_token, new_refresh_token = AuthService.refresh_access_token(
            db, refresh_token_value, device_info, ip_address, user_agent
        )
        
        return build_auth_token_response(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.jwt.access_token_expire_minutes * 60,
        )
        
    except ValueError as e:
        raise APIHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            error_code="INVALID_REFRESH_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/login-with-session-control")
async def login_with_session_control(
    credentials: UserSigninRequest,
    request: Request,
    db: Session = Depends(get_db),
    session_strategy: str = Query(None, description="Session management strategy"),
    _: None = Depends(RateLimitDependency.check_rate_limit("login", require_auth=False))
):
    """
    Enhanced login with session management options
    
    Session Strategies:
    - allow_multiple: Allow multiple sessions
    - replace_all: Replace all existing sessions (default)
    - replace_same_device: Replace sessions from same device
    - deny_if_exists: Deny login if user already has sessions
    - limit_sessions: Limit to max sessions per user
    """
    try:
        # Use default strategy from settings if not provided
        if session_strategy is None:
            session_strategy = settings.session.default_strategy
        
        device_info = f"{request.headers.get('user-agent', 'Unknown')}"
        ip_address = get_client_ip(request)
        user_agent = request.headers.get('user-agent', 'Unknown')
        
        # Use enhanced login service
        result = EnhancedLoginService.login_with_session_control(
            db=db,
            username=credentials.username,
            password=credentials.password,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
            session_strategy=session_strategy
        )
        
        if not result["success"]:
            error_code = result.get("error_code", "LOGIN_FAILED")
            if error_code == "ACCOUNT_LOCKED":
                lockout_info = result.get("lockout_info") or {}
                raise APIHTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account locked. Try again after {lockout_info.get('remaining_lockout_minutes', 0)} minutes.",
                    error_code="ACCOUNT_LOCKED",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if error_code == "ACCOUNT_DISABLED":
                raise APIHTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is disabled",
                    error_code="ACCOUNT_DISABLED",
                )
            if error_code == "INVALID_CREDENTIALS":
                raise APIHTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    error_code="INVALID_CREDENTIALS",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if result.get("requires_2fa"):
                return {
                    "requires_2fa": True,
                    "challenge_token": result["challenge_token"],
                    "message": result.get("message", "Two-factor authentication required"),
                }
            error_code = "SESSION_EXISTS" if "session" in result.get("error", "").lower() else error_code
            raise APIHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"],
                error_code=error_code,
            )
        
        return build_auth_token_response(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=result["expires_in"],
            session_info=result.get("session_info"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Enhanced login error: {str(e)}",
            username=credentials.username,
            error=str(e),
            event_type="enhanced_login_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
@router.post("/logout")
async def logout(
    request: Request,
    refresh_data: Optional[RefreshTokenRequest] = Body(None),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("logout", require_auth=False)),
    __: None = Depends(require_csrf_header),
):
    """Logout: revoke refresh token from cookie or legacy body and clear cookie."""
    try:
        refresh_token_value = resolve_refresh_token(
            request,
            refresh_data.refresh_token if refresh_data else None,
        )
        if not refresh_token_value:
            raise APIHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token required",
                error_code="INVALID_REFRESH_TOKEN",
            )

        user = LogoutService.get_user_from_refresh_token(db, refresh_token_value)
        
        success = LogoutService.logout_user(
            db=db,
            refresh_token=refresh_token_value,
            user_id=user.id if user else None
        )
        
        if not success:
            raise APIHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refresh token",
                error_code="INVALID_REFRESH_TOKEN",
            )
        
        # Create audit log for successful logout
        if user:
            AuditLogService.log_authentication_event(
                db=db,
                event_type="logout",
                user_id=user.id,
                username=user.username,
                email=user.email,
                status="success",
                metadata={
                    "logout_type": "single_session",
                    "refresh_token_revoked": True
                }
            )
        
        return build_logout_response("Successfully logged out")
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Logout endpoint error: {str(e)}",
            error=str(e),
            event_type="logout_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/logout-all")
async def logout_all_sessions(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("logout_all")),
    __: None = Depends(require_csrf_header),
):
    """Logout from all sessions; requires access JWT and a valid refresh cookie."""
    try:
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        refresh_token_value = get_refresh_token_from_request(request)
        if not refresh_token_value:
            raise APIHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh cookie required to logout all sessions",
                error_code="REFRESH_REQUIRED",
            )

        current = RefreshTokenService.get_active_token_for_user(
            db, user.id, refresh_token_value
        )
        if not current:
            raise APIHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh session",
                error_code="INVALID_REFRESH_TOKEN",
            )

        revoked_count = LogoutService.logout_all_user_sessions(db, user.id)

        response = JSONResponse(
            content={
                "message": f"Successfully logged out from {revoked_count} sessions",
                "timestamp": utc_now().isoformat(),
            }
        )
        clear_refresh_cookie(response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Logout all sessions error: {str(e)}",
            error=str(e),
            event_type="logout_all_endpoint_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
