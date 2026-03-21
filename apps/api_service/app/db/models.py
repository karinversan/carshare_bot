import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String, Boolean, BigInteger, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from packages.shared_py.car_inspection.enums import (
    InspectionType, InspectionStatus, ImageType, ImageStatus, ReviewStatus,
    ComparisonStatus, AdminCaseStatus, DamageType, SeverityHint, RentalStatus
)
from apps.api_service.app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


def _utcnow():
    return datetime.now(timezone.utc)

def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="customer", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = uuid_pk()
    external_vehicle_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    license_plate: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class RentalSession(Base):
    __tablename__ = "rental_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    status: Mapped[str] = mapped_column(String(64), default=RentalStatus.AWAITING_PICKUP_INSPECTION.value, index=True)
    route_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pickup_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dropoff_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    planned_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pre_inspection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inspection_sessions.id"), nullable=True)
    post_inspection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inspection_sessions.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class InspectionSession(Base):
    __tablename__ = "inspection_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    inspection_type: Mapped[str] = mapped_column(String(50), default=InspectionType.PRE_TRIP.value)
    status: Mapped[str] = mapped_column(String(50), default=InspectionStatus.CREATED.value)
    linked_pre_trip_session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inspection_sessions.id"), nullable=True)
    required_slots: Mapped[list] = mapped_column(JSONType, default=list)
    accepted_slots: Mapped[list] = mapped_column(JSONType, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comparison_status: Mapped[str] = mapped_column(String(50), default=ComparisonStatus.NOT_RUN.value)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class InspectionImage(Base):
    __tablename__ = "inspection_images"

    id: Mapped[uuid.UUID] = uuid_pk()
    inspection_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_sessions.id"), index=True)
    image_type: Mapped[str] = mapped_column(String(50), default=ImageType.REQUIRED_VIEW.value, index=True)
    slot_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default=ImageStatus.UPLOADED.value)
    capture_order: Mapped[int] = mapped_column(Integer, default=1)
    object_key_raw: Mapped[str] = mapped_column(Text)
    object_key_processed: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_key_thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    overlay_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    car_present: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    car_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    car_bbox: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    quality_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    view_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    view_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duplicate_of_image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inspection_images.id"), nullable=True)
    parent_damage_review_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    parent_manual_damage_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class PredictedDamage(Base):
    __tablename__ = "predicted_damages"

    id: Mapped[uuid.UUID] = uuid_pk()
    inspection_image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_images.id"), index=True)
    damage_type: Mapped[str] = mapped_column(String(50), default=DamageType.SCRATCH.value, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    bbox_norm: Mapped[dict] = mapped_column(JSONType)
    centroid_x: Mapped[float] = mapped_column(Float)
    centroid_y: Mapped[float] = mapped_column(Float)
    area_norm: Mapped[float] = mapped_column(Float)
    mask_rle: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    polygon_json: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    model_name: Mapped[str] = mapped_column(String(128))
    model_version: Mapped[str] = mapped_column(String(128))
    inference_run_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class DamageReview(Base):
    __tablename__ = "damage_reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    predicted_damage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("predicted_damages.id"), unique=True)
    inspection_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_sessions.id"), index=True)
    review_status: Mapped[str] = mapped_column(String(50), default=ReviewStatus.PENDING.value, index=True)
    severity_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class ManualDamage(Base):
    __tablename__ = "manual_damages"

    id: Mapped[uuid.UUID] = uuid_pk()
    inspection_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_sessions.id"), index=True)
    base_image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_images.id"), index=True)
    damage_type: Mapped[str] = mapped_column(String(50), default=DamageType.SCRATCH.value)
    bbox_norm: Mapped[dict] = mapped_column(JSONType)
    centroid_x: Mapped[float] = mapped_column(Float)
    centroid_y: Mapped[float] = mapped_column(Float)
    area_norm: Mapped[float] = mapped_column(Float)
    polygon_json: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    severity_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class InspectionDamageFinal(Base):
    __tablename__ = "inspection_damages_final"

    id: Mapped[uuid.UUID] = uuid_pk()
    inspection_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_sessions.id"), index=True)
    view_slot: Mapped[str] = mapped_column(String(50), index=True)
    base_image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_images.id"))
    source_type: Mapped[str] = mapped_column(String(50))
    source_predicted_damage_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("predicted_damages.id"), nullable=True)
    source_manual_damage_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("manual_damages.id"), nullable=True)
    damage_type: Mapped[str] = mapped_column(String(50), index=True)
    bbox_norm: Mapped[dict] = mapped_column(JSONType)
    centroid_x: Mapped[float] = mapped_column(Float)
    centroid_y: Mapped[float] = mapped_column(Float)
    area_norm: Mapped[float] = mapped_column(Float)
    polygon_json: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    severity_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class InspectionComparison(Base):
    __tablename__ = "inspection_comparisons"
    __table_args__ = (UniqueConstraint("pre_session_id", "post_session_id", "diff_version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    pre_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_sessions.id"))
    post_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_sessions.id"))
    status: Mapped[str] = mapped_column(String(50), default=ComparisonStatus.NOT_RUN.value)
    diff_version: Mapped[str] = mapped_column(String(64), default="v1")
    summary_json: Mapped[dict] = mapped_column(JSONType, default=dict)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    possible_new_count: Mapped[int] = mapped_column(Integer, default=0)
    new_confirmed_count: Mapped[int] = mapped_column(Integer, default=0)
    requires_admin_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class DamageMatch(Base):
    __tablename__ = "damage_matches"

    id: Mapped[uuid.UUID] = uuid_pk()
    comparison_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_comparisons.id"), index=True)
    view_slot: Mapped[str] = mapped_column(String(50), index=True)
    pre_damage_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inspection_damages_final.id"), nullable=True)
    post_damage_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("inspection_damages_final.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    match_score: Mapped[float] = mapped_column(Float)
    iou_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_distance_norm: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

class AdminCase(Base):
    __tablename__ = "admin_cases"

    id: Mapped[uuid.UUID] = uuid_pk()
    comparison_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspection_comparisons.id"), unique=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    status: Mapped[str] = mapped_column(String(50), default=AdminCaseStatus.OPEN.value, index=True)
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
