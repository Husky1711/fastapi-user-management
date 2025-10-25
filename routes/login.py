from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import hashlib
from services.users import UserService
from services.auth import AuthService
from services.auth import RefreshTokenService
from services.auth import LogoutService
from services.auth import EnhancedLoginService
from services.users import PasswordResetService
from services.users import ProfileUpdateService
from services.audit import AuditLogService
from services.sessions import UserSessionService
from services.permissions import UserPermissionService
from services.permissions import UserGroupService
from services.permissions import ApiKeyService
from services.users import PasswordHistoryService
from schemas.login import (
    UserSigninRequest, UserSignupRequest, TokenResponse, UserResponse, 
    RefreshTokenRequest, SessionInfo, UsersListResponse, SuperAdminUsersResponse,
    UserDetailResponse, ErrorResponse, SuccessResponse, LogoutResponse,
    HealthCheckResponse, RateLimitResponse, UserRole, UserStatus,
    AdminCreateUserRequest, AdminCreateUserResponse,
    PasswordResetRequest, PasswordResetResponse, PasswordResetConfirm, PasswordResetConfirmResponse,
    UserProfileUpdate, UserProfileUpdateResponse, PasswordChangeRequest, PasswordChangeResponse
)
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency
from models.user_model import User, RefreshToken
from utils.loggers import auth_logger, api_logger, db_logger, security_logger
from utils.production_logging import CorrelationIDGenerator
from utils.request_context import RequestTracker, track_request
import traceback

from typing import Dict, Any

router = APIRouter(prefix = "/api/v1", tags=["Authentication & User Management"])
security = HTTPBearer()

