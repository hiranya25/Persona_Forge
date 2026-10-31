"""Passwords, tokens, one-time codes, and secret encryption."""

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet

from app.core.config import get_settings

MIN_PASSWORD_LENGTH = 10
_hasher = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Passwords ---------------------------------------------------------------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        # Spend comparable time so missing accounts aren't revealed by timing.
        _hasher.hash(password)
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# --- Opaque tokens (refresh tokens, invitations, recovery codes) -------------

def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_recovery_codes(count: int = 10) -> list[str]:
    codes = []
    for _ in range(count):
        raw = base64.b32encode(secrets.token_bytes(10)).decode().lower()
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    raw = code.strip().lower().replace("-", "").replace(" ", "")
    return "-".join(raw[i:i + 4] for i in range(0, len(raw), 4))


# --- Email one-time codes ----------------------------------------------------

def new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, code.strip().encode(), hashlib.sha256).hexdigest()


def otp_matches(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(code), code_hash)


# --- JWTs ----------------------------------------------------------------------

def _encode(payload: dict[str, Any], ttl_seconds: int) -> str:
    now = utcnow()
    payload = {**payload, "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def _decode(token: str, purpose: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("purpose") != purpose:
        return None
    return payload


def create_access_token(user_id: uuid.UUID, company_id: uuid.UUID | None,
                        is_platform_admin: bool, roles: list[str]) -> str:
    return _encode(
        {
            "purpose": "access",
            "sub": str(user_id),
            "cid": str(company_id) if company_id else None,
            "pa": is_platform_admin,
            "roles": sorted(roles),
        },
        get_settings().access_token_ttl_seconds,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    return _decode(token, "access")


def create_mfa_token(user_id: uuid.UUID, purpose: str) -> str:
    """Short-lived token proving the password step passed ("mfa" or "mfa_setup")."""
    return _encode({"purpose": purpose, "sub": str(user_id)},
                   get_settings().mfa_token_ttl_seconds)


def decode_mfa_token(token: str, purpose: str) -> uuid.UUID | None:
    payload = _decode(token, purpose)
    return uuid.UUID(payload["sub"]) if payload else None


# --- TOTP ------------------------------------------------------------------------

def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.data_encryption_key
    if not key:
        digest = hashlib.sha256(("fernet:" + settings.jwt_secret).encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Persona Forge")


def totp_matches(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
