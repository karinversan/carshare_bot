from enum import StrEnum

class InspectionType(StrEnum):
    PRE_TRIP = "pre_trip"
    POST_TRIP = "post_trip"

class RentalStatus(StrEnum):
    AWAITING_PICKUP_INSPECTION = "awaiting_pickup_inspection"
    ACTIVE = "active"
    AWAITING_RETURN_INSPECTION = "awaiting_return_inspection"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class InspectionStatus(StrEnum):
    CREATED = "created"
    CAPTURING_REQUIRED_VIEWS = "capturing_required_views"
    CAPTURING_OPTIONAL_PHOTOS = "capturing_optional_photos"
    READY_FOR_INFERENCE = "ready_for_inference"
    INFERENCE_RUNNING = "inference_running"
    READY_FOR_REVIEW = "ready_for_review"
    UNDER_REVIEW = "under_review"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"
    FAILED = "failed"

class ImageType(StrEnum):
    REQUIRED_VIEW = "required_view"
    OPTIONAL_CLOSEUP = "optional_closeup"

class ImageStatus(StrEnum):
    UPLOADED = "uploaded"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DUPLICATE_SUPERSEDED = "duplicate_superseded"

class ReviewStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"

class ComparisonStatus(StrEnum):
    NOT_RUN = "not_run"
    NO_NEW_DAMAGE = "no_new_damage"
    POSSIBLE_NEW_DAMAGE = "possible_new_damage"
    ADMIN_CASE_CREATED = "admin_case_created"
    NO_REFERENCE_BASELINE = "no_reference_baseline"

class AdminCaseStatus(StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED_CONFIRMED = "resolved_confirmed"
    RESOLVED_NO_ISSUE = "resolved_no_issue"
    DISMISSED = "dismissed"

class DamageType(StrEnum):
    SCRATCH = "scratch"
    DENT = "dent"
    CRACK = "crack"
    BROKEN_PART = "broken_part"

class SeverityHint(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    SEVERE = "severe"

REQUIRED_SLOTS = [
    "front",
    "left_side",
    "right_side",
    "rear",
]

SLOT_LABELS = {
    "front": "Front",
    "left_side": "Left Side",
    "right_side": "Right Side",
    "rear": "Rear",
}

SLOT_SHORT = {
    "front": "FR",
    "left_side": "LS",
    "right_side": "RS",
    "rear": "RR",
}

VIEW_MATCH_ALIASES = {
    "front": {"front", "front_left_3q", "front_right_3q", "front_valid"},
    "left_side": {"left_side", "front_left_3q", "rear_left_3q"},
    "right_side": {"right_side", "front_right_3q", "rear_right_3q"},
    "rear": {"rear", "rear_left_3q", "rear_right_3q", "rear_valid"},
}

SIDE_VIEW_ALIASES = {"side_valid"}
INVALID_VIEW_LABELS = {"angled_invalid", "other_invalid"}


def canonical_slot(slot: str | None) -> str | None:
    if slot is None:
        return None
    for product_slot, aliases in VIEW_MATCH_ALIASES.items():
        if slot in aliases:
            return product_slot
    return slot


def slot_matches(expected_slot: str, predicted_slot: str | None) -> bool:
    canonical_predicted = canonical_slot(predicted_slot)
    if predicted_slot in SIDE_VIEW_ALIASES:
        return expected_slot in {"left_side", "right_side"}
    return canonical_predicted == expected_slot
