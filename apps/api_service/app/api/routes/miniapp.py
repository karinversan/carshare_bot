import uuid
import mimetypes
from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api_service.app.db.session import get_db
from apps.api_service.app.db import models
from apps.api_service.app.schemas.miniapp import DamageDecisionRequest, ManualDamageRequest
from packages.shared_py.car_inspection.enums import ReviewStatus
from packages.shared_py.car_inspection.enums import InspectionStatus
from packages.shared_py.car_inspection.enums import DamageType
from apps.api_service.app.services.storage_service import storage_service
from apps.api_service.app.core.config import settings

router = APIRouter(prefix="/miniapp", tags=["miniapp"])


CLOSED_INSPECTION_STATUSES = {
    InspectionStatus.FINALIZED.value,
    InspectionStatus.CANCELLED.value,
    InspectionStatus.FAILED.value,
}
OPTIONAL_PHOTO_STATUS = (
    InspectionStatus.CAPTURING_OPTIONAL_PHOTOS.value
    if hasattr(InspectionStatus, "CAPTURING_OPTIONAL_PHOTOS")
    else "capturing_optional_photos"
)


def _object_url(bucket: str, key: str | None) -> str | None:
    if not key:
        return None
    return f"/api/s3/{bucket}/{quote(key, safe='/')}"


def _resolve_image_content_type(filename: str | None, content_type: str | None) -> str:
    if content_type and content_type.startswith("image/"):
        return content_type
    guessed, _ = mimetypes.guess_type(filename or "")
    if guessed and guessed.startswith("image/"):
        return guessed
    return "image/jpeg"


def _resolve_image_extension(filename: str | None, content_type: str | None) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].strip().lower()
        if ext in {"jpg", "jpeg", "png", "webp", "bmp", "gif"}:
            return ext
    guessed_ext = mimetypes.guess_extension(_resolve_image_content_type(filename, content_type) or "")
    if guessed_ext:
        return guessed_ext.lstrip(".")
    return "jpg"


def _closeup_payload(image: models.InspectionImage) -> dict:
    return {
        "image_id": str(image.id),
        "slot_code": image.slot_code,
        "raw_url": _object_url(settings.s3_bucket_closeups, image.object_key_raw),
        "comment": image.note,
        "created_at": image.created_at,
    }


def _ensure_inspection_open(inspection: models.InspectionSession) -> None:
    if inspection.status in CLOSED_INSPECTION_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "inspection_closed",
                "status": inspection.status,
                "message": "inspection is already closed",
            },
        )


def _ensure_image_extra_photo_allowed(inspection: models.InspectionSession) -> None:
    if inspection.status != OPTIONAL_PHOTO_STATUS:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "inspection_stage_conflict",
                "status": inspection.status,
                "message": "Image-level extra photos are allowed only before the photo set is confirmed.",
            },
        )


def _ensure_damage_closeup_allowed(inspection: models.InspectionSession) -> None:
    if inspection.status not in {
        InspectionStatus.READY_FOR_REVIEW.value,
        InspectionStatus.UNDER_REVIEW.value,
    }:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "inspection_stage_conflict",
                "status": inspection.status,
                "message": "Damage closeups are available only after inference results are ready.",
            },
        )


def _read_and_validate_closeup_bytes(file_bytes: bytes) -> None:
    max_size = 20 * 1024 * 1024  # 20 MB
    if len(file_bytes) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large ({len(file_bytes)} bytes, max {max_size})")


