import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api_service.app.core.auth import (
    AuthUser,
    ensure_comparison_access,
    require_auth_or_internal,
    require_internal_service,
)
from apps.api_service.app.db.session import get_db
from apps.api_service.app.db import models
from apps.api_service.app.services.comparison_service import run_post_trip_comparison

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


class RunComparisonRequest(BaseModel):
    post_session_id: uuid.UUID


@router.post("/run")
def run_comparison(
    payload: RunComparisonRequest,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_internal_service),
):
    post_session_id = payload.post_session_id
    post_session = db.get(models.InspectionSession, post_session_id)
    if not post_session:
        raise HTTPException(status_code=404, detail="post session not found")
    comparison = run_post_trip_comparison(db, post_session)
    db.commit()
    if not comparison:
        return {"data": {"status": post_session.comparison_status}}
    return {"data": {"comparison_id": comparison.id, "status": comparison.status}}

@router.get("/{comparison_id}")
def get_comparison(
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_auth_or_internal),
):
    comparison = db.get(models.InspectionComparison, comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="comparison not found")
    ensure_comparison_access(db, comparison, current_user)
    matches = db.execute(
        select(models.DamageMatch).where(models.DamageMatch.comparison_id == comparison.id)
    ).scalars().all()
    return {
        "data": {
            "comparison_id": comparison.id,
            "status": comparison.status,
            "summary": comparison.summary_json,
            "matches": [
                {
                    "id": m.id,
                    "view_slot": m.view_slot,
                    "status": m.status,
                    "match_score": m.match_score,
                    "pre_damage_id": m.pre_damage_id,
                    "post_damage_id": m.post_damage_id,
                } for m in matches
            ]
        }
    }
