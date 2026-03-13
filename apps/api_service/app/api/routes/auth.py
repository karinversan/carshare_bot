"""Auth routes — token issuance for demo/development.

In production, tokens would be issued after Telegram WebApp initData validation.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api_service.app.db.session import get_db
from apps.api_service.app.db import models
from apps.api_service.app.core.auth import create_token

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    telegram_user_id: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=TokenResponse)
def issue_token(payload: TokenRequest, db: Session = Depends(get_db)):
    """Issue a JWT token for a known Telegram user.

    In production, this would validate Telegram WebApp initData.
    For the MVP, it just looks up the user by telegram_user_id.
    """
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
    return TokenResponse(access_token=token)
