import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api_service.app.db import models
from apps.api_service.app.services.inspection_service import (
    create_inspection,
    get_or_create_user,
    get_or_create_vehicle,
)
from packages.shared_py.car_inspection.enums import RentalStatus


DEMO_FLEET = {
    "VEH-001": {
        "make": "Volkswagen",
        "model": "Polo",
        "color": "White",
        "license_plate": "A123AA77",
        "location": "Tverskaya 18",
        "eta_min": 4,
        "route_label": "Tverskaya -> Цветной бульвар",
        "pickup_title": "Pickup: Tverskaya 18",
        "dropoff_title": "Drop-off zone: Цветной бульвар",
        "planned_duration_min": 32,
        "accent": "Sedan",
    },
    "VEH-002": {
        "make": "Kia",
        "model": "Rio",
        "color": "Graphite",
        "license_plate": "B482KM77",
        "location": "Petrovka 11",
        "eta_min": 6,
        "route_label": "Petrovka -> Парк Горького",
        "pickup_title": "Pickup: Petrovka 11",
        "dropoff_title": "Drop-off zone: Парк Горького",
        "planned_duration_min": 41,
        "accent": "Economy",
    },
    "VEH-003": {
        "make": "Skoda",
        "model": "Rapid",
        "color": "Silver",
        "license_plate": "E919OP77",
        "location": "Arbat 6",
        "eta_min": 3,
        "route_label": "Arbat -> Moscow City",
        "pickup_title": "Pickup: Arbat 6",
        "dropoff_title": "Drop-off zone: Moscow City",
        "planned_duration_min": 27,
        "accent": "Liftback",
    },
}

