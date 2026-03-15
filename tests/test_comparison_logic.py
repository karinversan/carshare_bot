"""Tests for the comparison/diff engine domain logic."""
import pytest
from apps.api_service.app.domain.comparisons import (
    bbox_iou, centroid_distance, centroid_distance_normalized,
    area_similarity, match_score,
)

class TestBboxIou:
    def test_overlapping(self):
        a = {"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.4}
        b = {"x1": 0.2, "y1": 0.2, "x2": 0.5, "y2": 0.5}
        assert 0 < bbox_iou(a, b) < 1

    def test_identical(self):
        a = {"x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5}
        assert bbox_iou(a, a) == pytest.approx(1.0)

    def test_no_overlap(self):
        a = {"x1": 0.0, "y1": 0.0, "x2": 0.2, "y2": 0.2}
        b = {"x1": 0.5, "y1": 0.5, "x2": 0.7, "y2": 0.7}
        assert bbox_iou(a, b) == 0.0

    def test_missing_keys(self):
        assert bbox_iou({"x1": 0.1}, {"x1": 0}) == 0.0

    def test_symmetric(self):
        a = {"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.4}
        b = {"x1": 0.2, "y1": 0.2, "x2": 0.5, "y2": 0.5}
        assert bbox_iou(a, b) == pytest.approx(bbox_iou(b, a))

class TestCentroidDistance:
    def test_same_point(self):
        assert centroid_distance((0.5, 0.5), (0.5, 0.5)) == 0.0

    def test_normalized_max_is_one(self):
        assert centroid_distance_normalized((0, 0), (1, 1)) == pytest.approx(1.0, abs=0.01)

    def test_normalized_never_exceeds_one(self):
        assert centroid_distance_normalized((0, 0), (2, 2)) == 1.0

class TestAreaSimilarity:
    def test_equal(self):
        assert area_similarity(0.5, 0.5) == 1.0

    def test_both_zero(self):
        assert area_similarity(0.0, 0.0) == 1.0

    def test_ratio(self):
        assert area_similarity(0.2, 0.4) == pytest.approx(0.5)

class TestMatchScore:
    def test_perfect(self):
        assert match_score(1.0, 0.0, 1.0) == pytest.approx(1.0)

    def test_worst(self):
        assert match_score(0.0, 1.0, 0.0) == pytest.approx(0.0)

    def test_monotonic(self):
        assert match_score(0.8, 0.1, 0.9) > match_score(0.2, 0.7, 0.3)

    def test_in_range(self):
        s = match_score(0.5, 0.5, 0.5)
        assert 0.0 <= s <= 1.0
