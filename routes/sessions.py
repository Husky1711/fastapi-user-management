"""Session management endpoints (refresh_tokens-backed auth sessions)."""

from typing import Any, Dict

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from models.user_model import RefreshToken
from dependencies.auth import CurrentUser
from routes.auth_common import create_api_router
from schemas.login import SessionInfo, SuccessResponse
from services.auth import EnhancedLoginService, RefreshTokenService
from utils.cookie_auth import get_refresh_token_from_request
from utils.database import get_db
from utils.loggers import auth_logger
from utils.rate_limit_dependency import RateLimitDependency

router = create_api_router(tags=["Sessions"])


@router.get("/sessions/info", response_model=Dict[str, Any])
async def get_session_info(
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("sessions")),
):
    """Get detailed auth-session information for current user (refresh_tokens)."""
    try:
        session_info = EnhancedLoginService.get_user_session_info(
            db,
            current_user.id,
            current_refresh_token=get_refresh_token_from_request(request),
        )
        return session_info

    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Session info error: {str(e)}",
            user_id=current_user.id,
            error=str(e),
            event_type="session_info_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/sessions/revoke-others", response_model=SuccessResponse)
async def revoke_other_sessions(
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("session_revoke")),
):
    """Revoke all other auth sessions except current one"""
    try:
        refresh_token = get_refresh_token_from_request(request)
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current session not found; refresh cookie required",
            )

        current_session = RefreshTokenService.get_active_token_for_user(
            db, current_user.id, refresh_token
        )
        if not current_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current session not found or expired",
            )

        result = EnhancedLoginService.revoke_other_sessions(
            db, current_user.id, current_session.id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"],
            )

        return SuccessResponse(
            message=f"Revoked {result['sessions_revoked']} other sessions"
        )

    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"Revoke other sessions error: {str(e)}",
            user_id=current_user.id,
            error=str(e),
            event_type="revoke_other_sessions_error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/sessions", response_model=list[SessionInfo])
async def get_user_sessions(
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("sessions")),
):
    """List active auth sessions (refresh_tokens) for the current user."""
    sessions = RefreshTokenService.get_user_tokens(db, current_user.id)
    current_refresh = get_refresh_token_from_request(request)
    current_id = None
    if current_refresh:
        current = RefreshTokenService.get_active_token_for_user(
            db, current_user.id, current_refresh
        )
        if current:
            current_id = current.id

    return [
        SessionInfo(
            id=session.id,
            device_info=session.device_info,
            ip_address=session.ip_address,
            created_at=session.created_at,
            expires_at=session.expires_at,
            is_active=not session.is_revoked,
            is_current=session.id == current_id if current_id else False,
        )
        for session in sessions
    ]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("session_revoke")),
):
    """Revoke a specific auth session"""
    session = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.id == session_id,
            RefreshToken.user_id == current_user.id,
            RefreshToken.is_revoked == False,
        )
        .first()
    )

    if not session or not RefreshTokenService.revoke_token_by_id(
        db, session_id, reason="user_revoke"
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SuccessResponse(message="Session revoked successfully")
