"""Session management endpoints (refresh_tokens-backed)."""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from models.user_model import RefreshToken
from routes.auth_common import create_api_router, security
from schemas.login import SessionInfo, SuccessResponse
from services.auth import AuthService, EnhancedLoginService, RefreshTokenService, RefreshTokenService
from utils.database import get_db
from utils.loggers import auth_logger
from utils.rate_limit_dependency import RateLimitDependency

router = create_api_router(tags=["Sessions"])

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
    
    if not RefreshTokenService.revoke_token_by_id(db, session_id, reason="user_revoke"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return SuccessResponse(message="Session revoked successfully")