def _create_closeup_row(
    db: Session,
    *,
    inspection: models.InspectionSession,
    file_bytes: bytes,
    key: str,
    slot_code: str | None,
    content_type: str | None = None,
    comment: str | None = None,
    review_ref_id: uuid.UUID | None = None,
    manual_ref_id: uuid.UUID | None = None,
) -> models.InspectionImage:
    storage_service.put_bytes(
        settings.s3_bucket_closeups,
        key,
        file_bytes,
        _resolve_image_content_type(key, content_type),
    )
    closeup = models.InspectionImage(
        inspection_session_id=inspection.id,
        image_type="optional_closeup",
        slot_code=slot_code,
        status="accepted",
        capture_order=999,
        object_key_raw=key,
        parent_damage_review_id=review_ref_id,
        parent_manual_damage_id=manual_ref_id,
        note=comment,
    )
    db.add(closeup)
    db.commit()
    return closeup

@router.get("/inspections/{inspection_id}")
def get_miniapp_inspection(inspection_id: uuid.UUID, db: Session = Depends(get_db)):
    inspection = db.get(models.InspectionSession, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    _ensure_inspection_open(inspection)
    vehicle = db.get(models.Vehicle, inspection.vehicle_id)

    images = db.execute(
        select(models.InspectionImage)
        .where(models.InspectionImage.inspection_session_id == inspection.id)
        .order_by(models.InspectionImage.created_at.asc())
    ).scalars().all()
    closeups = [
        img for img in images
        if img.image_type == "optional_closeup"
    ]
    closeups_by_review: dict[str, list[dict]] = {}
    closeups_by_manual: dict[str, list[dict]] = {}
    closeups_by_slot: dict[str, list[dict]] = {}
    image_extra_photos: list[dict] = []
    for closeup in closeups:
        payload = _closeup_payload(closeup)
        has_parent = False
        if closeup.parent_damage_review_id:
            closeups_by_review.setdefault(str(closeup.parent_damage_review_id), []).append(payload)
            has_parent = True
        if closeup.parent_manual_damage_id:
            closeups_by_manual.setdefault(str(closeup.parent_manual_damage_id), []).append(payload)
            has_parent = True
        if not has_parent:
            image_extra_photos.append(payload)
            if closeup.slot_code:
                closeups_by_slot.setdefault(closeup.slot_code, []).append(payload)

    payload_images = []
    valid_damage_types = {damage.value for damage in DamageType}
    ui_min_confidence = 0.1

    for img in images:
        if img.image_type != "required_view" or not img.accepted:
            continue
        preds = db.execute(
            select(models.PredictedDamage, models.DamageReview)
            .join(models.DamageReview, models.DamageReview.predicted_damage_id == models.PredictedDamage.id)
            .where(models.PredictedDamage.inspection_image_id == img.id)
        ).all()
        manuals = db.execute(
            select(models.ManualDamage).where(models.ManualDamage.base_image_id == img.id)
        ).scalars().all()
        predicted_payload = []
        for pred, review in preds:
            if review.review_status == ReviewStatus.REJECTED.value:
                continue
            if (pred.confidence or 0.0) < ui_min_confidence:
                continue
            if pred.damage_type not in valid_damage_types:
                continue
            predicted_payload.append(
                {
                    "damage_id": str(pred.id),
                    "damage_type": pred.damage_type,
                    "confidence": pred.confidence,
                    "bbox_norm": pred.bbox_norm,
                    "centroid_x": pred.centroid_x,
                    "centroid_y": pred.centroid_y,
                    "area_norm": pred.area_norm,
                    "polygon_json": pred.polygon_json,
                    "review_status": review.review_status,
                    "review_id": str(review.id),
                    "review_note": review.review_note,
                    "closeups": closeups_by_review.get(str(review.id), []),
                }
            )

        payload_images.append({
            "image_id": str(img.id),
            "slot_code": img.slot_code,
            "status": img.status,
            "raw_url": _object_url(settings.s3_bucket_raw_images, img.object_key_raw),
            "overlay_url": _object_url(settings.s3_bucket_overlays, img.overlay_object_key),
            "predicted_damages": predicted_payload,
            "manual_damages": [
                {
                    "manual_damage_id": str(md.id),
                    "damage_type": md.damage_type,
                    "bbox_norm": md.bbox_norm,
                    "polygon_json": md.polygon_json,
                    "severity_hint": md.severity_hint,
                    "note": md.note,
                    "closeups": closeups_by_manual.get(str(md.id), []),
                } for md in manuals
            ],
            "image_closeups": closeups_by_slot.get(img.slot_code or "", []),
        })

    return {
        "data": {
            "inspection_id": str(inspection.id),
            "status": inspection.status,
            "required_slots": inspection.required_slots,
            "accepted_slots": inspection.accepted_slots,
            "vehicle_id": vehicle.external_vehicle_id if vehicle else None,
            "vehicle_plate": vehicle.license_plate if vehicle else None,
            "vehicle_title": " ".join(part for part in [vehicle.make, vehicle.model] if part).strip() if vehicle else None,
            "images": payload_images,
            "extra_photos": image_extra_photos,
        }
    }

def _update_review(damage_or_review_id: uuid.UUID, review_status: str, payload: DamageDecisionRequest, db: Session):
    review = db.get(models.DamageReview, damage_or_review_id)
    if not review:
        review = db.execute(
            select(models.DamageReview).where(models.DamageReview.predicted_damage_id == damage_or_review_id)
        ).scalar_one_or_none()
    if not review:
        predicted_damage = db.get(models.PredictedDamage, damage_or_review_id)
        if not predicted_damage:
            raise HTTPException(status_code=404, detail="review not found")
        base_image = db.get(models.InspectionImage, predicted_damage.inspection_image_id)
        if not base_image:
            raise HTTPException(status_code=404, detail="base image not found")
        review = models.DamageReview(
            predicted_damage_id=predicted_damage.id,
            inspection_session_id=base_image.inspection_session_id,
            review_status=ReviewStatus.PENDING.value,
        )
        db.add(review)
        db.flush()
    review.review_status = review_status
    review.severity_hint = payload.severity_hint
    review.review_note = payload.reason or payload.note
    review.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"data": {"review_id": review.id, "review_status": review.review_status}}

