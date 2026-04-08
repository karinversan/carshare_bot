import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api_service.app.core.auth import AuthUser, require_admin
from apps.api_service.app.db.session import get_db
from apps.api_service.app.db import models
from apps.api_service.app.schemas.admin import UpdateAdminCaseStatusRequest
from apps.api_service.app.services.storage_service import storage_service
from apps.api_service.app.core.config import settings
from apps.api_service.app.services.rental_service import assign_admin_case

router = APIRouter(prefix="/admin-cases", tags=["admin"])


def _image_payload(image: models.InspectionImage | None, bucket: str) -> dict | None:
    if not image:
        return None
    return {
        "image_id": str(image.id),
        "slot_code": image.slot_code,
        "raw_url": storage_service.presigned_url(bucket, image.object_key_raw) if image.object_key_raw else None,
        "overlay_url": storage_service.presigned_url(settings.s3_bucket_overlays, image.overlay_object_key) if image.overlay_object_key else None,
    }


def _assignee_name(db: Session, user_id: uuid.UUID | None) -> str | None:
    if not user_id:
        return None
    user = db.get(models.User, user_id)
    if not user:
        return None
    return user.first_name or user.username


def _closeups_for_final_damage(db: Session, final_damage: models.InspectionDamageFinal | None) -> list[dict]:
    if not final_damage:
        return []

    stmt = select(models.InspectionImage).where(models.InspectionImage.image_type == "optional_closeup")
    if final_damage.source_predicted_damage_id:
        review = db.execute(
            select(models.DamageReview).where(
                models.DamageReview.predicted_damage_id == final_damage.source_predicted_damage_id
            )
        ).scalar_one_or_none()
        if not review:
            return []
        stmt = stmt.where(models.InspectionImage.parent_damage_review_id == review.id)
    elif final_damage.source_manual_damage_id:
        stmt = stmt.where(models.InspectionImage.parent_manual_damage_id == final_damage.source_manual_damage_id)
    else:
        return []

    images = db.execute(stmt).scalars().all()
    return [
        {
            "image_id": str(image.id),
            "raw_url": storage_service.presigned_url(settings.s3_bucket_closeups, image.object_key_raw),
            "slot_code": image.slot_code,
        }
        for image in images
    ]

@router.get("")
def list_admin_cases(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_admin),
):
    stmt = select(models.AdminCase).order_by(models.AdminCase.opened_at.desc())
    if status:
        stmt = stmt.where(models.AdminCase.status == status)
    cases = db.execute(stmt).scalars().all()
    return {
        "data": [
            {
                "id": str(c.id),
                "comparison_id": str(c.comparison_id),
                "vehicle_id": (db.get(models.Vehicle, c.vehicle_id).external_vehicle_id if db.get(models.Vehicle, c.vehicle_id) else str(c.vehicle_id)),
                "status": c.status,
                "priority": c.priority,
                "title": c.title,
                "summary": c.summary,
                "opened_at": c.opened_at,
                "assignee_name": _assignee_name(db, c.assigned_to_user_id),
            } for c in cases
        ]
    }

@router.get("/{case_id}")
def get_admin_case(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_admin),
):
    case = db.get(models.AdminCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    comparison = db.get(models.InspectionComparison, case.comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="comparison not found for this case")
    matches = db.execute(
        select(models.DamageMatch).where(models.DamageMatch.comparison_id == comparison.id)
    ).scalars().all()
    vehicle = db.get(models.Vehicle, case.vehicle_id)
    return {
        "data": {
            "id": str(case.id),
            "vehicle_id": vehicle.external_vehicle_id if vehicle else str(case.vehicle_id),
            "status": case.status,
            "title": case.title,
            "summary": case.summary,
            "assignee_name": _assignee_name(db, case.assigned_to_user_id),
            "comparison": comparison.summary_json,
            "matches": [
                {
                    "id": str(m.id),
                    "view_slot": m.view_slot,
                    "status": m.status,
                    "match_score": m.match_score,
                    "pre_damage_id": str(m.pre_damage_id) if m.pre_damage_id else None,
                    "post_damage_id": str(m.post_damage_id) if m.post_damage_id else None,
                    "pre_damage": (
                        lambda damage: {
                            "damage_id": str(damage.id),
                            "damage_type": damage.damage_type,
                            "severity_hint": damage.severity_hint,
                            "note": damage.note,
                            "image": _image_payload(db.get(models.InspectionImage, damage.base_image_id), settings.s3_bucket_raw_images),
                        } if damage else None
                    )(db.get(models.InspectionDamageFinal, m.pre_damage_id) if m.pre_damage_id else None),
                    "post_damage": (
                        lambda damage: {
                            "damage_id": str(damage.id),
                            "damage_type": damage.damage_type,
                            "severity_hint": damage.severity_hint,
                            "note": damage.note,
                            "image": _image_payload(db.get(models.InspectionImage, damage.base_image_id), settings.s3_bucket_raw_images),
                            "closeups": _closeups_for_final_damage(db, damage),
                        } if damage else None
                    )(db.get(models.InspectionDamageFinal, m.post_damage_id) if m.post_damage_id else None),
                } for m in matches
            ]
        }
    }

@router.post("/{case_id}/status")
def update_case_status(
    case_id: uuid.UUID,
    payload: UpdateAdminCaseStatusRequest,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_admin),
):
    case = db.get(models.AdminCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    case.status = payload.status
    case.resolved_note = payload.resolved_note
    case.updated_at = datetime.now(timezone.utc)
    if payload.status.startswith("resolved") or payload.status == "dismissed":
        case.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"data": {"id": str(case.id), "status": case.status}}


@router.post("/{case_id}/assign")
def assign_case(
    case_id: uuid.UUID,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(require_admin),
):
    case = db.get(models.AdminCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    current_db_user = None
    try:
        current_db_user = db.get(models.User, uuid.UUID(current_user.user_id))
    except (ValueError, TypeError):
        current_db_user = None
    user = assign_admin_case(
        db,
        case=case,
        first_name=payload.get("first_name") or (current_db_user.first_name if current_db_user else None),
        username=payload.get("username") or (current_db_user.username if current_db_user else None),
    )
    db.commit()
    return {
        "data": {
            "id": str(case.id),
            "assigned_to_user_id": str(user.id),
            "assignee_name": user.first_name or user.username,
        }
    }