@router.post("/login", response_model=TokenResponse)
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
        user = AuthService.authenticate_user(db, credentials.username, credentials.password)
        if not user:
            # Log failed login
            auth_logger.login_failure(
                username=credentials.username,
                ip_address=ip_address,
                reason="Invalid credentials",
                user_agent=user_agent,
                correlation_id=correlation_id
            )
            
            # Create audit log for failed login
            AuditLogService.log_authentication_event(
                db=db,
                event_type="login_failed",
                username=credentials.username,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=correlation_id,
                correlation_id=correlation_id,
                status="failure",
                error_message="Invalid credentials",
                metadata={
                    "reason": "Invalid credentials",
                    "attempted_username": credentials.username
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
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
        
        return TokenResponse(
            access_token=access_token, 
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=300  # 5 minutes
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

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest, 
    request: Request, 
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("refresh", require_auth=False))
):
    """Refresh access token using refresh token"""
    try:
        # Get device info for security
        device_info = f"{request.headers.get('user-agent', 'Unknown')}"
        ip_address = request.client.host if request.client else "Unknown"
        user_agent = request.headers.get('user-agent', 'Unknown')
        
        # Refresh tokens
        access_token, new_refresh_token = AuthService.refresh_access_token(
            db, refresh_data.refresh_token, device_info, ip_address, user_agent
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=300  # 5 minutes
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/login-with-session-control", response_model=TokenResponse)
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type="bearer",
            expires_in=result["expires_in"],
            session_info=result.get("session_info")
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

@router.get("/sessions/info", response_model=Dict[str, Any])
async def get_session_info(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("sessions"))
):
    """Get detailed session information for current user"""
    try:
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        session_info = EnhancedLoginService.get_user_session_info(db, user.id)
        return session_info
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Session info error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="session_info_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/sessions/revoke-others", response_model=SuccessResponse)
async def revoke_other_sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("session_revoke"))
):
    """Revoke all other sessions except current one"""
    try:
        user = AuthService.get_current_user(db, credentials.credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get current session ID (simplified - would need proper token tracking)
        result = EnhancedLoginService.revoke_other_sessions(db, user.id, 0)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return SuccessResponse(
            message=f"Revoked {result['sessions_revoked']} other sessions"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Revoke other sessions error: {str(e)}",
            user_id=user.id if 'user' in locals() else None,
            error=str(e),
            event_type="revoke_other_sessions_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/logout", response_model=LogoutResponse)
async def logout(
    refresh_data: RefreshTokenRequest, 
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("logout"))
):
    """Enhanced logout endpoint with Redis cache cleanup"""
    try:
        # Get user from refresh token for additional cleanup
        user = LogoutService.get_user_from_refresh_token(db, refresh_data.refresh_token)
        
        # Perform logout with Redis cleanup
        success = LogoutService.logout_user(
            db=db,
            refresh_token=refresh_data.refresh_token,
            user_id=user.id if user else None
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refresh token"
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
        
        return LogoutResponse(message="Successfully logged out")
        
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

@router.post("/logout-all", response_model=SuccessResponse)
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
        
        return SuccessResponse(
            message=f"Successfully logged out from {revoked_count} sessions"
        )
        
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

@router.get("/sessions", response_model=list[SessionInfo])
async def get_user_sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("sessions"))
):
    """Get all active sessions for current user"""
    # Verify JWT token
    user = AuthService.get_current_user(db, credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user's active sessions
    sessions = RefreshTokenService.get_user_tokens(db, user.id)
    
    return [SessionInfo(
        id=session.id,
        device_info=session.device_info,
        ip_address=session.ip_address,
        created_at=session.created_at,
        expires_at=session.expires_at,
        is_active=not session.is_revoked
    ) for session in sessions]

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: int, 
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("session_revoke"))
):
    """Revoke a specific session"""
    # Verify JWT token
    user = AuthService.get_current_user(db, credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Find and revoke the session
    session = db.query(RefreshToken).filter(
        RefreshToken.id == session_id,
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked == False
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session.is_revoked = True
    session.revoked_at = datetime.utcnow()
    db.commit()
    
    return SuccessResponse(message="Session revoked successfully")

@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint"""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        environment="development"
    )

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
    
    # Get role and organization info from JWT token
    from utils.jwt_config import verify_token
    payload = verify_token(credentials.credentials)
    current_user_role = payload.get("role", "user")
    current_user_org_id = payload.get("organization_id", 1)
    
    # Get users based on role
    users = UserService.get_users_by_role_and_organization(
        db, current_user_role, current_user_org_id
    )
    
    # Format response based on role
    if current_user_role == "super_admin":
        # Super admin sees all users grouped by organization
        response = {}
        for user in users:
            org_id = user.organization_id
            if org_id not in response:
                response[org_id] = {"organization_id": org_id, "users": []}
            response[org_id]["users"].append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "phone_number": user.phone_number
            })
        return response
    elif current_user_role == "admin":
        # Admin sees users from their organization
        return {
            "organization_id": current_user_org_id,
            "users": [{
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "phone_number": user.phone_number
            } for user in users]
        }
    else:
        # Regular user sees only themselves
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "phone_number": user.phone_number
            }
        }

@router.get("/users/{user_id}")
async def get_user_by_id(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("user_detail"))
):
    """Get specific user by ID based on current user's role and organization"""
    # Verify JWT token and get user info
    user = AuthService.get_current_user(db, credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get role and organization info from JWT token
    from utils.jwt_config import verify_token
    payload = verify_token(credentials.credentials)
    current_user_role = payload.get("role", "user")
    current_user_org_id = payload.get("organization_id", 1)
    current_user_id = payload.get("user_id", user.id)
    
    # Get specific user based on role
    specific_user = UserService.get_user_by_role_and_organization(
        db, user_id, current_user_role, current_user_org_id, current_user_id
    )
    
    if specific_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or access denied"
        )
    
    return {
        "id": specific_user.id,
        "username": specific_user.username,
        "email": specific_user.email,
        "role": specific_user.role,
        "organization_id": specific_user.organization_id,
        "status": specific_user.status,
        "phone_number": specific_user.phone_number
    }

@router.post("/debug-login", response_model=TokenResponse)
async def debug_login(
    credentials: UserSigninRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Debug login endpoint to test basic functionality"""
    try:
        # Simple authentication test
        user = AuthService.authenticate_user(db, credentials.username, credentials.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Create tokens
        device_info = f"{request.headers.get('user-agent', 'Unknown')}"
        ip_address = request.client.host if request.client else "Unknown"
        user_agent = request.headers.get('user-agent', 'Unknown')
        
        access_token, refresh_token = AuthService.create_tokens_for_user(
            db, user, device_info, ip_address, user_agent
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt.access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(f"Debug login error: {str(e)}", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/debug-refresh", response_model=TokenResponse)
async def debug_refresh(
    refresh_data: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Debug refresh endpoint to test token refresh functionality"""
    try:
        auth_logger.info(
            f"Debug refresh attempt with token: {refresh_data.refresh_token[:20]}...",
            token_prefix=refresh_data.refresh_token[:20],
            event_type="debug_refresh_attempt"
        )
        
        # Test RefreshTokenService.verify_refresh_token directly
        user = RefreshTokenService.verify_refresh_token(db, refresh_data.refresh_token)
        if not user:
            auth_logger.warning("Refresh token verification failed", event_type="debug_refresh_failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        auth_logger.info(f"Refresh token verified for user: {user.username}", event_type="debug_refresh_success")
        
        # Create new tokens
        device_info = f"{request.headers.get('user-agent', 'Unknown')}"
        ip_address = request.client.host if request.client else "Unknown"
        user_agent = request.headers.get('user-agent', 'Unknown')
        
        access_token, new_refresh_token = AuthService.refresh_access_token(
            db, refresh_data.refresh_token, device_info, ip_address, user_agent
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.jwt.access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(f"Debug refresh error: {str(e)}", error=str(e), traceback=traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
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
    - Super Admin → Can create: Organization Admin, Admin, User
    - Organization Admin → Can create: Admin, User
    - Admin → Can create: User only
    - User → Cannot create anyone
    
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
        
        # Prepare response
        created_user = result["user"]
        user_response = UserResponse(
            id=created_user.id,
            username=created_user.username,
            email=created_user.email,
            role=created_user.role,
            organization_id=created_user.organization_id,
            status=created_user.status,
            phone_number=created_user.phone_number,
            created_at=created_user.created_at,
            last_login=created_user.last_login
        )
        
        return AdminCreateUserResponse(
            success=True,
            message=result["message"],
            user=user_response,
            generated_password=result.get("generated_password"),
            email_sent=False,  # TODO: Implement email service
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

# Password Reset Endpoints
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
        
        return UserResponse(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
            role=current_user.role,
            organization_id=current_user.organization_id,
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

# ============================================================================
# PRODUCTION API ENDPOINTS - ADVANCED FEATURES
# ============================================================================

# ============================================================================
# AUDIT LOGGING ENDPOINTS
# ============================================================================

@router.get("/audit/logs", response_model=Dict[str, Any])
async def get_audit_logs(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    user_id: int = Query(None, description="Filter by user ID"),
    organization_id: int = Query(None, description="Filter by organization ID"),
    event_type: str = Query(None, description="Filter by event type"),
    event_category: str = Query(None, description="Filter by event category"),
    resource_type: str = Query(None, description="Filter by resource type"),
    status: str = Query(None, description="Filter by status"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)"),
    limit: int = Query(100, description="Maximum number of records"),
    offset: int = Query(0, description="Number of records to skip"),
    _: None = Depends(RateLimitDependency.check_rate_limit("audit_logs"))
):
    """
    Get audit logs with filtering options
    
    **Access Control:**
    - Requires authentication
    - Users can only see logs for their organization
    - Super Admins can see all logs
    
    **Features:**
    - Comprehensive filtering options
    - Pagination support
    - Organization isolation
    - Role-based access control
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Parse dates if provided
        start_datetime = None
        end_datetime = None
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "SUPER_ADMIN":
            filter_organization_id = current_user.organization_id
        
        # Get audit logs
        result = AuditLogService.get_audit_logs(
            db=db,
            user_id=user_id,
            organization_id=filter_organization_id,
            event_type=event_type,
            event_category=event_category,
            resource_type=resource_type,
            status=status,
            start_date=start_datetime,
            end_date=end_datetime,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get audit logs endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="audit_logs_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/audit/statistics", response_model=Dict[str, Any])
async def get_audit_statistics(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    organization_id: int = Query(None, description="Filter by organization ID"),
    start_date: str = Query(None, description="Start date (ISO format)"),
    end_date: str = Query(None, description="End date (ISO format)"),
    _: None = Depends(RateLimitDependency.check_rate_limit("audit_statistics"))
):
    """
    Get audit statistics and analytics
    
    **Access Control:**
    - Requires authentication
    - Users can only see statistics for their organization
    - Super Admins can see all statistics
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Parse dates if provided
        start_datetime = None
        end_datetime = None
        if start_date:
            start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Apply organization filter for non-super admins
        filter_organization_id = organization_id
        if current_user.role != "SUPER_ADMIN":
            filter_organization_id = current_user.organization_id
        
        # Get audit statistics
        result = AuditLogService.get_audit_statistics(
            db=db,
            organization_id=filter_organization_id,
            start_date=start_datetime,
            end_date=end_datetime
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result["error"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Get audit statistics endpoint error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="audit_statistics_endpoint_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )