from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

class NormalizedBBox(BaseModel):
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)

class DamageInstance(BaseModel):
    damage_type: Literal["scratch", "dent", "crack", "broken_part"]
    confidence: float
    bbox_norm: NormalizedBBox
    centroid_x: float
    centroid_y: float
    area_norm: float
    polygon_json: Optional[list[list[float]]] = None
    mask_rle: Optional[dict[str, Any]] = None

class UploadValidationResult(BaseModel):
    accepted: bool
    expected_slot: str
    predicted_view: Optional[str]
    quality_label: str
    quality_score: float
    rejection_reason: Optional[str] = None
    car_present: bool
    car_confidence: float
    car_bbox: Optional[dict[str, float]] = None

class ComparisonMatch(BaseModel):
    status: Literal[
        "matched_existing",
        "possible_match",
        "possible_new",
        "new_confirmed",
        "not_visible_enough",
        "requires_admin_review",
    ]
    pre_damage_id: Optional[str]
    post_damage_id: Optional[str]
    match_score: float
    iou_norm: Optional[float] = None
    centroid_distance_norm: Optional[float] = None
    area_similarity: Optional[float] = None
