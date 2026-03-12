"""Tests for shared enums to ensure they stay in sync with the codebase."""
from packages.shared_py.car_inspection.enums import (
    InspectionType, InspectionStatus, ImageType, ImageStatus,
    ReviewStatus, ComparisonStatus, AdminCaseStatus,
    DamageType, SeverityHint, REQUIRED_SLOTS, SLOT_LABELS,
    canonical_slot, slot_matches,
)


def test_inspection_types():
    assert InspectionType.PRE_TRIP == "pre_trip"
    assert InspectionType.POST_TRIP == "post_trip"


def test_inspection_statuses_cover_flow():
    statuses = [s.value for s in InspectionStatus]
    assert "created" in statuses
    assert "finalized" in statuses
    assert "cancelled" in statuses


def test_required_slots_has_four():
    assert len(REQUIRED_SLOTS) == 4
    assert all(isinstance(s, str) for s in REQUIRED_SLOTS)
    assert set(REQUIRED_SLOTS) == set(SLOT_LABELS.keys())


def test_view_aliases_map_to_product_slots():
    assert canonical_slot("front_left_3q") == "front"
    assert canonical_slot("front_valid") == "front"
    assert canonical_slot("rear_left_3q") == "left_side"
    assert canonical_slot("rear_right_3q") == "right_side"
    assert slot_matches("left_side", "rear_left_3q") is True
    assert slot_matches("left_side", "side_valid") is True
    assert slot_matches("right_side", "side_valid") is True


def test_damage_types():
    assert len(DamageType) >= 4
    assert "scratch" in [d.value for d in DamageType]


def test_severity_hints():
    values = [s.value for s in SeverityHint]
    assert "small" in values
    assert "medium" in values
    assert "severe" in values
