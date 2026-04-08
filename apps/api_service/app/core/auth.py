"""JWT auth, Telegram WebApp verification, and internal-service auth helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from apps.api_service.app.core.config import settings
from apps.api_service.app.db import models

logger = logging.getLogger(__name__)

_security = HTTPBearer(auto_error=False)


def _auth_enabled() -> bool:
    return bool(settings.auth_enabled)


@dataclass
class AuthUser:
    user_id: str
    role: str = "customer"
    telegram_user_id: int | None = None
    is_internal: bool = False
    service_name: str | None = None


@dataclass
class TelegramIdentity:
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None


def create_token(
    user_id: str,
    role: str = "customer",
    telegram_user_id: int | None = None,
    expires_hours: int = 24,
    *,
    is_internal: bool = False,
    service_name: str | None = None,
) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "telegram_user_id": telegram_user_id,
        "is_internal": is_internal,
        "service_name": service_name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> AuthUser:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return AuthUser(
            user_id=str(payload["sub"]),
            role=payload.get("role", "customer"),
            telegram_user_id=payload.get("telegram_user_id"),
            is_internal=bool(payload.get("is_internal", False)),
            service_name=payload.get("service_name"),
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc


def validate_telegram_init_data(init_data: str, *, max_age_seconds: int = 3600) -> TelegramIdentity:
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram auth is unavailable: bot token is not configured")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    payload = dict(pairs)
    received_hash = payload.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Telegram initData hash is missing")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hmac.new(
        b"WebAppData",
        settings.telegram_bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Telegram initData signature is invalid")

    auth_date_raw = payload.get("auth_date")
    if auth_date_raw:
        auth_date = datetime.fromtimestamp(int(auth_date_raw), tz=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - auth_date).total_seconds()
        if age_seconds > max_age_seconds:
            raise HTTPException(status_code=401, detail="Telegram initData is too old")

    user_raw = payload.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="Telegram initData user payload is missing")

    try:
        user_payload = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=401, detail="Telegram initData user payload is malformed") from exc

    telegram_user_id = user_payload.get("id")
    if not telegram_user_id:
        raise HTTPException(status_code=401, detail="Telegram user id is missing")

    return TelegramIdentity(
        telegram_user_id=int(telegram_user_id),
        username=user_payload.get("username"),
        first_name=user_payload.get("first_name"),
        last_name=user_payload.get("last_name"),
    )


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> AuthUser:
    if not _auth_enabled():
        return AuthUser(user_id="demo-user", role="admin", telegram_user_id=0)

    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")
    return decode_token(credentials.credentials)


async def require_auth_or_internal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    x_internal_service_token: str | None = Header(default=None),
) -> AuthUser:
    if not _auth_enabled():
        return AuthUser(user_id="demo-user", role="admin", telegram_user_id=0)

    if x_internal_service_token and hmac.compare_digest(x_internal_service_token, settings.internal_service_token):
        return AuthUser(
            user_id="internal-service",
            role="service",
            is_internal=True,
            service_name="internal",
        )

    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")
    return decode_token(credentials.credentials)


async def require_internal_service(
    x_internal_service_token: str | None = Header(default=None),
) -> AuthUser:
    if not _auth_enabled():
        return AuthUser(user_id="demo-internal", role="service", is_internal=True, service_name="internal")

    if not x_internal_service_token:
        raise HTTPException(status_code=401, detail="Internal service token required")
    if not hmac.compare_digest(x_internal_service_token, settings.internal_service_token):
        raise HTTPException(status_code=403, detail="Invalid internal service token")
    return AuthUser(user_id="internal-service", role="service", is_internal=True, service_name="internal")


async def require_admin(user: AuthUser = Depends(require_auth)) -> AuthUser:
    if not _auth_enabled():
        return user
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def ensure_inspection_access(
    inspection: models.InspectionSession,
    user: AuthUser,
) -> None:
    if user.is_internal or user.role == "admin":
        return
    if str(inspection.user_id) != user.user_id:
        raise HTTPException(status_code=403, detail="Inspection access denied")


def ensure_comparison_access(
    db: Session,
    comparison: models.InspectionComparison,
    user: AuthUser,
) -> None:
    if user.is_internal or user.role == "admin":
        return
    post_session = db.get(models.InspectionSession, comparison.post_session_id)
    if not post_session or str(post_session.user_id) != user.user_id:
        raise HTTPException(status_code=403, detail="Comparison access denied")


def ensure_user_exists(
    db: Session,
    auth_user: AuthUser,
    *,
    fallback_first_name: str | None = None,
    fallback_username: str | None = None,
) -> models.User:
    user = db.get(models.User, auth_user.user_id)
    if user:
        return user

    telegram_user_id = auth_user.telegram_user_id
    if telegram_user_id is None:
        raise HTTPException(status_code=401, detail="Authenticated user is not linked to a stored account")

    user = models.User(
        id=auth_user.user_id,
        telegram_user_id=telegram_user_id,
        username=fallback_username,
        first_name=fallback_first_name,
        role=auth_user.role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user
