import io

from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api_service.app.db.base import Base
from apps.api_service.app.db.session import get_db
from apps.api_service.app.main import app
from apps.api_service.app.services.inspection_service import inference_client
from apps.api_service.app.services.storage_service import storage_service


def _make_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _override_db(db: Session):
    def _override():
        try:
            yield db
        finally:
            pass

    return _override


def _jpeg_bytes(color: int) -> bytes:
    image = Image.new("RGB", (640, 480), (color, color, color))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _damage_instance(damage_type: str, confidence: float, x1: float, y1: float, x2: float, y2: float) -> dict:
    return {
        "damage_type": damage_type,
        "confidence": confidence,
        "bbox_norm": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        "centroid_x": (x1 + x2) / 2,
        "centroid_y": (y1 + y2) / 2,
        "area_norm": abs((x2 - x1) * (y2 - y1)),
        "polygon_json": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
    }


def _upload_and_accept_required(client: TestClient, inspection_id: str, slot_code: str, color: int, capture_order: int) -> None:
    upload_response = client.post(
        f"/inspections/{inspection_id}/images",
        files={"file": (f"{slot_code}.jpg", _jpeg_bytes(color), "image/jpeg")},
        data={
            "image_type": "required_view",
            "slot_code": slot_code,
            "capture_order": str(capture_order),
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    image_id = upload_response.json()["data"]["image_id"]

    check_response = client.post(
        f"/inspections/{inspection_id}/run-initial-checks",
        json={"image_id": image_id, "expected_slot": slot_code},
    )
    assert check_response.status_code == 200, check_response.text
    assert check_response.json()["data"]["accepted"] is True


def test_e2e_smoke_pre_post_comparison_admin_case(monkeypatch):
    db = _make_db()
    store: dict[tuple[str, str], bytes] = {}
    phase = {"value": "pre"}

    monkeypatch.setattr(
        storage_service,
        "put_bytes",
        lambda bucket, key, data, content_type: store.__setitem__((bucket, key), data),
    )
    monkeypatch.setattr(storage_service, "get_bytes", lambda bucket, key: store[(bucket, key)])
    monkeypatch.setattr(storage_service, "delete_object", lambda bucket, key: store.pop((bucket, key), None))
    monkeypatch.setattr(
        storage_service,
        "presigned_url",
        lambda bucket, key, expires=3600: f"http://test.local/s3/{bucket}/{key}",
    )

    def _fake_quality_view_predict(image_bytes: bytes, filename: str, expected_slot: str) -> dict:
        return {
            "accepted": True,
            "expected_slot": expected_slot,
            "predicted_view": expected_slot,
            "view_score": 0.98,
            "quality_label": "good",
            "quality_score": 0.98,
            "rejection_reason": None,
            "car_present": True,
            "car_confidence": 0.98,
            "car_bbox": {"x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.9},
            "model_backend": "mock",
        }

    def _fake_damage_seg_predict(image_bytes: bytes, filename: str, slot_code: str) -> dict:
        instances: list[dict] = []
        if phase["value"] == "pre":
            if slot_code == "front":
                instances.append(_damage_instance("scratch", 0.92, 0.12, 0.20, 0.32, 0.34))
        else:
            if slot_code == "front":
                instances.append(_damage_instance("scratch", 0.91, 0.12, 0.20, 0.32, 0.34))
            if slot_code == "rear":
                instances.append(_damage_instance("dent", 0.95, 0.55, 0.50, 0.78, 0.74))

        return {
            "model_name": "mock_seg",
            "model_version": "1",
            "inference_run_id": f"{phase['value']}-{slot_code}",
            "overlay_png_b64": None,
            "damage_instances": instances,
        }

    monkeypatch.setattr(inference_client, "quality_view_predict", _fake_quality_view_predict)
    monkeypatch.setattr(inference_client, "damage_seg_predict", _fake_damage_seg_predict)

    app.dependency_overrides[get_db] = _override_db(db)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            start_resp = client.post(
                "/mobile/trips/start",
                json={
                    "telegram_user_id": 777001,
                    "username": "karin",
                    "first_name": "Karin",
                    "vehicle_id": "VEH-001",
                },
            )
            assert start_resp.status_code == 200, start_resp.text
            start_data = start_resp.json()["data"]
            rental_id = start_data["rental"]["rental_id"]
            pre_inspection_id = start_data["inspection_id"]
            assert pre_inspection_id
            assert start_data["rental"]["status"] == "awaiting_pickup_inspection"

            for idx, slot in enumerate(["front", "left_side", "right_side", "rear"], start=1):
                _upload_and_accept_required(client, pre_inspection_id, slot, color=50 + idx * 20, capture_order=idx)

            pre_inf_resp = client.post(f"/inspections/{pre_inspection_id}/run-damage-inference?force_sync=true")
            assert pre_inf_resp.status_code == 200, pre_inf_resp.text

            pre_fin_resp = client.post(
                f"/inspections/{pre_inspection_id}/finalize",
                json={"photos_review_confirmed": True},
            )
            assert pre_fin_resp.status_code == 200, pre_fin_resp.text
            assert pre_fin_resp.json()["data"]["status"] == "finalized"

            dashboard_active_resp = client.get(
                "/mobile/dashboard",
                params={"telegram_user_id": 777001, "username": "karin", "first_name": "Karin"},
            )
            assert dashboard_active_resp.status_code == 200
            active_rental = dashboard_active_resp.json()["data"]["active_rental"]
            assert active_rental is not None
            assert active_rental["status"] == "active"

            return_resp = client.post(
                f"/mobile/trips/{rental_id}/return",
                json={"telegram_user_id": 777001, "username": "karin", "first_name": "Karin"},
            )
            assert return_resp.status_code == 200, return_resp.text
            post_inspection_id = return_resp.json()["data"]["inspection_id"]
            assert post_inspection_id

            phase["value"] = "post"
            for idx, slot in enumerate(["front", "left_side", "right_side", "rear"], start=1):
                _upload_and_accept_required(client, post_inspection_id, slot, color=120 + idx * 15, capture_order=idx)

            post_inf_resp = client.post(f"/inspections/{post_inspection_id}/run-damage-inference?force_sync=true")
            assert post_inf_resp.status_code == 200, post_inf_resp.text

            post_fin_resp = client.post(
                f"/inspections/{post_inspection_id}/finalize",
                json={"photos_review_confirmed": True},
            )
            assert post_fin_resp.status_code == 200, post_fin_resp.text
            post_fin_data = post_fin_resp.json()["data"]
            assert post_fin_data["status"] == "finalized"
            assert post_fin_data["comparison_status"] == "admin_case_created"

            cases_resp = client.get("/admin-cases")
            assert cases_resp.status_code == 200, cases_resp.text
            cases = cases_resp.json()["data"]
            assert len(cases) >= 1
            case_id = cases[0]["id"]

            case_detail_resp = client.get(f"/admin-cases/{case_id}")
            assert case_detail_resp.status_code == 200, case_detail_resp.text
            matches = case_detail_resp.json()["data"]["matches"]
            assert any(match["status"] == "matched_existing" for match in matches)
            assert any(match["status"] == "new_confirmed" for match in matches)

            dashboard_after_return_resp = client.get(
                "/mobile/dashboard",
                params={"telegram_user_id": 777001, "username": "karin", "first_name": "Karin"},
            )
            assert dashboard_after_return_resp.status_code == 200
            assert dashboard_after_return_resp.json()["data"]["active_rental"] is None
    finally:
        app.dependency_overrides.clear()
        db.close()

