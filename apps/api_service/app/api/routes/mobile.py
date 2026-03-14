import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api_service.app.core.config import settings
from apps.api_service.app.db.session import get_db
from apps.api_service.app.schemas.mobile import (
    StartRentalRequest,
    StartReturnInspectionRequest,
)
from apps.api_service.app.services.rental_service import (
    get_dashboard,
    start_rental,
    start_return_inspection,
    cancel_pending_rental,
    get_rental_for_inspection,
    serialize_rental_card,
)

router = APIRouter(prefix="/mobile", tags=["mobile"])


@router.get("/dashboard")
def dashboard(
    telegram_user_id: int = Query(...),
    username: str | None = Query(None),
    first_name: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return {
        "data": get_dashboard(
            db,
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            public_web_base_url=settings.public_web_base_url,
        )
    }


@router.post("/trips/start")
def start_trip(payload: StartRentalRequest, db: Session = Depends(get_db)):
    rental, inspection_id, created = start_rental(
        db,
        telegram_user_id=payload.telegram_user_id,
        username=payload.username,
        first_name=payload.first_name,
        vehicle_external_id=payload.vehicle_id,
    )
    db.commit()
    return {
        "data": {
            "created": created,
            "inspection_id": str(inspection_id) if inspection_id else None,
            "rental": serialize_rental_card(db, rental),
        }
    }


@router.post("/trips/{trip_id}/return")
def start_return(trip_id: uuid.UUID, payload: StartReturnInspectionRequest, db: Session = Depends(get_db)):
    try:
        rental, inspection_id = start_return_inspection(
            db,
            rental_id=trip_id,
            telegram_user_id=payload.telegram_user_id,
            username=payload.username,
            first_name=payload.first_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return {
        "data": {
            "inspection_id": str(inspection_id),
            "rental": serialize_rental_card(db, rental),
        }
    }


@router.post("/trips/{trip_id}/cancel")
def cancel_trip(trip_id: uuid.UUID, db: Session = Depends(get_db)):
    try:
        rental = cancel_pending_rental(db, trip_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return {
        "data": {
            "rental_id": str(rental.id),
            "status": rental.status,
        }
    }


@router.get("/inspections/{inspection_id}/context")
def inspection_context(inspection_id: uuid.UUID, db: Session = Depends(get_db)):
    rental = get_rental_for_inspection(db, inspection_id)
    return {
        "data": {
            "rental": serialize_rental_card(db, rental) if rental else None,
        }
    }
