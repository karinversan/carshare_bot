import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, select

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


def _user_name_map(db: Session, user_ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    resolved_ids = {user_id for user_id in user_ids if user_id}
    if not resolved_ids:
        return {}

    users = db.execute(select(models.User).where(models.User.id.in_(resolved_ids))).scalars().all()
    return {user.id: (user.first_name or user.username or "") for user in users}


def _vehicle_external_id_map(db: Session, vehicle_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    resolved_ids = {vehicle_id for vehicle_id in vehicle_ids}
    if not resolved_ids:
        return {}

    vehicles = db.execute(select(models.Vehicle).where(models.Vehicle.id.in_(resolved_ids))).scalars().all()
    return {vehicle.id: vehicle.external_vehicle_id for vehicle in vehicles}


def _final_damage_payload_map(
    db: Session,
    final_damages: list[models.InspectionDamageFinal],
) -> dict[uuid.UUID, dict]:
    if not final_damages:
        return {}

    image_ids = {damage.base_image_id for damage in final_damages if damage.base_image_id}
    images = db.execute(select(models.InspectionImage).where(models.InspectionImage.id.in_(image_ids))).scalars().all()
    images_by_id = {image.id: image for image in images}

    predicted_damage_ids = {
        damage.source_predicted_damage_id
        for damage in final_damages
        if damage.source_predicted_damage_id
    }
    manual_damage_ids = {
        damage.source_manual_damage_id
        for damage in final_damages
        if damage.source_manual_damage_id
    }

    reviews_by_predicted_id: dict[uuid.UUID, models.DamageReview] = {}
    if predicted_damage_ids:
        reviews = db.execute(
            select(models.DamageReview).where(models.DamageReview.predicted_damage_id.in_(predicted_damage_ids))
        ).scalars().all()
        reviews_by_predicted_id = {review.predicted_damage_id: review for review in reviews}
    review_ids = {review.id for review in reviews_by_predicted_id.values()}

    closeups_by_review_id: dict[uuid.UUID, list[dict]] = {}
    closeups_by_manual_id: dict[uuid.UUID, list[dict]] = {}
    closeup_filters = []
    if review_ids:
        closeup_filters.append(models.InspectionImage.parent_damage_review_id.in_(review_ids))
    if manual_damage_ids:
        closeup_filters.append(models.InspectionImage.parent_manual_damage_id.in_(manual_damage_ids))

    if closeup_filters:
        closeups = db.execute(
            select(models.InspectionImage)
            .where(models.InspectionImage.image_type == "optional_closeup")
            .where(or_(*closeup_filters))
        ).scalars().all()
        for closeup in closeups:
            payload = {
                "image_id": str(closeup.id),
                "raw_url": storage_service.presigned_url(settings.s3_bucket_closeups, closeup.object_key_raw),
                "slot_code": closeup.slot_code,
            }
            if closeup.parent_damage_review_id:
                closeups_by_review_id.setdefault(closeup.parent_damage_review_id, []).append(payload)
            if closeup.parent_manual_damage_id:
                closeups_by_manual_id.setdefault(closeup.parent_manual_damage_id, []).append(payload)

    return {
        damage.id: {
            "damage_id": str(damage.id),
            "damage_type": damage.damage_type,
            "severity_hint": damage.severity_hint,
            "note": damage.note,
            "image": _image_payload(images_by_id.get(damage.base_image_id), settings.s3_bucket_raw_images),
            "closeups": (
                closeups_by_review_id.get(reviews_by_predicted_id[damage.source_predicted_damage_id].id, [])
                if damage.source_predicted_damage_id and damage.source_predicted_damage_id in reviews_by_predicted_id
                else closeups_by_manual_id.get(damage.source_manual_damage_id, [])
                if damage.source_manual_damage_id
                else []
            ),
        }
        for damage in final_damages
    }

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
    vehicle_external_ids = _vehicle_external_id_map(db, [case.vehicle_id for case in cases])
    assignee_names = _user_name_map(db, [case.assigned_to_user_id for case in cases])
    return {
        "data": [
            {
                "id": str(c.id),
                "comparison_id": str(c.comparison_id),
                "vehicle_id": vehicle_external_ids.get(c.vehicle_id, str(c.vehicle_id)),
                "status": c.status,
                "priority": c.priority,
                "title": c.title,
                "summary": c.summary,
                "opened_at": c.opened_at,
                "assignee_name": assignee_names.get(c.assigned_to_user_id),
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
    vehicle_external_ids = _vehicle_external_id_map(db, [case.vehicle_id])
    assignee_names = _user_name_map(db, [case.assigned_to_user_id])
    final_damage_ids = {
        damage_id
        for match in matches
        for damage_id in (match.pre_damage_id, match.post_damage_id)
        if damage_id
    }
    final_damages = db.execute(
        select(models.InspectionDamageFinal).where(models.InspectionDamageFinal.id.in_(final_damage_ids))
    ).scalars().all() if final_damage_ids else []
    damage_payloads = _final_damage_payload_map(db, final_damages)
    return {
        "data": {
            "id": str(case.id),
            "vehicle_id": vehicle_external_ids.get(case.vehicle_id, str(case.vehicle_id)),
            "status": case.status,
            "title": case.title,
            "summary": case.summary,
            "assignee_name": assignee_names.get(case.assigned_to_user_id),
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
                        {
                            key: value
                            for key, value in damage_payloads[m.pre_damage_id].items()
                            if key != "closeups"
                        }
                        if m.pre_damage_id and m.pre_damage_id in damage_payloads
                        else None
                    ),
                    "post_damage": damage_payloads.get(m.post_damage_id),
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
