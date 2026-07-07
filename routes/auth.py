"""Authentication endpoints: login, signup, refresh, logout."""

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from config.settings import settings
from models.user_model import User
from routes.auth_common import create_api_router, security
from schemas.login import RefreshTokenRequest, UserResponse, UserSigninRequest, UserSignupRequest
from services.audit import AuditLogService
from services.auth import AuthService, EnhancedLoginService, LogoutService
from services.auth.login_attempt_service import LoginAttemptService
from services.sessions import UserSessionService
from services.users import UserService
from utils.api_errors import APIHTTPException
from utils.cookie_auth import build_auth_token_response, build_logout_response, resolve_refresh_token
from utils.database import get_db
from utils.loggers import auth_logger
from utils.production_logging import CorrelationIDGenerator
from utils.rate_limit_dependency import RateLimitDependency

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
    ip_address = request.client.host if request.client else "Unknown"
    user_agent = request.headers.get('user-agent', 'Unknown')
    
    # Log login attempt
    auth_logger.login_attempt(
        username=credentials.username,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    
    try:
        # Check if user exists first
        user = db.query(User).filter(User.username == credentials.username).first()
        
        # Record login attempt (even before authentication)
        LoginAttemptService.record_login_attempt(
            db=db,
            username=credentials.username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason="Pending authentication",
            user_id=user.id if user else None
        )
        
        # Check if account is locked
        if user and LoginAttemptService.is_account_locked(user):
            lockout_info = LoginAttemptService.get_lockout_info(user)
            
            # Log failed login (locked account)
            auth_logger.login_failure(
                username=credentials.username,
                ip_address=ip_address,
                reason="Account locked",
                user_agent=user_agent,
                correlation_id=correlation_id
            )
            
            # Record failed attempt
            LoginAttemptService.record_login_attempt(
                db=db,
                username=credentials.username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="Account locked",
                user_id=user.id if user else None
            )
            
            raise APIHTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked. Try again after {lockout_info['remaining_lockout_minutes']} minutes.",
                error_code="ACCOUNT_LOCKED",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Authenticate user
        user = AuthService.authenticate_user(db, credentials.username, credentials.password)
        if not user:
            # Get the user again to increment failed attempts
            user = db.query(User).filter(User.username == credentials.username).first()
            
            if user:
                # Increment failed attempts
                LoginAttemptService.increment_failed_attempts(db, user)
            
            # Record failed login attempt
            LoginAttemptService.record_login_attempt(
                db=db,
                username=credentials.username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="Invalid credentials",
                user_id=user.id if user else None
            )
            
            # Log failed login
            auth_logger.login_failure(
                username=credentials.username,
                ip_address=ip_address,
                reason="Invalid credentials",
                user_agent=user_agent,
                correlation_id=correlation_id
            )
            
            raise APIHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                error_code="INVALID_CREDENTIALS",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Reset failed attempts on successful authentication
        LoginAttemptService.reset_failed_attempts(db, user)
        
        # Record successful login attempt
        LoginAttemptService.record_login_attempt(
            db=db,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            user_id=user.id
        )
        
        # Get device info for security
        device_info = f"{user_agent}"
        
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
        
        # Create user session for tracking
        parsed_ua = UserSessionService.parse_user_agent(user_agent)
        device_fingerprint = UserSessionService.generate_device_fingerprint(user_agent, ip_address)
        
        session_result = UserSessionService.create_session(
            db=db,
            user_id=user.id,
            access_token_hash=hashlib.sha256(access_token.encode()).hexdigest(),
            refresh_token_id=None,  # Will be updated when refresh token is created
            device_fingerprint=device_fingerprint,
            device_name=f"{parsed_ua['os_name']} {parsed_ua['device_type']}",
            device_type=parsed_ua['device_type'],
            browser_name=parsed_ua['browser_name'],
            browser_version=parsed_ua['browser_version'],
            os_name=parsed_ua['os_name'],
            os_version=parsed_ua['os_version'],
            ip_address=ip_address,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        if session_result["success"]:
            auth_logger.info(
                f"User session created: {session_result['session_id']}",
                user_id=user.id,
                session_id=session_result['session_id'],
                event_type="session_created"
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
    ip_address = request.client.host if request.client else "Unknown"
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
            email=user.email
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
        
        # Send welcome email
        try:
            from utils.email_service import get_email_service
            email_service = get_email_service()
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
        return UserResponse(
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
    _: None = Depends(RateLimitDependency.check_rate_limit("refresh", require_auth=False))
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
        ip_address = request.client.host if request.client else "Unknown"
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
        ip_address = request.client.host if request.client else "Unknown"
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
            error_code = "SESSION_EXISTS" if "session" in result.get("error", "").lower() else "LOGIN_FAILED"
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
    _: None = Depends(RateLimitDependency.check_rate_limit("logout", require_auth=False))
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
            
            # Deactivate user session (we'll need to find the session by refresh token)
            # For now, we'll deactivate all sessions for the user
            session_result = UserSessionService.deactivate_user_sessions(
                db=db,
                user_id=user.id,
                reason="logout"
            )
            
            if session_result["success"]:
                auth_logger.info(
                    f"User sessions deactivated: {session_result['deactivated_count']} sessions",
                    user_id=user.id,
                    deactivated_count=session_result['deactivated_count'],
                    event_type="sessions_deactivated"
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("logout_all"))
):
    """Logout from all sessions with Redis cache cleanup"""
    try:
        # Get current user
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Logout from all sessions
        revoked_count = LogoutService.logout_all_user_sessions(db, user.id)

        response = JSONResponse(
            content={
                "message": f"Successfully logged out from {revoked_count} sessions",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        from utils.cookie_auth import clear_refresh_cookie

        clear_refresh_cookie(response)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Logout all sessions error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="logout_all_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
