import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apps.api_service.app.db import models

engine = create_engine(os.getenv("SYNC_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/car_inspection"))

with Session(engine) as db:
    fleet = [
        ("VEH-001", "Volkswagen", "Polo", "A123AA77", "White"),
        ("VEH-002", "Kia", "Rio", "B482KM77", "Graphite"),
        ("VEH-003", "Skoda", "Rapid", "E919OP77", "Silver"),
    ]
    for vehicle_id, make, model, plate, color in fleet:
        if not db.execute(select(models.Vehicle).where(models.Vehicle.external_vehicle_id == vehicle_id)).scalar_one_or_none():
            db.add(
                models.Vehicle(
                    external_vehicle_id=vehicle_id,
                    make=make,
                    model=model,
                    license_plate=plate,
                    color=color,
                    active=True,
                )
            )
    db.commit()
    print("seeded demo vehicles")
