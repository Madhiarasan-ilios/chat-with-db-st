"""
JWT helpers – encoding and decoding only.
User look-up / validation lives in api/deps.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Encode *data* into a signed JWT.

    Required keys in *data*:
        sub        – unique user identifier
        role       – user role string
        udise_code – school UDISE code the token is scoped to
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    return jwt.encode(
        payload,
        settings.resolved_jwt_secret(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT.  Returns the payload dict or *None* if invalid/expired.
    """
    try:
        return jwt.decode(
            token,
            settings.resolved_jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None
