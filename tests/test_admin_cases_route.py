import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api_service.app.db.base import Base
from apps.api_service.app.db import models
from apps.api_service.app.db.session import get_db
from apps.api_service.app.main import app


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


def _seed_case_with_orphan_assignee(db: Session) -> uuid.UUID:
    user = models.User(telegram_user_id=11111, first_name="Karin", username="karin")
    vehicle = models.Vehicle(
        external_vehicle_id="VEH-TEST-001",
        license_plate="T000AA77",
        make="Test",
        model="Car",
        color="Gray",
        active=True,
    )
    db.add(user)
    db.add(vehicle)
    db.flush()

    pre = models.InspectionSession(
        vehicle_id=vehicle.id,
        user_id=user.id,
        inspection_type="pre_trip",
        status="finalized",
        required_slots=["front", "left_side", "right_side", "rear"],
        accepted_slots=["front", "left_side", "right_side", "rear"],
    )
    post = models.InspectionSession(
        vehicle_id=vehicle.id,
        user_id=user.id,
        inspection_type="post_trip",
        status="finalized",
        required_slots=["front", "left_side", "right_side", "rear"],
        accepted_slots=["front", "left_side", "right_side", "rear"],
        linked_pre_trip_session_id=pre.id,
    )
    db.add(pre)
    db.add(post)
    db.flush()

    comparison = models.InspectionComparison(
        pre_session_id=pre.id,
        post_session_id=post.id,
        status="completed",
        summary_json={"matched_count": 0, "possible_new_count": 1, "new_confirmed_count": 0},
        matched_count=0,
        possible_new_count=1,
        new_confirmed_count=0,
        requires_admin_review=True,
    )
    db.add(comparison)
    db.flush()

    case = models.AdminCase(
        comparison_id=comparison.id,
        vehicle_id=vehicle.id,
        status="open",
        priority="high",
        title="Likely new damage",
        summary="Potential new scratch on right side",
        assigned_to_user_id=uuid.uuid4(),  # user does not exist
    )
    db.add(case)
    db.commit()
    return case.id


def test_admin_cases_list_handles_orphan_assignee_without_500():
    db = _make_db()
    _seed_case_with_orphan_assignee(db)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/admin-cases")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert len(payload) == 1
        assert payload[0]["assignee_name"] is None
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_admin_case_detail_handles_orphan_assignee_without_500():
    db = _make_db()
    case_id = _seed_case_with_orphan_assignee(db)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(f"/admin-cases/{case_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == str(case_id)
        assert data["assignee_name"] is None
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_admin_case_can_be_assigned_and_status_updated():
    db = _make_db()
    case_id = _seed_case_with_orphan_assignee(db)
    app.dependency_overrides[get_db] = _override_db(db)
    try:
        client = TestClient(app, raise_server_exceptions=False)

        assign_response = client.post(
            f"/admin-cases/{case_id}/assign",
            json={"first_name": "Verifier"},
        )
        assert assign_response.status_code == 200, assign_response.text
        assign_data = assign_response.json()["data"]
        assert assign_data["assignee_name"] == "Verifier"

        status_response = client.post(
            f"/admin-cases/{case_id}/status",
            json={"status": "in_review", "resolved_note": "Берём кейс в работу"},
        )
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["data"]["status"] == "in_review"

        detail_response = client.get(f"/admin-cases/{case_id}")
        assert detail_response.status_code == 200, detail_response.text
        detail_data = detail_response.json()["data"]
        assert detail_data["status"] == "in_review"
        assert detail_data["assignee_name"] == "Verifier"
    finally:
        app.dependency_overrides.clear()
        db.close()
