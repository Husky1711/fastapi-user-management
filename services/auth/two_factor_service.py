"""
Two-Factor Authentication Service
Handles TOTP-based 2FA for enhanced security
"""

import pyotp
import qrcode
import io
import base64
from datetime import datetime, timedelta
from typing import Optional, Tuple
import secrets
import hashlib


class TwoFactorService:
    """Service for Two-Factor Authentication using TOTP"""
    
    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new 2FA secret
        
        Returns:
            str: Base32-encoded secret key
        """
        return pyotp.random_base32()
    
    @staticmethod
    def get_provisioning_uri(username: str, secret: str, issuer: str = "FastAPI User Management") -> str:
        """
        Generate provisioning URI for QR code
        
        Args:
            username: Username
            secret: 2FA secret
            issuer: Service name
            
        Returns:
            str: OTP Auth URI
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=username, issuer_name=issuer)
    
    @staticmethod
    def generate_qr_code(uri: str) -> str:
        """
        Generate QR code image as base64 string
        
        Args:
            uri: Provisioning URI
            
        Returns:
            str: Base64-encoded PNG image
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    @staticmethod
    def verify_totp(secret: str, token: str) -> bool:
        """
        Verify TOTP token
        
        Args:
            secret: 2FA secret
            token: 6-digit TOTP code
            
        Returns:
            bool: True if valid, False otherwise
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)  # Allow 1 time step tolerance
    
    @staticmethod
    def generate_backup_codes(count: int = 8) -> list[str]:
        """
        Generate backup codes for account recovery
        
        Args:
            count: Number of backup codes to generate
            
        Returns:
            list[str]: List of backup codes
        """
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = secrets.token_hex(4).upper()
            codes.append(code)
        return codes
    
    @staticmethod
    def hash_backup_codes(codes: list[str]) -> list[str]:
        """
        Hash backup codes for secure storage
        
        Args:
            codes: List of backup codes
            
        Returns:
            list[str]: List of hashed backup codes
        """
        return [hashlib.sha256(code.encode()).hexdigest() for code in codes]
    
    @staticmethod
    def verify_backup_code(provided_code: str, hashed_codes: list[str]) -> bool:
        """
        Verify a backup code
        
        Args:
            provided_code: User-provided backup code
            hashed_codes: List of hashed backup codes
            
        Returns:
            bool: True if valid, False otherwise
        """
        provided_hash = hashlib.sha256(provided_code.upper().encode()).hexdigest()
        return provided_hash in hashed_codes
    
    @staticmethod
    def get_remaining_attempts(max_attempts: int, failed_attempts: int) -> int:
        """
        Calculate remaining login attempts
        
        Args:
            max_attempts: Maximum allowed attempts
            failed_attempts: Current failed attempts
            
        Returns:
            int: Remaining attempts
        """
        return max(0, max_attempts - failed_attempts)
    
    @staticmethod
    def calculate_lockout_time(failed_attempts: int, lockout_duration_minutes: int = 15) -> Optional[datetime]:
        """
        Calculate lockout expiration time
        
        Args:
            failed_attempts: Number of failed attempts
            lockout_duration_minutes: Lockout duration in minutes
            
        Returns:
            Optional[datetime]: Lockout expiration time or None
        """
        max_attempts = 5  # Lock after 5 failed attempts
        
        if failed_attempts >= max_attempts:
            return datetime.utcnow() + timedelta(minutes=lockout_duration_minutes)
        
        return None
    
    @staticmethod
    def is_account_locked(locked_until: Optional[datetime]) -> bool:
        """
        Check if account is locked
        
        Args:
            locked_until: Lockout expiration time
            
        Returns:
            bool: True if locked, False otherwise
        """
        if locked_until is None:
            return False
        
        return datetime.utcnow() < locked_until
