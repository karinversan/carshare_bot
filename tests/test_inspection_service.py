import io

from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apps.api_service.app.db import models
from apps.api_service.app.db.base import Base
from apps.api_service.app.services.inspection_service import (
    confirm_photo_set,
    create_inspection,
    finalize_inspection,
    run_damage_inference,
    run_initial_checks,
    upload_inspection_image,
)
from apps.api_service.app.services.inference_client import inference_client
from apps.api_service.app.services.storage_service import storage_service


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _jpeg_bytes(color: int) -> bytes:
    image = Image.new("RGB", (320, 240), (color, color, color))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_rejected_required_upload_is_deleted(monkeypatch):
    db = _make_db()
    stored: dict[tuple[str, str], bytes] = {}

    monkeypatch.setattr(storage_service, "put_bytes", lambda bucket, key, data, content_type: stored.__setitem__((bucket, key), data))
    monkeypatch.setattr(storage_service, "get_bytes", lambda bucket, key: stored[(bucket, key)])
    monkeypatch.setattr(storage_service, "delete_object", lambda bucket, key: stored.pop((bucket, key), None))
    monkeypatch.setattr(
        inference_client,
        "quality_view_predict",
        lambda image_bytes, filename, expected_slot: {
            "accepted": False,
            "expected_slot": expected_slot,
            "predicted_view": "front",
            "view_score": 0.98,
            "quality_label": "too_dark",
            "quality_score": 0.93,
            "rejection_reason": "too_dark",
            "car_present": True,
            "car_confidence": 0.97,
            "car_bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.9},
            "model_backend": "mock",
        },
    )

    inspection, _ = create_inspection(db, "VEH-001", "pre_trip", 1001, "user", "Karin")
    row = upload_inspection_image(db, inspection, _jpeg_bytes(120), "front.jpg", "required_view", "front", 1)

    result = run_initial_checks(db, inspection, row, "front")
    db.commit()

    assert result["accepted"] is False
    images = db.execute(select(models.InspectionImage).where(models.InspectionImage.inspection_session_id == inspection.id)).scalars().all()
    assert images == []
    assert inspection.accepted_slots == []
    assert stored == {}


def test_latest_accepted_image_replaces_previous_slot_image(monkeypatch):
    db = _make_db()
    stored: dict[tuple[str, str], bytes] = {}

    monkeypatch.setattr(storage_service, "put_bytes", lambda bucket, key, data, content_type: stored.__setitem__((bucket, key), data))
    monkeypatch.setattr(storage_service, "get_bytes", lambda bucket, key: stored[(bucket, key)])
    monkeypatch.setattr(storage_service, "delete_object", lambda bucket, key: stored.pop((bucket, key), None))
    monkeypatch.setattr(
        inference_client,
        "quality_view_predict",
        lambda image_bytes, filename, expected_slot: {
            "accepted": True,
            "expected_slot": expected_slot,
            "predicted_view": expected_slot,
            "view_score": 0.98,
            "quality_label": "good",
            "quality_score": 0.98,
            "rejection_reason": None,
            "car_present": True,
            "car_confidence": 0.97,
            "car_bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.9},
            "model_backend": "mock",
        },
    )

    inspection, _ = create_inspection(db, "VEH-001", "pre_trip", 1001, "user", "Karin")

    first = upload_inspection_image(db, inspection, _jpeg_bytes(80), "front-a.jpg", "required_view", "front", 1)
    run_initial_checks(db, inspection, first, "front")
    db.commit()

    second = upload_inspection_image(db, inspection, _jpeg_bytes(160), "front-b.jpg", "required_view", "front", 1)
    run_initial_checks(db, inspection, second, "front")
    db.commit()

    images = db.execute(
        select(models.InspectionImage).where(
            models.InspectionImage.inspection_session_id == inspection.id,
            models.InspectionImage.slot_code == "front",
        )
    ).scalars().all()

    assert len(images) == 1
    assert images[0].id == second.id
    assert inspection.accepted_slots == ["front"]
    assert len(stored) == 1


def test_duplicate_check_ignores_unconfirmed_uploaded_rows(monkeypatch):
    db = _make_db()
    stored: dict[tuple[str, str], bytes] = {}

    monkeypatch.setattr(storage_service, "put_bytes", lambda bucket, key, data, content_type: stored.__setitem__((bucket, key), data))
    monkeypatch.setattr(storage_service, "get_bytes", lambda bucket, key: stored[(bucket, key)])
    monkeypatch.setattr(storage_service, "delete_object", lambda bucket, key: stored.pop((bucket, key), None))

    inspection, _ = create_inspection(db, "VEH-001", "pre_trip", 1001, "user", "Karin")
    first = upload_inspection_image(db, inspection, _jpeg_bytes(80), "front-a.jpg", "required_view", "front", 1)
    db.commit()

    second = upload_inspection_image(db, inspection, _jpeg_bytes(80), "front-b.jpg", "required_view", "front", 1)
    db.commit()

    assert first.accepted is None
    assert second.duplicate_of_image_id is None


