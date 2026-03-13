from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from typing import Literal, Optional

class CreateInspectionRequest(BaseModel):
    vehicle_id: str
    inspection_type: Literal["pre_trip", "post_trip"]
    user_telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None

class CreateInspectionResponse(BaseModel):
    inspection_id: UUID
    status: str
    required_slots: list[str]
    next_required_slot: str

class RunInitialChecksRequest(BaseModel):
    image_id: UUID
    expected_slot: str

class FinalizeInspectionRequest(BaseModel):
    finalize_note: Optional[str] = None
    photos_review_confirmed: bool = False

class InspectionImageSummary(BaseModel):
    image_id: UUID
    slot_code: Optional[str]
    status: str
    accepted: Optional[bool]
    rejection_reason: Optional[str]
    raw_url: Optional[str] = None
    overlay_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

class InspectionSummary(BaseModel):
    inspection_id: UUID
    vehicle_id: str
    inspection_type: str
    status: str
    required_slots: list[str]
    accepted_slots: list[str]
    images: list[InspectionImageSummary]
    linked_pre_trip_session_id: Optional[UUID] = None