@router.post("/damages/{damage_id}/confirm")
def confirm_damage(damage_id: uuid.UUID, payload: DamageDecisionRequest, db: Session = Depends(get_db)):
    return _update_review(damage_id, ReviewStatus.CONFIRMED.value, payload, db)

@router.post("/damages/{damage_id}/reject")
def reject_damage(damage_id: uuid.UUID, payload: DamageDecisionRequest, db: Session = Depends(get_db)):
    return _update_review(damage_id, ReviewStatus.REJECTED.value, payload, db)

@router.post("/damages/{damage_id}/uncertain")
def uncertain_damage(damage_id: uuid.UUID, payload: DamageDecisionRequest, db: Session = Depends(get_db)):
    return _update_review(damage_id, ReviewStatus.UNCERTAIN.value, payload, db)

@router.post("/damages/manual")
def create_manual_damage(payload: ManualDamageRequest, db: Session = Depends(get_db)):
    inspection = db.get(models.InspectionSession, payload.inspection_session_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    _ensure_inspection_open(inspection)
    image = db.get(models.InspectionImage, payload.base_image_id)
    if not image:
        raise HTTPException(status_code=404, detail="image not found")

    bbox = payload.bbox_norm
    centroid_x = (bbox["x1"] + bbox["x2"]) / 2
    centroid_y = (bbox["y1"] + bbox["y2"]) / 2
    area_norm = abs((bbox["x2"] - bbox["x1"]) * (bbox["y2"] - bbox["y1"]))

    user = db.get(models.User, inspection.user_id)
    manual = models.ManualDamage(
        inspection_session_id=inspection.id,
        base_image_id=image.id,
        damage_type=payload.damage_type,
        bbox_norm=payload.bbox_norm,
        centroid_x=centroid_x,
        centroid_y=centroid_y,
        area_norm=area_norm,
        polygon_json=[
            [bbox["x1"], bbox["y1"]],
            [bbox["x2"], bbox["y1"]],
            [bbox["x2"], bbox["y2"]],
            [bbox["x1"], bbox["y2"]],
        ],
        severity_hint=payload.severity_hint,
        note=payload.note,
        created_by_user_id=user.id,
    )
    db.add(manual)
    db.commit()
    return {"data": {"manual_damage_id": manual.id}}

@router.post("/images/{image_id}/attach-closeup")
async def attach_closeup(
    image_id: uuid.UUID,
    file: UploadFile = File(...),
    damage_ref_type: str | None = Form(default=None),
    damage_ref_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    image = db.get(models.InspectionImage, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="image not found")
    inspection = db.get(models.InspectionSession, image.inspection_session_id)
    _ensure_inspection_open(inspection)
    file_bytes = await file.read()
    _read_and_validate_closeup_bytes(file_bytes)
    if (damage_ref_type and not damage_ref_id) or (damage_ref_id and not damage_ref_type):
        raise HTTPException(status_code=400, detail="damage_ref_type and damage_ref_id must be provided together")

    if damage_ref_type not in {None, "predicted_review", "manual"}:
        raise HTTPException(status_code=400, detail="unsupported damage_ref_type")

    if damage_ref_type is None and damage_ref_id is None:
        _ensure_image_extra_photo_allowed(inspection)
    else:
        _ensure_damage_closeup_allowed(inspection)

    review_ref_id: uuid.UUID | None = None
    manual_ref_id: uuid.UUID | None = None
    if damage_ref_type and damage_ref_id:
        try:
            parsed_ref_id = uuid.UUID(damage_ref_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid damage_ref_id") from exc
        if damage_ref_type == "predicted_review":
            review_ref_id = parsed_ref_id
        if damage_ref_type == "manual":
            manual_ref_id = parsed_ref_id

    key_group = damage_ref_type or "image"
    key_ref = damage_ref_id or str(image.id)
    ext = _resolve_image_extension(file.filename, file.content_type)
    key = f"{inspection.id}/{key_group}/{key_ref}/{uuid.uuid4()}.{ext}"
    # Image-level extra photos are global for the inspection and must not be bound to a required slot.
    slot_code = image.slot_code if damage_ref_type else None
    closeup = _create_closeup_row(
        db,
        inspection=inspection,
        file_bytes=file_bytes,
        key=key,
        slot_code=slot_code,
        content_type=file.content_type,
        review_ref_id=review_ref_id,
        manual_ref_id=manual_ref_id,
    )
    return {
        "data": {
            "image_id": closeup.id,
            "status": closeup.status,
            "raw_url": _object_url(settings.s3_bucket_closeups, closeup.object_key_raw),
            "comment": closeup.note,
        }
    }


@router.post("/inspections/{inspection_id}/attach-extra-photo")
async def attach_extra_photo(
    inspection_id: uuid.UUID,
    file: UploadFile = File(...),
    comment: str = Form(...),
    db: Session = Depends(get_db),
):
    inspection = db.get(models.InspectionSession, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    _ensure_inspection_open(inspection)
    _ensure_image_extra_photo_allowed(inspection)

    file_bytes = await file.read()
    _read_and_validate_closeup_bytes(file_bytes)
    clean_comment = comment.strip()
    if not clean_comment:
        raise HTTPException(status_code=400, detail="comment is required")

    ext = _resolve_image_extension(file.filename, file.content_type)
    key = f"{inspection.id}/image/extra/{uuid.uuid4()}.{ext}"
    closeup = _create_closeup_row(
        db,
        inspection=inspection,
        file_bytes=file_bytes,
        key=key,
        slot_code=None,
        content_type=file.content_type,
        comment=clean_comment,
    )
    return {
        "data": {
            "image_id": closeup.id,
            "status": closeup.status,
            "raw_url": _object_url(settings.s3_bucket_closeups, closeup.object_key_raw),
        }
    }
