"""Encrypt and decrypt user 2FA secrets at rest."""

from __future__ import annotations

from typing import Optional

from utils.field_encryption import decrypt_value, encrypt_value


class TwoFactorSecretService:
    @staticmethod
    def encrypt(secret: str) -> str:
        return encrypt_value(secret)

    @staticmethod
    def decrypt(stored_secret: Optional[str]) -> Optional[str]:
        return decrypt_value(stored_secret)

    @staticmethod
    def store_secret(secret: str) -> str:
        return TwoFactorSecretService.encrypt(secret)
