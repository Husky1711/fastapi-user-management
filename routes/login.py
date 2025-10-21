from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime
from services.user_service import UserService
from services.auth_service import AuthService
from services.refresh_token_service import RefreshTokenService
from schemas.login import userSignin, userSignup, Token, userResponse, RefreshTokenRequest, SessionInfo
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency
from models.user_model import User, RefreshToken
from utils.loggers import auth_logger, api_logger, db_logger, security_logger
from utils.production_logging import CorrelationIDGenerator
from utils.request_context import RequestTracker, track_request

router = APIRouter(prefix = "/api", tags=["login"])
security = HTTPBearer()

@router.post("/login", response_model=Token)
async def login(
    credentials: userSignin, 
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
        
        return {
            "access_token": access_token, 
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
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

@router.post("/signup", response_model=userResponse)
async def signup(
    user: userSignup, 
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
        return {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "status": new_user.status,
            "phone_number": new_user.phone_number
        }
        
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

@router.post("/refresh", response_model=Token)
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
        
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/logout")
async def logout(refresh_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Logout endpoint - revoke refresh token"""
    success = RefreshTokenService.revoke_token(db, refresh_data.refresh_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token"
        )
    
    return {"message": "Successfully logged out"}

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
        created_at=session.created_at.isoformat(),
        expires_at=session.expires_at.isoformat()
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
    
    return {"message": "Session revoked successfully"}

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