def test_auto_damage_decision_and_finalize_state(monkeypatch):
    db = _make_db()
    stored: dict[tuple[str, str], bytes] = {}

    monkeypatch.setattr(storage_service, "put_bytes", lambda bucket, key, data, content_type: stored.__setitem__((bucket, key), data))
    monkeypatch.setattr(storage_service, "get_bytes", lambda bucket, key: stored[(bucket, key)])
    monkeypatch.setattr(storage_service, "delete_object", lambda bucket, key: stored.pop((bucket, key), None))

    monkeypatch.setattr(
        inference_client,
        "quality_view_predict",
        lambda image_bytes, filename, expected_slot: {
            "accepted": True,
            "expected_slot": expected_slot,
            "predicted_view": expected_slot,
            "view_score": 0.95,
            "quality_label": "good",
            "quality_score": 0.96,
            "rejection_reason": None,
            "car_present": True,
            "car_confidence": 0.98,
            "car_bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.9},
            "model_backend": "mock",
        },
    )
    monkeypatch.setattr(
        inference_client,
        "damage_seg_predict",
        lambda image_bytes, filename, slot_code: {
            "model_name": "mock_seg",
            "model_version": "1",
            "inference_run_id": f"run-{slot_code}",
            "overlay_png_b64": None,
            "damage_instances": [
                {
                    "damage_type": "scratch",
                    "confidence": 0.92,
                    "bbox_norm": {"x1": 0.1, "y1": 0.1, "x2": 0.3, "y2": 0.25},
                    "centroid_x": 0.2,
                    "centroid_y": 0.175,
                    "area_norm": 0.03,
                    "polygon_json": [[0.1, 0.1], [0.3, 0.1], [0.3, 0.25], [0.1, 0.25]],
                },
                {
                    "damage_type": "dent",
                    "confidence": 0.55,
                    "bbox_norm": {"x1": 0.4, "y1": 0.2, "x2": 0.55, "y2": 0.35},
                    "centroid_x": 0.475,
                    "centroid_y": 0.275,
                    "area_norm": 0.0225,
                    "polygon_json": [[0.4, 0.2], [0.55, 0.2], [0.55, 0.35], [0.4, 0.35]],
                },
                {
                    "damage_type": "crack",
                    "confidence": 0.3,
                    "bbox_norm": {"x1": 0.6, "y1": 0.2, "x2": 0.75, "y2": 0.3},
                    "centroid_x": 0.675,
                    "centroid_y": 0.25,
                    "area_norm": 0.015,
                    "polygon_json": [[0.6, 0.2], [0.75, 0.2], [0.75, 0.3], [0.6, 0.3]],
                },
            ],
        },
    )

    inspection, _ = create_inspection(db, "VEH-001", "pre_trip", 5555, "user", "Karin")
    for index, slot in enumerate(["front", "left_side", "right_side", "rear"], start=1):
        row = upload_inspection_image(
            db,
            inspection,
            _jpeg_bytes(40 * index),
            f"{slot}.jpg",
            "required_view",
            slot,
            index,
        )
        result = run_initial_checks(db, inspection, row, slot)
        assert result["accepted"] is True

    confirm_photo_set(inspection)
    run_damage_inference(db, inspection)
    finalize_inspection(db, inspection)
    db.commit()

    reviews = db.execute(
        select(models.DamageReview).where(models.DamageReview.inspection_session_id == inspection.id)
    ).scalars().all()
    statuses = [review.review_status for review in reviews]
    assert "confirmed" in statuses
    assert "uncertain" in statuses
    assert "rejected" in statuses

    finals = db.execute(
        select(models.InspectionDamageFinal).where(models.InspectionDamageFinal.inspection_session_id == inspection.id)
    ).scalars().all()
    source_types = {row.source_type for row in finals}
    assert source_types == {"predicted_auto_high", "predicted_auto_low"}


def test_photo_set_confirmation_is_required_before_inference(monkeypatch):
    from packages.shared_py.car_inspection.enums import InspectionStatus

    db = _make_db()
    stored: dict[tuple[str, str], bytes] = {}

    monkeypatch.setattr(storage_service, "put_bytes", lambda bucket, key, data, content_type: stored.__setitem__((bucket, key), data))
    monkeypatch.setattr(storage_service, "get_bytes", lambda bucket, key: stored[(bucket, key)])
    monkeypatch.setattr(storage_service, "delete_object", lambda bucket, key: stored.pop((bucket, key), None))
    monkeypatch.setattr(
        inference_client,
        "quality_view_predict",
        lambda image_bytes, filename, expected_slot: {
            "accepted": True,
            "expected_slot": expected_slot,
            "predicted_view": expected_slot,
            "view_score": 0.98,
            "quality_label": "good",
            "quality_score": 0.98,
            "rejection_reason": None,
            "car_present": True,
            "car_confidence": 0.97,
            "car_bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.9},
            "model_backend": "mock",
        },
    )
    monkeypatch.setattr(
        inference_client,
        "damage_seg_predict",
        lambda image_bytes, filename, slot_code: {
            "model_name": "mock_seg",
            "model_version": "1",
            "inference_run_id": f"run-{slot_code}",
            "overlay_png_b64": None,
            "damage_instances": [],
        },
    )

    inspection, _ = create_inspection(db, "VEH-001", "pre_trip", 7777, "user", "Karin")
    for index, slot in enumerate(["front", "left_side", "right_side", "rear"], start=1):
        row = upload_inspection_image(
            db,
            inspection,
            _jpeg_bytes(40 * index),
            f"{slot}.jpg",
            "required_view",
            slot,
            index,
        )
        result = run_initial_checks(db, inspection, row, slot)
        assert result["accepted"] is True

    assert inspection.status == InspectionStatus.CAPTURING_OPTIONAL_PHOTOS.value

    try:
        run_damage_inference(db, inspection)
    except ValueError as exc:
        assert "not ready for damage inference" in str(exc)
    else:
        raise AssertionError("damage inference should require photo-set confirmation")

    confirm_photo_set(inspection)
    assert inspection.status == InspectionStatus.READY_FOR_INFERENCE.value

    run_damage_inference(db, inspection)
    assert inspection.status == InspectionStatus.READY_FOR_REVIEW.value
