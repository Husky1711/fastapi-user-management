"""Debug auth endpoints (disabled unless SECURITY__ALLOW_DEBUG_AUTH)."""

import traceback

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config.settings import settings
from routes.auth_common import create_api_router
from schemas.login import RefreshTokenRequest, TokenResponse, UserSigninRequest
from services.auth import AuthService, RefreshTokenService
from utils.database import get_db
from utils.loggers import auth_logger

router = create_api_router(tags=["Debug"])

@router.post("/debug-login", response_model=TokenResponse)
async def debug_login(
    credentials: UserSigninRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Debug login endpoint to test basic functionality"""
    if not settings.security.allow_debug_auth:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

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
    if not settings.security.allow_debug_auth:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

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
