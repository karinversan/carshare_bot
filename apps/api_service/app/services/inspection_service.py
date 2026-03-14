import base64
import hashlib
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api_service.app.core.config import settings
from apps.api_service.app.db import models
from apps.api_service.app.services.comparison_service import run_post_trip_comparison
from apps.api_service.app.services.inference_client import inference_client
from apps.api_service.app.services.storage_service import storage_service
from packages.shared_py.car_inspection.enums import (
    ComparisonStatus,
    ImageStatus,
    InspectionStatus,
    InspectionType,
    REQUIRED_SLOTS,
    ReviewStatus,
)

MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _raw_image_key(inspection_id, slot_code, filename) -> str:
    suffix = filename.split(".")[-1] if "." in filename else "jpg"
    return f"{inspection_id}/{slot_code}/{uuid.uuid4()}.{suffix}"


def _image_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()[:32]


def _load_image_metadata(file_bytes: bytes) -> tuple[int, int]:
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image.verify()
        image = Image.open(io.BytesIO(file_bytes))
        return image.size
    except Exception as exc:
        raise ValueError(f"Invalid image file: {exc}") from exc


def _accepted_required_images(db: Session, inspection_id):
    return db.execute(
        select(models.InspectionImage).where(
            models.InspectionImage.inspection_session_id == inspection_id,
            models.InspectionImage.accepted == True,  # noqa: E712
            models.InspectionImage.image_type == "required_view",
        )
    ).scalars().all()


def _duplicate_image(db: Session, inspection_id, phash: str):
    return db.execute(
        select(models.InspectionImage).where(
            models.InspectionImage.inspection_session_id == inspection_id,
            models.InspectionImage.phash == phash,
            models.InspectionImage.accepted == True,  # noqa: E712
        )
    ).scalar_one_or_none()


def _predicted_damages_for_image(db: Session, image_id):
    return db.execute(
        select(models.PredictedDamage).where(models.PredictedDamage.inspection_image_id == image_id)
    ).scalars().all()


def _manual_damages_for_image(db: Session, image_id):
    return db.execute(
        select(models.ManualDamage).where(models.ManualDamage.base_image_id == image_id)
    ).scalars().all()


def _final_rows_for_predicted_damage(db: Session, predicted_damage_id):
    return db.execute(
        select(models.InspectionDamageFinal).where(
            models.InspectionDamageFinal.source_predicted_damage_id == predicted_damage_id
        )
    ).scalars().all()


def _final_rows_for_manual_damage(db: Session, manual_damage_id):
    return db.execute(
        select(models.InspectionDamageFinal).where(
            models.InspectionDamageFinal.source_manual_damage_id == manual_damage_id
        )
    ).scalars().all()


def _final_rows_for_base_image(db: Session, image_id):
    return db.execute(
        select(models.InspectionDamageFinal).where(models.InspectionDamageFinal.base_image_id == image_id)
    ).scalars().all()


def _review_for_predicted_damage(db: Session, predicted_damage_id):
    return db.execute(
        select(models.DamageReview).where(models.DamageReview.predicted_damage_id == predicted_damage_id)
    ).scalar_one_or_none()


def _closeups_query(db: Session, *, review_id: uuid.UUID | None = None, manual_id: uuid.UUID | None = None):
    stmt = select(models.InspectionImage).where(models.InspectionImage.image_type == "optional_closeup")
    if review_id:
        stmt = stmt.where(models.InspectionImage.parent_damage_review_id == review_id)
    if manual_id:
        stmt = stmt.where(models.InspectionImage.parent_manual_damage_id == manual_id)
    return db.execute(stmt).scalars().all()


