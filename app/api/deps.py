"""
FastAPI dependency functions for authentication and authorisation.

``get_current_super_admin`` is injected into protected routes via
``Depends(get_current_super_admin)`` and returns a verified user dict
with keys: id, role, udise_code.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock user store
# Replace with a real DB/secret-manager lookup in production.
# ---------------------------------------------------------------------------
MOCK_USERS: Dict[str, Dict[str, Any]] = {
    "super_admin_schoolA": {
        "id": "super_admin_schoolA",
        "role": "super_admin",
        "udise_code": "123456",
    },
    "super_admin_schoolB": {
        "id": "super_admin_schoolB",
        "role": "super_admin",
        "udise_code": "789012",
    },
}

# ---------------------------------------------------------------------------
# OAuth2 scheme – clients POST to /token to get a bearer token
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)

_FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Insufficient privileges – super_admin role required.",
)


async def get_current_super_admin(
    token: str = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """
    Decode the JWT, look up the user, and assert they are a super_admin.
    Raises 401 / 403 on failure; returns the user dict on success.
    """
    payload = decode_access_token(token)
    if payload is None:
        logger.warning("JWT decode failed")
        raise _CREDENTIALS_EXCEPTION

    user_id: str = payload.get("sub", "")
    user = MOCK_USERS.get(user_id)

    if user is None:
        logger.warning("Unknown user_id in token: %s", user_id)
        raise _CREDENTIALS_EXCEPTION

    if user["role"] != "super_admin":
        logger.warning("Role check failed for %s (role=%s)", user_id, user["role"])
        raise _FORBIDDEN_EXCEPTION

    logger.debug("Authenticated: %s | udise=%s", user_id, user["udise_code"])
    return user
