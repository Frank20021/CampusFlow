from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import get_settings
from app.core.exceptions import AppError

# argon2id is the current OWASP recommendation (memory-hard, so GPU cracking
# is expensive). bcrypt is the common alternative: more examples online, but
# a 72-byte password cap and weaker GPU resistance.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(*, user_id: UUID) -> str:
    """Issue a signed JWT access token.

    Chosen: short-lived access tokens in the Authorization header.
    Alternative: httpOnly cookies (stronger XSS protection, CSRF to manage)
    or access+refresh rotation (better idle sessions, more moving parts).
    Phase 1 keeps a single access token so the auth story stays interview-simple.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise AppError(
            code="token_expired",
            message="Access token has expired",
            status_code=401,
        ) from exc
    except InvalidTokenError as exc:
        raise AppError(
            code="invalid_token",
            message="Access token is invalid",
            status_code=401,
        ) from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise AppError(
            code="invalid_token",
            message="Access token is invalid",
            status_code=401,
        )

    try:
        return UUID(payload["sub"])
    except ValueError as exc:
        raise AppError(
            code="invalid_token",
            message="Access token is invalid",
            status_code=401,
        ) from exc
