"""
2FA Management Endpoints
Handles Two-Factor Authentication setup and management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from utils.database import get_db
from services.auth import AuthService
from services.auth.two_factor_service import TwoFactorService
from utils.loggers import auth_logger
from schemas.auth_2fa import (
    Enable2FARequest, Enable2FAResponse,
    Disable2FARequest, Disable2FAResponse,
    Verify2FARequest, Verify2FAResponse,
    GenerateQRCodeResponse,
    BackupCodesResponse
)

router = APIRouter(prefix="/api/v1", tags=["Two-Factor Authentication"])
security = HTTPBearer()

@router.post("/2fa/enable", response_model=Enable2FAResponse)
async def enable_2fa(
    request: Enable2FARequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Enable Two-Factor Authentication for user
    
    **Process:**
    1. User requests to enable 2FA
    2. Generate 2FA secret
    3. Generate QR code for scanning
    4. Return QR code and backup codes
    5. User scans QR with authenticator app
    6. User verifies with 2FA code
    7. 2FA is enabled
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        # Generate 2FA secret
        secret = TwoFactorService.generate_secret()
        
        # Generate QR code
        uri = TwoFactorService.get_provisioning_uri(
            username=current_user.username,
            secret=secret,
            issuer="FastAPI User Management"
        )
        qr_code = TwoFactorService.generate_qr_code(uri)
        
        # Generate backup codes
        backup_codes = TwoFactorService.generate_backup_codes()
        hashed_backup_codes = TwoFactorService.hash_backup_codes(backup_codes)
        
        # Update user with 2FA settings
        current_user.two_factor_secret = secret
        current_user.backup_codes = hashed_backup_codes
        db.commit()
        
        return Enable2FAResponse(
            success=True,
            message="2FA setup initiated. Please verify with your authenticator app.",
            qr_code=qr_code,
            backup_codes=backup_codes,
            username=current_user.username
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"2FA enable error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="2fa_enable_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/2fa/verify", response_model=Verify2FAResponse)
async def verify_2fa_code(
    request: Verify2FARequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Verify 2FA code to complete 2FA setup or login
    
    **Use Cases:**
    1. Complete 2FA setup after scanning QR code
    2. Login with 2FA enabled
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        # Verify TOTP code
        if not current_user.two_factor_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA not configured for this user"
            )
        
        is_valid = TwoFactorService.verify_totp(
            current_user.two_factor_secret,
            request.totp_code
        )
        
        if not is_valid:
            # Check backup codes
            if current_user.backup_codes and request.totp_code:
                is_valid = TwoFactorService.verify_backup_code(
                    request.totp_code,
                    current_user.backup_codes
                )
        
        if is_valid:
            # Enable 2FA if just setting up
            if not current_user.is_2fa_enabled:
                current_user.is_2fa_enabled = True
                db.commit()
            
            return Verify2FAResponse(
                success=True,
                message="2FA code verified successfully"
            )
        else:
            return Verify2FAResponse(
                success=False,
                message="Invalid 2FA code"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"2FA verify error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="2fa_verify_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/2fa/disable", response_model=Disable2FAResponse)
async def disable_2fa(
    request: Disable2FARequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Disable Two-Factor Authentication for user
    """
    try:
        # Get current user
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        # Verify with 2FA code before disabling
        if current_user.two_factor_secret:
            is_valid = TwoFactorService.verify_totp(
                current_user.two_factor_secret,
                request.totp_code
            )
            
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid 2FA code"
                )
        
        # Disable 2FA
        current_user.is_2fa_enabled = False
        current_user.two_factor_secret = None
        current_user.backup_codes = None
        db.commit()
        
        return Disable2FAResponse(
            success=True,
            message="2FA has been disabled successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"2FA disable error: {str(e)}",
            user_id=current_user.id if 'current_user' in locals() else None,
            error=str(e),
            event_type="2fa_disable_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/2fa/status")
async def get_2fa_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get 2FA status for current user"""
    try:
        current_user = AuthService.get_current_user(db, credentials.credentials)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        return {
            "is_enabled": current_user.is_2fa_enabled,
            "has_secret": current_user.two_factor_secret is not None,
            "has_backup_codes": current_user.backup_codes is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        auth_logger.error(
            f"2FA status error: {str(e)}",
            error=str(e),
            event_type="2fa_status_error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
