from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.api_service.app.db.base import Base
from apps.api_service.app.services.rental_service import get_dashboard, start_rental


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_dashboard_does_not_surface_pending_pickup_as_active_rental():
    db = _make_db()

    rental, inspection_id, created = start_rental(
        db,
        telegram_user_id=9001,
        username="karin",
        first_name="Karin",
        vehicle_external_id="VEH-001",
    )
    db.commit()

    dashboard = get_dashboard(
        db,
        telegram_user_id=9001,
        username="karin",
        first_name="Karin",
        public_web_base_url="https://demo.example",
    )

    assert created is True
    assert inspection_id == rental.pre_inspection_id
    assert dashboard["active_rental"] is None
    assert len(dashboard["available_vehicles"]) >= 1


def test_start_rental_reuses_same_pending_pickup_without_duplicates():
    db = _make_db()

    first_rental, first_inspection_id, first_created = start_rental(
        db,
        telegram_user_id=9002,
        username="karin",
        first_name="Karin",
        vehicle_external_id="VEH-002",
    )
    db.commit()

    second_rental, second_inspection_id, second_created = start_rental(
        db,
        telegram_user_id=9002,
        username="karin",
        first_name="Karin",
        vehicle_external_id="VEH-002",
    )

    assert first_created is True
    assert second_created is False
    assert second_rental.id == first_rental.id
    assert second_inspection_id == first_inspection_id
