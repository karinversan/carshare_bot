import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api_service.app.db.session import get_db
from apps.api_service.app.db import models
from apps.api_service.app.schemas.inspections import (
    CreateInspectionRequest, RunInitialChecksRequest, FinalizeInspectionRequest
)
from apps.api_service.app.services.inspection_service import (
    create_inspection, upload_inspection_image, run_initial_checks,
    run_damage_inference, finalize_inspection
)
from apps.api_service.app.services.inference_client import InferenceServiceError
from apps.api_service.app.services.storage_service import storage_service
from apps.api_service.app.core.config import settings
from packages.shared_py.car_inspection.enums import REQUIRED_SLOTS
from packages.shared_py.car_inspection.enums import InspectionStatus

router = APIRouter(prefix="/inspections", tags=["inspections"])


CLOSED_INSPECTION_STATUSES = {
    InspectionStatus.FINALIZED.value,
    InspectionStatus.CANCELLED.value,
    InspectionStatus.FAILED.value,
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

@router.post("")
def create_inspection_route(payload: CreateInspectionRequest, db: Session = Depends(get_db)):
    inspection, vehicle = create_inspection(
        db,
        vehicle_external_id=payload.vehicle_id,
        inspection_type=payload.inspection_type,
        telegram_user_id=payload.user_telegram_id,
        username=payload.username,
        first_name=payload.first_name,
    )
    db.commit()
    return {
        "data": {
            "inspection_id": inspection.id,
            "status": inspection.status,
            "required_slots": REQUIRED_SLOTS,
            "next_required_slot": REQUIRED_SLOTS[len(inspection.accepted_slots)] if len(inspection.accepted_slots) < len(REQUIRED_SLOTS) else None,
        }
    }

@router.get("/{inspection_id}")
def get_inspection(inspection_id: uuid.UUID, db: Session = Depends(get_db)):
    inspection = db.get(models.InspectionSession, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    vehicle = db.get(models.Vehicle, inspection.vehicle_id)
    images = db.execute(
        select(models.InspectionImage).where(models.InspectionImage.inspection_session_id == inspection.id)
    ).scalars().all()
    return {
        "data": {
            "inspection_id": inspection.id,
            "vehicle_id": vehicle.external_vehicle_id,
            "inspection_type": inspection.inspection_type,
            "status": inspection.status,
            "required_slots": inspection.required_slots,
            "accepted_slots": inspection.accepted_slots,
            "linked_pre_trip_session_id": inspection.linked_pre_trip_session_id,
            "images": [
                {
                    "image_id": img.id,
                    "slot_code": img.slot_code,
                    "status": img.status,
                    "accepted": img.accepted,
                    "rejection_reason": img.rejection_reason,
                    "raw_url": storage_service.presigned_url(settings.s3_bucket_raw_images, img.object_key_raw) if img.object_key_raw else None,
                    "overlay_url": storage_service.presigned_url(settings.s3_bucket_overlays, img.overlay_object_key) if img.overlay_object_key else None,
                    "thumbnail_url": storage_service.presigned_url(settings.s3_bucket_processed_images, img.object_key_thumbnail) if img.object_key_thumbnail else None,
                } for img in images
            ],
        }
    }

@router.post("/{inspection_id}/images")
async def upload_image(
    inspection_id: uuid.UUID,
    file: UploadFile = File(...),
    image_type: str = Form(...),
    slot_code: str | None = Form(None),
    capture_order: int = Form(1),
    db: Session = Depends(get_db),
):
    inspection = db.get(models.InspectionSession, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    _ensure_inspection_open(inspection)
    file_bytes = await file.read()
    try:
        image_row = upload_inspection_image(
            db, inspection, file_bytes, file.filename or "upload.jpg", image_type, slot_code, capture_order
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {"data": {"image_id": image_row.id, "status": image_row.status}}

@router.post("/{inspection_id}/run-initial-checks")
def run_initial_checks_route(
    inspection_id: uuid.UUID,
    payload: RunInitialChecksRequest,
    db: Session = Depends(get_db),
):
    inspection = db.get(models.InspectionSession, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    _ensure_inspection_open(inspection)
    image_row = db.get(models.InspectionImage, payload.image_id)
    if not image_row or image_row.inspection_session_id != inspection.id:
        raise HTTPException(status_code=404, detail="image not found")

    try:
        result = run_initial_checks(db, inspection, image_row, payload.expected_slot)
    except InferenceServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "inference_unavailable",
                "message": "Сервис проверки фото временно недоступен. Попробуйте ещё раз через несколько секунд.",
                "debug": str(exc),
            },
        ) from exc
    db.commit()
    next_slot = None
    if result["accepted"]:
        remaining = [slot for slot in REQUIRED_SLOTS if slot not in inspection.accepted_slots]
        next_slot = remaining[0] if remaining else None
    return {"data": {**result, "next_required_slot": next_slot}}

@router.post("/{inspection_id}/run-damage-inference")
def run_damage_inference_route(
    inspection_id: uuid.UUID,
    force_sync: bool = Query(False, description="Bypass async dispatch and run inference in-process."),
    db: Session = Depends(get_db),
):
    inspection = db.get(models.InspectionSession, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    _ensure_inspection_open(inspection)

    if settings.async_inference and not force_sync:
        # Dispatch to Celery worker for background processing
        from apps.worker_service.app.tasks import run_damage_inference_task
        from packages.shared_py.car_inspection.enums import InspectionStatus
        inspection.status = InspectionStatus.INFERENCE_RUNNING.value
        db.commit()
        run_damage_inference_task.delay(str(inspection_id))
        return {"data": {"inspection_id": inspection.id, "status": inspection.status, "async": True}}

    try:
        run_damage_inference(db, inspection)
    except InferenceServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "inference_unavailable",
                "message": "Сервис анализа повреждений временно недоступен. Попробуйте ещё раз позже.",
                "debug": str(exc),
            },
        ) from exc
    db.commit()
    return {"data": {"inspection_id": inspection.id, "status": inspection.status}}


@router.post("/{inspection_id}/mark-failed")
def mark_failed_route(inspection_id: uuid.UUID, db: Session = Depends(get_db)):
    """Called by worker tasks when inference fails."""
    from packages.shared_py.car_inspection.enums import InspectionStatus
    inspection = db.get(models.InspectionSession, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    inspection.status = InspectionStatus.FAILED.value
    db.commit()
    return {"data": {"inspection_id": inspection.id, "status": inspection.status}}

@router.post("/{inspection_id}/finalize")
def finalize_inspection_route(inspection_id: uuid.UUID, payload: FinalizeInspectionRequest, db: Session = Depends(get_db)):
    inspection = db.get(models.InspectionSession, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="inspection not found")
    if not payload.photos_review_confirmed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "photos_review_not_confirmed",
                "message": "Перед завершением подтвердите, что проверили все фото.",
            },
        )
    try:
        comparison = finalize_inspection(db, inspection)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    db.commit()
    final_count = db.execute(
        select(models.InspectionDamageFinal).where(models.InspectionDamageFinal.inspection_session_id == inspection.id)
    ).scalars().all()
    return {
        "data": {
            "inspection_id": inspection.id,
            "status": inspection.status,
            "canonical_damage_count": len(final_count),
            "comparison_id": comparison.id if comparison else None,
            "comparison_status": inspection.comparison_status,
        }
    }
