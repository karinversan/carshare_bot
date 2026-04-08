"""Authentication routes for Telegram Mini App and admin panel."""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api_service.app.core.auth import create_token, validate_telegram_init_data
from apps.api_service.app.core.config import settings
from apps.api_service.app.db import models
from apps.api_service.app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class TelegramAuthRequest(BaseModel):
    init_data: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str
    first_name: str | None = None
    username: str | None = None


class TokenRequest(BaseModel):
    telegram_user_id: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str


def _stable_admin_telegram_id(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return -int.from_bytes(digest[:7], "big")


def _get_or_create_user(
    db: Session,
    *,
    telegram_user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None = None,
    role: str = "customer",
) -> models.User:
    user = db.execute(
        select(models.User).where(models.User.telegram_user_id == telegram_user_id)
    ).scalar_one_or_none()
    if user:
        user.username = username or user.username
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.role = role if role == "admin" else user.role
        return user

    user = models.User(
        id=uuid.uuid4(),
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@router.post("/telegram", response_model=TokenResponse)
def telegram_login(payload: TelegramAuthRequest, db: Session = Depends(get_db)):
    identity = validate_telegram_init_data(payload.init_data)
    user = _get_or_create_user(
        db,
        telegram_user_id=identity.telegram_user_id,
        username=identity.username,
        first_name=identity.first_name,
        last_name=identity.last_name,
        role="customer",
    )
    db.commit()
    token = create_token(
        user_id=str(user.id),
        role=user.role,
        telegram_user_id=user.telegram_user_id,
    )
    return TokenResponse(
        access_token=token,
        role=user.role,
        user_id=str(user.id),
    )


@router.post("/admin/login", response_model=TokenResponse)
def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    if payload.email.lower() != settings.admin_demo_email.lower() or payload.password != settings.admin_demo_password:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    username = payload.username or payload.email.split("@", 1)[0]
    first_name = payload.first_name or "Admin"
    telegram_user_id = _stable_admin_telegram_id(payload.email.lower())
    user = _get_or_create_user(
        db,
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        role="admin",
    )
    user.role = "admin"
    db.commit()
    token = create_token(
        user_id=str(user.id),
        role="admin",
        telegram_user_id=user.telegram_user_id,
    )
    return TokenResponse(
        access_token=token,
        role="admin",
        user_id=str(user.id),
    )


@router.post("/token", response_model=TokenResponse)
def issue_token(payload: TokenRequest, db: Session = Depends(get_db)):
    if settings.auth_enabled:
        raise HTTPException(status_code=403, detail="Legacy dev token route is disabled when AUTH_ENABLED=true")

    user = db.execute(
        select(models.User).where(models.User.telegram_user_id == payload.telegram_user_id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Start an inspection via the bot first.")

    token = create_token(
        user_id=str(user.id),
        role=user.role,
        telegram_user_id=user.telegram_user_id,
    )
    return TokenResponse(
        access_token=token,
        role=user.role,
        user_id=str(user.id),
    )
