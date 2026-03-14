from uuid import UUID
from typing import Optional, Literal
from pydantic import BaseModel

class DamageDecisionRequest(BaseModel):
    severity_hint: Optional[Literal["small", "medium", "severe"]] = None
    reason: Optional[str] = None
    note: Optional[str] = None

class ManualDamageRequest(BaseModel):
    inspection_session_id: UUID
    base_image_id: UUID
    damage_type: Literal["scratch", "dent", "crack", "broken_part"]
    bbox_norm: dict
    severity_hint: Optional[Literal["small", "medium", "severe"]] = None
    note: Optional[str] = None
