"""Fernet field-level encryption for secrets stored in the database."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from config.settings import settings

_ENCRYPTED_PREFIX = "enc:"


def _fernet() -> Fernet:
    key_material = settings.jwt.secret_key
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(plaintext: str) -> str:
    if not plaintext:
        return plaintext
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{_ENCRYPTED_PREFIX}{token}"


def decrypt_value(stored: str | None) -> str | None:
    if not stored:
        return stored
    if stored.startswith(_ENCRYPTED_PREFIX):
        ciphertext = stored[len(_ENCRYPTED_PREFIX) :]
        try:
            return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return None
    return stored
