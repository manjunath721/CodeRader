import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from app.core.config import get_settings

settings = get_settings()

SECRET_KEY = getattr(settings, "SECRET_KEY", "coderadar-secret-key-change-in-production-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 600k iterations (OWASP recommendation)."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2:sha256:{PBKDF2_ITERATIONS}${salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored hash."""
    try:
        if hashed_password.startswith("pbkdf2:sha256:"):
            parts = hashed_password.split("$")
            if len(parts) != 3:
                return False
            _, salt, expected_hex = parts
            header_parts = parts[0].split(":")
            iterations = int(header_parts[2]) if len(header_parts) >= 3 else PBKDF2_ITERATIONS
            key = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            )
            return hmac.compare_digest(key.hex(), expected_hex)
        elif hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
            import bcrypt
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        return False
    except Exception:
        return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate signed JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
