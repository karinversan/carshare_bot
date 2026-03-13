"""JWT authentication middleware and dependencies.

Usage in routes:
    from apps.api_service.app.core.auth import require_auth, require_admin

    @router.get("/protected")
    def protected(user = Depends(require_auth)):
        ...

    @router.get("/admin-only")
    def admin_only(user = Depends(require_admin)):
        ...

For the MVP, auth can be disabled by setting AUTH_ENABLED=false in .env.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError, ExpiredSignatureError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api_service.app.core.config import settings

logger = logging.getLogger(__name__)

_security = HTTPBearer(auto_error=False)

AUTH_ENABLED = getattr(settings, "auth_enabled", False)


class AuthUser:
    """Decoded JWT payload."""
    def __init__(self, user_id: str, role: str = "customer", telegram_user_id: int | None = None):
        self.user_id = user_id
        self.role = role
        self.telegram_user_id = telegram_user_id


def create_token(user_id: str, role: str = "customer", telegram_user_id: int | None = None, expires_hours: int = 24) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": user_id,
        "role": role,
        "telegram_user_id": telegram_user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> AuthUser:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return AuthUser(
            user_id=payload["sub"],
            role=payload.get("role", "customer"),
            telegram_user_id=payload.get("telegram_user_id"),
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> AuthUser:
    """Dependency: require valid JWT. Returns AuthUser.

    When AUTH_ENABLED=false (MVP mode), returns a demo user.
    """
    if not AUTH_ENABLED:
        return AuthUser(user_id="demo-user", role="admin", telegram_user_id=0)

    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")

    return decode_token(credentials.credentials)


async def require_admin(user: AuthUser = Depends(require_auth)) -> AuthUser:
    """Dependency: require admin role."""
    if not AUTH_ENABLED:
        return user

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
