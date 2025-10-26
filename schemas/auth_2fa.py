"""
2FA Schemas
Pydantic models for Two-Factor Authentication
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class Enable2FARequest(BaseModel):
    """Request to enable 2FA"""
    pass


class Enable2FAResponse(BaseModel):
    """Response for 2FA enabling"""
    success: bool
    message: str
    qr_code: str
    backup_codes: List[str]
    username: str


class Disable2FARequest(BaseModel):
    """Request to disable 2FA"""
    totp_code: str = Field(..., min_length=6, max_length=6, description="Current 2FA code")


class Disable2FAResponse(BaseModel):
    """Response for 2FA disabling"""
    success: bool
    message: str


class Verify2FARequest(BaseModel):
    """Request to verify 2FA code"""
    totp_code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class Verify2FAResponse(BaseModel):
    """Response for 2FA verification"""
    success: bool
    message: str


class GenerateQRCodeResponse(BaseModel):
    """Response for QR code generation"""
    qr_code: str
    backup_codes: List[str]


class BackupCodesResponse(BaseModel):
    """Response for backup codes"""
    backup_codes: List[str]
    message: str
