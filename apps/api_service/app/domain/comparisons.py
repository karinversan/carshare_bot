from math import sqrt

# Maximum possible centroid distance for normalized [0,1] coordinates is sqrt(2) ≈ 1.414
_MAX_CENTROID_DIST = sqrt(2.0)


def bbox_iou(a: dict, b: dict) -> float:
    """Intersection over Union for two bounding boxes.

    Each box is a dict with keys x1, y1, x2, y2 (normalized or pixel coords).
    Returns 0.0 if boxes don't overlap or inputs are invalid.
    """
    required_keys = {"x1", "y1", "x2", "y2"}
    if not (required_keys <= set(a.keys()) and required_keys <= set(b.keys())):
        return 0.0

    x1 = max(a["x1"], b["x1"])
    y1 = max(a["y1"], b["y1"])
    x2 = min(a["x2"], b["x2"])
    y2 = min(a["y2"], b["y2"])
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    area_a = max(0.0, (a["x2"] - a["x1"])) * max(0.0, (a["y2"] - a["y1"]))
    area_b = max(0.0, (b["x2"] - b["x1"])) * max(0.0, (b["y2"] - b["y1"]))
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def centroid_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Raw Euclidean distance between two 2D points."""
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def centroid_distance_normalized(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Centroid distance normalized to [0, 1] range.

    Assumes coordinates are in [0, 1] normalized space.
    Divides by sqrt(2) — the maximum possible distance in unit square.
    """
    return min(centroid_distance(a, b) / _MAX_CENTROID_DIST, 1.0)


def area_similarity(a: float, b: float) -> float:
    """Ratio of smaller area to larger area. Returns 1.0 if both are zero."""
    if max(a, b) == 0:
        return 1.0
    return min(a, b) / max(a, b)


def match_score(iou_norm: float, centroid_distance_norm: float, area_similarity_score: float) -> float:
    """Weighted composite match score in [0, 1].

    Components:
        - 55% IoU
        - 25% (1 - centroid_distance_norm)  — proximity bonus
        - 20% area similarity
    """
    return (
        0.55 * iou_norm
        + 0.25 * max(0.0, 1.0 - centroid_distance_norm)
        + 0.20 * area_similarity_score
    )