CURRENT_RENTAL_STATUSES = {
    RentalStatus.ACTIVE.value,
    RentalStatus.AWAITING_RETURN_INSPECTION.value,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_admin_telegram_id(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return -int.from_bytes(digest[:7], "big")


def ensure_demo_fleet(db: Session) -> None:
    for vehicle_id, meta in DEMO_FLEET.items():
        vehicle = get_or_create_vehicle(db, vehicle_id)
        vehicle.make = meta["make"]
        vehicle.model = meta["model"]
        vehicle.color = meta["color"]
        vehicle.license_plate = meta["license_plate"]
        vehicle.active = True
    db.flush()


def get_current_rental_for_user(db: Session, user_id) -> models.RentalSession | None:
    return db.execute(
        select(models.RentalSession)
        .where(
            models.RentalSession.user_id == user_id,
            models.RentalSession.status.in_(CURRENT_RENTAL_STATUSES),
        )
        .order_by(models.RentalSession.created_at.desc())
    ).scalar_one_or_none()


def get_pending_pickup_rental_for_user(db: Session, user_id) -> models.RentalSession | None:
    return db.execute(
        select(models.RentalSession)
        .where(
            models.RentalSession.user_id == user_id,
            models.RentalSession.status == RentalStatus.AWAITING_PICKUP_INSPECTION.value,
        )
        .order_by(models.RentalSession.created_at.desc())
    ).scalar_one_or_none()


def serialize_vehicle_card(vehicle: models.Vehicle) -> dict:
    meta = DEMO_FLEET.get(vehicle.external_vehicle_id, {})
    title = " ".join(part for part in [vehicle.make, vehicle.model] if part).strip() or vehicle.external_vehicle_id
    subtitle = " • ".join(
        part for part in [meta.get("accent"), vehicle.color, meta.get("location")] if part
    )
    return {
        "vehicle_id": vehicle.external_vehicle_id,
        "title": title,
        "subtitle": subtitle,
        "license_plate": vehicle.license_plate,
        "eta_min": meta.get("eta_min", 5),
        "route_label": meta.get("route_label"),
        "pickup_title": meta.get("pickup_title"),
        "dropoff_title": meta.get("dropoff_title"),
        "planned_duration_min": meta.get("planned_duration_min", 30),
    }


def serialize_rental_card(db: Session, rental: models.RentalSession) -> dict:
    vehicle = db.get(models.Vehicle, rental.vehicle_id)
    vehicle_card = serialize_vehicle_card(vehicle)
    current_inspection_id = None
    next_action = None
    next_action_label = None
    if rental.status == RentalStatus.AWAITING_PICKUP_INSPECTION.value:
        current_inspection_id = str(rental.pre_inspection_id) if rental.pre_inspection_id else None
        next_action = "complete_pickup_inspection"
        next_action_label = "Открыть осмотр"
    elif rental.status == RentalStatus.ACTIVE.value:
        next_action = "start_return"
        next_action_label = "Сдать машину"
    elif rental.status == RentalStatus.AWAITING_RETURN_INSPECTION.value:
        current_inspection_id = str(rental.post_inspection_id) if rental.post_inspection_id else None
        next_action = "complete_return_inspection"
        next_action_label = "Открыть осмотр сдачи"

    return {
        "rental_id": str(rental.id),
        "status": rental.status,
        "vehicle": vehicle_card,
        "route_label": rental.route_label,
        "pickup_title": rental.pickup_title,
        "dropoff_title": rental.dropoff_title,
        "planned_duration_min": rental.planned_duration_min,
        "current_inspection_id": current_inspection_id,
        "next_action": next_action,
        "next_action_label": next_action_label,
    }


def get_dashboard(db: Session, telegram_user_id: int, username: str | None, first_name: str | None, public_web_base_url: str) -> dict:
    ensure_demo_fleet(db)
    user = get_or_create_user(db, telegram_user_id, username, first_name)
    active_rental = get_current_rental_for_user(db, user.id)
    vehicles = db.execute(
        select(models.Vehicle)
        .where(
            models.Vehicle.active == True,  # noqa: E712
            models.Vehicle.external_vehicle_id.in_(list(DEMO_FLEET.keys())),
        )
        .order_by(models.Vehicle.external_vehicle_id)
    ).scalars().all()

    return {
        "user": {
            "telegram_user_id": telegram_user_id,
            "first_name": user.first_name or first_name or "Driver",
            "username": user.username or username,
        },
        "active_rental": serialize_rental_card(db, active_rental) if active_rental else None,
        "available_vehicles": [serialize_vehicle_card(vehicle) for vehicle in vehicles],
        "admin_panel_url": f"{public_web_base_url.rstrip('/')}/admin/",
    }


def start_rental(
    db: Session,
    telegram_user_id: int,
    username: str | None,
    first_name: str | None,
    vehicle_external_id: str,
):
    ensure_demo_fleet(db)
    user = get_or_create_user(db, telegram_user_id, username, first_name)
    pending_pickup = get_pending_pickup_rental_for_user(db, user.id)
    if pending_pickup:
        existing_vehicle = db.get(models.Vehicle, pending_pickup.vehicle_id)
        if (
            existing_vehicle
            and existing_vehicle.external_vehicle_id != vehicle_external_id
        ):
            cancel_pending_rental(db, pending_pickup.id)
        else:
            return pending_pickup, pending_pickup.pre_inspection_id, False

    existing = get_current_rental_for_user(db, user.id)
    if existing:
        inspection_id = existing.post_inspection_id if existing.status == RentalStatus.AWAITING_RETURN_INSPECTION.value else None
        return existing, inspection_id, False

    inspection, vehicle = create_inspection(
        db,
        vehicle_external_id=vehicle_external_id,
        inspection_type="pre_trip",
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
    )
    meta = DEMO_FLEET.get(vehicle_external_id, {})
    rental = models.RentalSession(
        user_id=user.id,
        vehicle_id=vehicle.id,
        status=RentalStatus.AWAITING_PICKUP_INSPECTION.value,
        route_label=meta.get("route_label"),
        pickup_title=meta.get("pickup_title"),
        dropoff_title=meta.get("dropoff_title"),
        planned_duration_min=meta.get("planned_duration_min", 30),
        pre_inspection_id=inspection.id,
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(rental)
    db.flush()
    return rental, inspection.id, True


def cancel_pending_rental(db: Session, rental_id):
    rental = db.get(models.RentalSession, rental_id)
    if not rental:
        raise ValueError("Rental not found")
    if rental.status != RentalStatus.AWAITING_PICKUP_INSPECTION.value:
        raise ValueError("Only a pending pickup flow can be cancelled")

    rental.status = RentalStatus.CANCELLED.value
    rental.updated_at = _utcnow()
    if rental.pre_inspection_id:
        inspection = db.get(models.InspectionSession, rental.pre_inspection_id)
        if inspection:
            inspection.status = "cancelled"
            inspection.cancelled_at = _utcnow()
    db.flush()
    return rental


def start_return_inspection(
    db: Session,
    rental_id,
    telegram_user_id: int,
    username: str | None,
    first_name: str | None,
):
    rental = db.get(models.RentalSession, rental_id)
    if not rental:
        raise ValueError("Rental not found")
    if rental.status != RentalStatus.ACTIVE.value:
        raise ValueError("Return inspection is available only for active trips")

    vehicle = db.get(models.Vehicle, rental.vehicle_id)
    inspection, _ = create_inspection(
        db,
        vehicle_external_id=vehicle.external_vehicle_id,
        inspection_type="post_trip",
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
    )
    rental.post_inspection_id = inspection.id
    rental.status = RentalStatus.AWAITING_RETURN_INSPECTION.value
    rental.updated_at = _utcnow()
    db.flush()
    return rental, inspection.id


def get_rental_for_inspection(db: Session, inspection_id):
    return db.execute(
        select(models.RentalSession).where(
            (models.RentalSession.pre_inspection_id == inspection_id) |
            (models.RentalSession.post_inspection_id == inspection_id)
        )
    ).scalar_one_or_none()


def sync_rental_after_inspection_finalize(db: Session, inspection) -> models.RentalSession | None:
    rental = get_rental_for_inspection(db, inspection.id)
    if not rental:
        return None
    if rental.pre_inspection_id == inspection.id:
        rental.status = RentalStatus.ACTIVE.value
        rental.started_at = rental.started_at or _utcnow()
    elif rental.post_inspection_id == inspection.id:
        rental.status = RentalStatus.COMPLETED.value
        rental.completed_at = _utcnow()
    rental.updated_at = _utcnow()
    db.flush()
    return rental


def assign_admin_case(
    db: Session,
    case: models.AdminCase,
    first_name: str | None,
    username: str | None,
) -> models.User:
    label = username or first_name or "admin"
    telegram_user_id = _stable_admin_telegram_id(label)
    user = db.execute(
        select(models.User).where(models.User.telegram_user_id == telegram_user_id)
    ).scalar_one_or_none()
    if not user:
        user = models.User(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name or label,
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        user.username = username or user.username
        user.first_name = first_name or user.first_name
        user.role = "admin"
    case.assigned_to_user_id = user.id
    case.updated_at = _utcnow()
    db.flush()
    return user