def get_or_create_user(db: Session, telegram_user_id: int, username: Optional[str], first_name: Optional[str]):
    user = db.execute(
        select(models.User).where(models.User.telegram_user_id == telegram_user_id)
    ).scalar_one_or_none()
    if user:
        return user
    user = models.User(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        role="customer",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def get_or_create_vehicle(db: Session, external_vehicle_id: str):
    vehicle = db.execute(
        select(models.Vehicle).where(models.Vehicle.external_vehicle_id == external_vehicle_id)
    ).scalar_one_or_none()
    if vehicle:
        return vehicle
    vehicle = models.Vehicle(external_vehicle_id=external_vehicle_id, active=True)
    db.add(vehicle)
    db.flush()
    return vehicle


def _latest_finalized_pre_trip(db: Session, vehicle_id):
    return db.execute(
        select(models.InspectionSession)
        .where(
            models.InspectionSession.vehicle_id == vehicle_id,
            models.InspectionSession.inspection_type == InspectionType.PRE_TRIP.value,
            models.InspectionSession.status == InspectionStatus.FINALIZED.value,
        )
        .order_by(models.InspectionSession.started_at.desc())
    ).scalars().first()


def create_inspection(
    db: Session,
    vehicle_external_id: str,
    inspection_type: str,
    telegram_user_id: int,
    username: str | None,
    first_name: str | None,
):
    user = get_or_create_user(db, telegram_user_id, username, first_name)
    vehicle = get_or_create_vehicle(db, vehicle_external_id)

    linked_pre_trip_session_id = None
    if inspection_type == InspectionType.POST_TRIP.value:
        latest_pre = _latest_finalized_pre_trip(db, vehicle.id)
        linked_pre_trip_session_id = latest_pre.id if latest_pre else None

    inspection = models.InspectionSession(
        vehicle_id=vehicle.id,
        user_id=user.id,
        inspection_type=inspection_type,
        status=InspectionStatus.CAPTURING_REQUIRED_VIEWS.value,
        linked_pre_trip_session_id=linked_pre_trip_session_id,
        required_slots=REQUIRED_SLOTS,
        accepted_slots=[],
        started_at=_utcnow(),
        comparison_status=ComparisonStatus.NOT_RUN.value,
    )
    db.add(inspection)
    db.flush()
    return inspection, vehicle


def _delete_closeup_rows(db: Session, *, review_id: uuid.UUID | None = None, manual_id: uuid.UUID | None = None):
    for closeup in _closeups_query(db, review_id=review_id, manual_id=manual_id):
        storage_service.delete_object(settings.s3_bucket_closeups, closeup.object_key_raw)
        db.delete(closeup)


def _delete_image_objects(image_row: models.InspectionImage) -> None:
    storage_service.delete_object(settings.s3_bucket_raw_images, image_row.object_key_raw)
    storage_service.delete_object(settings.s3_bucket_processed_images, image_row.object_key_processed)
    storage_service.delete_object(settings.s3_bucket_processed_images, image_row.object_key_thumbnail)
    storage_service.delete_object(settings.s3_bucket_overlays, image_row.overlay_object_key)


def _delete_predicted_damage_state(db: Session, predicted_damage: models.PredictedDamage) -> None:
    review = _review_for_predicted_damage(db, predicted_damage.id)
    if review:
        _delete_closeup_rows(db, review_id=review.id)
        for final in _final_rows_for_predicted_damage(db, predicted_damage.id):
            db.delete(final)
        db.delete(review)
    db.delete(predicted_damage)


def _delete_manual_damage_state(db: Session, manual_damage: models.ManualDamage) -> None:
    _delete_closeup_rows(db, manual_id=manual_damage.id)
    for final in _final_rows_for_manual_damage(db, manual_damage.id):
        db.delete(final)
    db.delete(manual_damage)


def _purge_image_row(db: Session, image_row: models.InspectionImage):
    for predicted_damage in _predicted_damages_for_image(db, image_row.id):
        _delete_predicted_damage_state(db, predicted_damage)

    for manual_damage in _manual_damages_for_image(db, image_row.id):
        _delete_manual_damage_state(db, manual_damage)

    for final in _final_rows_for_base_image(db, image_row.id):
        db.delete(final)

    _delete_image_objects(image_row)
    db.delete(image_row)


def _replace_slot_image(db: Session, inspection: models.InspectionSession, slot_code: str, keep_image_id: uuid.UUID):
    superseded = db.execute(
        select(models.InspectionImage).where(
            models.InspectionImage.inspection_session_id == inspection.id,
            models.InspectionImage.image_type == "required_view",
            models.InspectionImage.slot_code == slot_code,
            models.InspectionImage.id != keep_image_id,
        )
    ).scalars().all()
    for old_image in superseded:
        _purge_image_row(db, old_image)


def upload_inspection_image(
    db: Session,
    inspection: models.InspectionSession,
    file_bytes: bytes,
    filename: str,
    image_type: str,
    slot_code: str | None,
    capture_order: int,
):
    if len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise ValueError(f"Image too large: {len(file_bytes)} bytes (max {MAX_IMAGE_SIZE_BYTES})")

    width, height = _load_image_metadata(file_bytes)
    phash = _image_hash(file_bytes)
    duplicate = _duplicate_image(db, inspection.id, phash)

    object_key = _raw_image_key(inspection.id, slot_code or "misc", filename)
    storage_service.put_bytes(settings.s3_bucket_raw_images, object_key, file_bytes, "image/jpeg")

    row = models.InspectionImage(
        inspection_session_id=inspection.id,
        image_type=image_type,
        slot_code=slot_code,
        status=ImageStatus.DUPLICATE_SUPERSEDED.value if duplicate else ImageStatus.UPLOADED.value,
        capture_order=capture_order,
        object_key_raw=object_key,
        width=width,
        height=height,
        phash=phash,
        duplicate_of_image_id=duplicate.id if duplicate else None,
        created_at=_utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def _duplicate_result(expected_slot: str) -> dict:
    return {
        "accepted": False,
        "expected_slot": expected_slot,
        "predicted_view": expected_slot,
        "view_score": 1.0,
        "quality_label": "duplicate_upload",
        "quality_score": 1.0,
        "rejection_reason": "duplicate_upload",
        "car_present": None,
        "car_confidence": None,
        "car_bbox": None,
        "model_backend": "local-dedup",
    }


def _apply_quality_result(image_row: models.InspectionImage, result: dict) -> None:
    image_row.car_present = result["car_present"]
    image_row.car_confidence = result["car_confidence"]
    image_row.car_bbox = result.get("car_bbox")
    image_row.quality_label = result["quality_label"]
    image_row.quality_score = result["quality_score"]
    image_row.view_label = result.get("predicted_view")
    image_row.view_score = result.get("view_score", 1.0)
    image_row.accepted = result["accepted"]
    image_row.rejection_reason = result.get("rejection_reason")
    image_row.pipeline_version = "online-v1"
    image_row.status = ImageStatus.ACCEPTED.value if result["accepted"] else ImageStatus.REJECTED.value


def _sync_required_slot_progress(inspection: models.InspectionSession, expected_slot: str) -> None:
    if expected_slot not in inspection.accepted_slots:
        inspection.accepted_slots = [*inspection.accepted_slots, expected_slot]
    if set(inspection.accepted_slots) == set(REQUIRED_SLOTS):
        inspection.status = InspectionStatus.READY_FOR_INFERENCE.value


def run_initial_checks(db: Session, inspection: models.InspectionSession, image_row: models.InspectionImage, expected_slot: str):
    if image_row.duplicate_of_image_id:
        result = _duplicate_result(expected_slot)
        _purge_image_row(db, image_row)
        db.flush()
        return result

    file_bytes = storage_service.get_bytes(settings.s3_bucket_raw_images, image_row.object_key_raw)
    result = inference_client.quality_view_predict(file_bytes, f"{image_row.id}.jpg", expected_slot)
    _apply_quality_result(image_row, result)

    if not result["accepted"]:
        _purge_image_row(db, image_row)
        db.flush()
        return result

    image_row.slot_code = expected_slot
    _replace_slot_image(db, inspection, expected_slot, image_row.id)
    _sync_required_slot_progress(inspection, expected_slot)
    db.flush()
    return result


def _clear_prediction_state_for_image(db: Session, image_row: models.InspectionImage) -> None:
    for predicted_damage in _predicted_damages_for_image(db, image_row.id):
        _delete_predicted_damage_state(db, predicted_damage)
    storage_service.delete_object(settings.s3_bucket_overlays, image_row.overlay_object_key)
    image_row.overlay_object_key = None


def _save_overlay_if_present(inspection: models.InspectionSession, image_row: models.InspectionImage, response: dict) -> None:
    if not response.get("overlay_png_b64"):
        return
    overlay_key = f"overlays/{inspection.id}/{image_row.slot_code}/{image_row.id}_overlay.png"
    overlay_bytes = base64.b64decode(response["overlay_png_b64"])
    storage_service.put_bytes(settings.s3_bucket_overlays, overlay_key, overlay_bytes, "image/png")
    image_row.overlay_object_key = overlay_key


def _create_predicted_damage_rows(db: Session, inspection: models.InspectionSession, image_row: models.InspectionImage, response: dict) -> None:
    high_conf = settings.damage_auto_confirm_confidence
    low_conf = settings.damage_auto_uncertain_confidence

    def auto_decision(confidence: float) -> tuple[str, str]:
        if confidence >= high_conf:
            return ReviewStatus.CONFIRMED.value, "auto_high_confidence"
        if confidence >= low_conf:
            return ReviewStatus.UNCERTAIN.value, "auto_low_confidence"
        return ReviewStatus.REJECTED.value, "auto_rejected_low_confidence"

    for damage in response["damage_instances"]:
        review_status, review_note = auto_decision(damage["confidence"])
        pred = models.PredictedDamage(
            inspection_image_id=image_row.id,
            damage_type=damage["damage_type"],
            confidence=damage["confidence"],
            bbox_norm=damage["bbox_norm"],
            centroid_x=damage["centroid_x"],
            centroid_y=damage["centroid_y"],
            area_norm=damage["area_norm"],
            polygon_json=damage.get("polygon_json"),
            mask_rle=damage.get("mask_rle"),
            model_name=response["model_name"],
            model_version=response["model_version"],
            inference_run_id=response["inference_run_id"],
        )
        db.add(pred)
        db.flush()
        db.add(
            models.DamageReview(
                predicted_damage_id=pred.id,
                inspection_session_id=inspection.id,
                review_status=review_status,
                review_note=review_note,
                reviewed_at=_utcnow(),
            )
        )


def run_damage_inference(db: Session, inspection: models.InspectionSession):
    for image_row in _accepted_required_images(db, inspection.id):
        _clear_prediction_state_for_image(db, image_row)
        file_bytes = storage_service.get_bytes(settings.s3_bucket_raw_images, image_row.object_key_raw)
        response = inference_client.damage_seg_predict(file_bytes, f"{image_row.id}.jpg", image_row.slot_code or "unknown")
        _save_overlay_if_present(inspection, image_row, response)
        _create_predicted_damage_rows(db, inspection, image_row, response)

    inspection.status = InspectionStatus.READY_FOR_REVIEW.value
    db.flush()


def _mark_pending_reviews_uncertain(db: Session, inspection_id) -> None:
    pending_reviews = db.execute(
        select(models.DamageReview).where(
            models.DamageReview.inspection_session_id == inspection_id,
            models.DamageReview.review_status == ReviewStatus.PENDING.value,
        )
    ).scalars().all()
    for review in pending_reviews:
        review.review_status = ReviewStatus.UNCERTAIN.value
        review.review_note = review.review_note or "auto_marked_uncertain_during_finalize"
        review.reviewed_at = _utcnow()


def _clear_final_state(db: Session, inspection_id) -> None:
    old = db.execute(
        select(models.InspectionDamageFinal).where(models.InspectionDamageFinal.inspection_session_id == inspection_id)
    ).scalars().all()
    for row in old:
        db.delete(row)
    db.flush()


def _finalizable_predicted_reviews(db: Session, inspection_id):
    return db.execute(
        select(models.DamageReview, models.PredictedDamage, models.InspectionImage)
        .join(models.PredictedDamage, models.DamageReview.predicted_damage_id == models.PredictedDamage.id)
        .join(models.InspectionImage, models.PredictedDamage.inspection_image_id == models.InspectionImage.id)
        .where(
            models.DamageReview.inspection_session_id == inspection_id,
            models.DamageReview.review_status.in_(
                [ReviewStatus.CONFIRMED.value, ReviewStatus.UNCERTAIN.value]
            ),
        )
    ).all()


def _manual_damages_for_inspection(db: Session, inspection_id):
    return db.execute(
        select(models.ManualDamage).where(models.ManualDamage.inspection_session_id == inspection_id)
    ).scalars().all()


def _final_from_predicted(inspection_id, review, pred, image):
    source_type = "predicted_auto_high"
    if review.review_status == ReviewStatus.UNCERTAIN.value:
        source_type = "predicted_auto_low"

    return models.InspectionDamageFinal(
        inspection_session_id=inspection_id,
        view_slot=image.slot_code or "unknown",
        base_image_id=image.id,
        source_type=source_type,
        source_predicted_damage_id=pred.id,
        damage_type=pred.damage_type,
        bbox_norm=pred.bbox_norm,
        centroid_x=pred.centroid_x,
        centroid_y=pred.centroid_y,
        area_norm=pred.area_norm,
        polygon_json=pred.polygon_json,
        severity_hint=review.severity_hint,
        note=review.review_note,
    )


def _final_from_manual(inspection_id, manual, image):
    return models.InspectionDamageFinal(
        inspection_session_id=inspection_id,
        view_slot=image.slot_code or "unknown",
        base_image_id=manual.base_image_id,
        source_type="manual",
        source_manual_damage_id=manual.id,
        damage_type=manual.damage_type,
        bbox_norm=manual.bbox_norm,
        centroid_x=manual.centroid_x,
        centroid_y=manual.centroid_y,
        area_norm=manual.area_norm,
        polygon_json=manual.polygon_json,
        severity_hint=manual.severity_hint,
        note=manual.note,
    )


def finalize_inspection(db: Session, inspection: models.InspectionSession):
    if inspection.status == InspectionStatus.FINALIZED.value:
        raise ValueError("Inspection is already finalized. Cannot re-finalize.")

    _mark_pending_reviews_uncertain(db, inspection.id)
    _clear_final_state(db, inspection.id)

    for review, pred, image in _finalizable_predicted_reviews(db, inspection.id):
        db.add(_final_from_predicted(inspection.id, review, pred, image))

    for manual in _manual_damages_for_inspection(db, inspection.id):
        image = db.get(models.InspectionImage, manual.base_image_id)
        db.add(_final_from_manual(inspection.id, manual, image))

    inspection.status = InspectionStatus.FINALIZED.value
    inspection.finalized_at = _utcnow()
    db.flush()

    comparison = None
    if inspection.inspection_type == InspectionType.POST_TRIP.value:
        comparison = run_post_trip_comparison(db, inspection)

    from apps.api_service.app.services.rental_service import sync_rental_after_inspection_finalize

    sync_rental_after_inspection_finalize(db, inspection)
    return comparison
