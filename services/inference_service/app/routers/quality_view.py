"""Quality + Viewpoint prediction endpoint.

Supports three backends:
  - mock: heuristic blur/brightness scoring, echoes expected_slot as predicted view
  - weights/mlflow: real EfficientNet-B0 multitask model (quality + viewpoint heads)

The endpoint always returns a consistent response schema regardless of backend.
"""

import logging

import numpy as np
from fastapi import APIRouter, UploadFile, File, Form

from packages.shared_py.car_inspection.enums import (
    INVALID_VIEW_LABELS,
    canonical_slot,
    slot_matches,
)
from services.inference_service.app.core.config import settings
from services.inference_service.app.model_registry import get_qv_model
from services.inference_service.app.utils.image import (
    pil_from_bytes, blur_score, brightness_score, bilateral_symmetry_score,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/quality-view", tags=["quality-view"])

# ── Class labels (must match training order) ─────────────────────────
DEFAULT_VIEWPOINT_CLASSES = [
    "front_left_3q", "front_right_3q", "rear_left_3q", "rear_right_3q",
]
DEFAULT_QUALITY_CLASSES = [
    "good", "blur", "dark", "overexposed",
]

QUALITY_LABEL_ALIASES = {
    "good": "good",
    "accept": "good",
    "blur": "too_blurry",
    "too_blurry": "too_blurry",
    "dark": "too_dark",
    "too_dark": "too_dark",
    "overexposed": "overexposed",
    "reject": "quality_gate_reject",
}


def _normalize_quality_label(raw_label: str) -> str:
    return QUALITY_LABEL_ALIASES.get(raw_label, raw_label)


VIEW_LABEL_ALIASES = {
    "front_valid": "front_valid",
    "valid_front": "front_valid",
    "front": "front_valid",
    "rear_valid": "rear_valid",
    "valid_rear": "rear_valid",
    "rear": "rear_valid",
    "side_valid": "side_valid",
    "valid_side": "side_valid",
    "side": "side_valid",
    "left_side_valid": "side_valid",
    "right_side_valid": "side_valid",
    "left_side": "side_valid",
    "right_side": "side_valid",
    "angled_invalid": "angled_invalid",
    "angle_invalid": "angled_invalid",
    "invalid_angle": "angled_invalid",
    "other_invalid": "other_invalid",
    "invalid_other": "other_invalid",
    "front_left_3q": "front_left_3q",
    "front_right_3q": "front_right_3q",
    "rear_left_3q": "rear_left_3q",
    "rear_right_3q": "rear_right_3q",
}


def _normalize_view_label(raw_label: str | None) -> str | None:
    if raw_label is None:
        return None
    cleaned = str(raw_label).strip().strip("'\"").lower()
    return VIEW_LABEL_ALIASES.get(cleaned, cleaned)


def _heuristic_quality_label(image_pil) -> str | None:
    brightness = brightness_score(image_pil)
    blur = blur_score(image_pil)
    if brightness < 30:
        return "too_dark"
    if brightness > 240:
        return "overexposed"
    if blur < 30:
        return "too_blurry"
    return None


def _view_mismatch_threshold(expected_slot: str, predicted_view_raw: str | None) -> float:
    predicted_view_raw = _normalize_view_label(predicted_view_raw)
    if predicted_view_raw in INVALID_VIEW_LABELS:
        return settings.viewpoint_mismatch_threshold

    predicted_slot = canonical_slot(predicted_view_raw)
    if expected_slot in {"left_side", "right_side"} and predicted_slot in {"front", "rear"}:
        return max(settings.viewpoint_mismatch_threshold, 0.82)
    if expected_slot in {"front", "rear"} and predicted_slot in {"left_side", "right_side"}:
        return max(settings.viewpoint_mismatch_threshold, 0.82)
    return settings.viewpoint_mismatch_threshold


def _expected_view_group(expected_slot: str) -> str:
    if expected_slot in {"left_side", "right_side"}:
        return "side"
    return expected_slot


def _predicted_view_group(predicted_view_raw: str | None) -> str | None:
    predicted_view_raw = _normalize_view_label(predicted_view_raw)
    if predicted_view_raw is None:
        return None
    if predicted_view_raw in INVALID_VIEW_LABELS:
        return "invalid"

    predicted_slot = canonical_slot(predicted_view_raw)
    if predicted_slot in {"left_side", "right_side"} or predicted_view_raw == "side_valid":
        return "side"
    if predicted_slot in {"front", "rear"}:
        return predicted_slot
    return predicted_slot


def _is_directional_view_mismatch(expected_slot: str, predicted_view_raw: str | None) -> bool:
    predicted_group = _predicted_view_group(predicted_view_raw)
    if predicted_group not in {"front", "rear", "side"}:
        return False
    return predicted_group != _expected_view_group(expected_slot)


def _should_reject_view_mismatch(expected_slot: str, predicted_view_raw: str | None, view_score: float, threshold: float) -> bool:
    predicted_view_raw = _normalize_view_label(predicted_view_raw)
    if predicted_view_raw is None:
        return True
    if predicted_view_raw in INVALID_VIEW_LABELS:
        return view_score >= threshold
    if _view_matches_expected(expected_slot, predicted_view_raw):
        return False
    return view_score >= threshold


def _view_matches_expected(expected_slot: str, predicted_view_raw: str | None) -> bool:
    predicted_view_raw = _normalize_view_label(predicted_view_raw)
    if predicted_view_raw is None:
        return False
    expected_aliases = {
        "front": {"front_valid", "front"},
        "rear": {"rear_valid", "rear"},
        "left_side": {"side_valid", "left_side_valid", "left_side"},
        "right_side": {"side_valid", "right_side_valid", "right_side"},
    }
    aliases = expected_aliases.get(expected_slot)
    if aliases and predicted_view_raw in aliases:
        return True
    return slot_matches(expected_slot, predicted_view_raw)


def _front_rear_confusion_override(expected_slot: str, predicted_view_raw: str | None, view_score: float, threshold: float, symmetry_score: float) -> bool:
    if expected_slot not in {"front", "rear"}:
        return False
    predicted_group = _predicted_view_group(predicted_view_raw)
    if predicted_group not in {"front", "rear"}:
        return False
    if predicted_group == _expected_view_group(expected_slot):
        return False
    if view_score >= threshold:
        return False
    return symmetry_score >= 0.74


# ── Real-model inference ─────────────────────────────────────────────

def _predict_real(image_pil, expected_slot: str) -> dict:
    """Run the trained EfficientNet-B0 multitask model."""
    import torch
    import torchvision.transforms as T

    model, meta = get_qv_model()
    if model is None:
        return _predict_mock(image_pil, expected_slot)

    vp_classes = meta.get("viewpoint_classes", DEFAULT_VIEWPOINT_CLASSES)
    qc_classes = meta.get("quality_classes", DEFAULT_QUALITY_CLASSES)
    trained_view_threshold = meta.get("view_threshold")
    trained_quality_threshold = meta.get("quality_reject_threshold")
    mean = meta.get("normalize_mean", [0.485, 0.456, 0.406])
    std = meta.get("normalize_std", [0.229, 0.224, 0.225])

    if isinstance(model, dict) and model.get("kind") == "split":
        quality_model = model["quality_gate"]
        view_model = model["view_validation"]
        quality_transform = T.Compose([
            T.Resize((meta.get("quality_image_size", 224), meta.get("quality_image_size", 224))),
            T.ToTensor(),
            T.Normalize(mean=mean, std=std),
        ])
        view_transform = T.Compose([
            T.Resize((meta.get("view_image_size", 224), meta.get("view_image_size", 224))),
            T.ToTensor(),
            T.Normalize(mean=mean, std=std),
        ])
        device = next(quality_model.parameters()).device
        quality_tensor = quality_transform(image_pil).unsqueeze(0).to(device)
        view_tensor = view_transform(image_pil).unsqueeze(0).to(device)

        with torch.no_grad():
            qc_logits = quality_model(quality_tensor)
            vp_logits = view_model(view_tensor)
    else:
        img_size = meta.get("image_size", 384)
        transform = T.Compose([
            T.Resize((img_size, img_size)),
            T.ToTensor(),
            T.Normalize(mean=mean, std=std),
        ])
        device = next(model.parameters()).device
        tensor = transform(image_pil).unsqueeze(0).to(device)

        with torch.no_grad():
            vp_logits, qc_logits = model(tensor)

    vp_probs = torch.softmax(vp_logits, dim=1).squeeze(0).cpu().numpy()
    qc_probs = torch.softmax(qc_logits, dim=1).squeeze(0).cpu().numpy()

    predicted_vp_idx = int(np.argmax(vp_probs))
    predicted_qc_idx = int(np.argmax(qc_probs))

    raw_view_label = vp_classes[predicted_vp_idx]
    predicted_view_raw = _normalize_view_label(raw_view_label)
    predicted_view = predicted_view_raw
    view_score = float(vp_probs[predicted_vp_idx])
    quality_label_raw = qc_classes[predicted_qc_idx]
    quality_label = _normalize_quality_label(quality_label_raw)
    quality_score = float(qc_probs[predicted_qc_idx])

    heuristic_label = _heuristic_quality_label(image_pil)
    symmetry_score = bilateral_symmetry_score(image_pil)
    binary_quality_gate = set(qc_classes) == {"accept", "reject"} and len(qc_classes) == 2
    quality_reject_threshold = (
        float(trained_quality_threshold)
        if trained_quality_threshold is not None
        else settings.quality_view_rejection_confidence
    )

    # ── Acceptance logic ──────────────────────────────────────────
    accepted = True
    rejection_reason = None

    # 1) Quality rejection:
    # For binary accept/reject gates, do not hard-reject by model output alone.
    # Require a simple image-quality heuristic to support the reject decision,
    # otherwise keep the frame and let later review steps decide.
    if binary_quality_gate:
        if quality_label == "quality_gate_reject" and quality_score >= quality_reject_threshold and heuristic_label:
            accepted = False
            quality_label = heuristic_label
            rejection_reason = quality_label
        elif quality_label == "quality_gate_reject":
            logger.info(
                "Binary quality gate predicted reject with score %.2f but no heuristic support — accepting",
                quality_score,
            )
            quality_label = heuristic_label or "good"
    elif quality_label != "good" and quality_score >= quality_reject_threshold:
        accepted = False
        rejection_reason = quality_label
    elif quality_label != "good":
        logger.info("Quality %s with low confidence %.2f — accepting", quality_label, quality_score)
        quality_label = heuristic_label or "good"

    # 2) Viewpoint mismatch: predicted view != expected with decent confidence
    base_view_threshold = float(trained_view_threshold) if trained_view_threshold is not None else settings.viewpoint_mismatch_threshold
    view_reject_threshold = max(base_view_threshold, _view_mismatch_threshold(expected_slot, predicted_view_raw))
    directional_view_mismatch = _is_directional_view_mismatch(expected_slot, predicted_view_raw)
    invalid_view_prediction = predicted_view_raw in INVALID_VIEW_LABELS

    if settings.quality_view_disable_viewpoint_check:
        predicted_view = expected_slot
    elif accepted and not _view_matches_expected(expected_slot, predicted_view_raw):
        if _front_rear_confusion_override(expected_slot, predicted_view_raw, view_score, view_reject_threshold, symmetry_score):
            predicted_view = f"{expected_slot}_valid"
            logger.info(
                "Accepting front/rear confusion by symmetry: expected=%s predicted=%s score=%.2f threshold=%.2f symmetry=%.3f",
                expected_slot,
                predicted_view_raw,
                view_score,
                view_reject_threshold,
                symmetry_score,
            )
        elif (
            directional_view_mismatch
            or invalid_view_prediction
            or _should_reject_view_mismatch(expected_slot, predicted_view_raw, view_score, view_reject_threshold)
        ):
            accepted = False
            rejection_reason = f"wrong_viewpoint: expected {expected_slot}, got {predicted_view_raw}"
            logger.info(
                "Rejecting viewpoint mismatch: expected=%s predicted=%s score=%.2f threshold=%.2f",
                expected_slot,
                predicted_view_raw,
                view_score,
                view_reject_threshold,
            )

    # 2.5) Product safety override for clear front/rear shots.
    # The current model can occasionally output angled_invalid for a straight,
    # symmetric rear/front frame. For the guided capture flow we prefer
    # accepting obviously frontal rear/front shots rather than forcing retakes.
    if (
        not accepted
        and not settings.quality_view_disable_viewpoint_check
        and expected_slot in {"front", "rear"}
        and predicted_view_raw in INVALID_VIEW_LABELS
        and quality_label == "good"
        and symmetry_score >= 0.74
    ):
        accepted = True
        predicted_view = f"{expected_slot}_valid"
        rejection_reason = None
        logger.info(
            "Overriding invalid viewpoint with symmetry heuristic: expected=%s raw=%s symmetry=%.3f",
            expected_slot,
            predicted_view_raw,
            symmetry_score,
        )

    # 3) Heuristic checks that neural net may miss.
    # Only use them as hard reject when the model itself is uncertain/good but the artifact is obvious.
    if accepted and heuristic_label and quality_score < max(quality_reject_threshold, 0.8):
        accepted = False
        quality_label = heuristic_label
        rejection_reason = heuristic_label

    # 4) Car presence helper — do not claim "no car" unless the image is actually tiny.
    car_present = image_pil.width >= 96 and image_pil.height >= 96
    car_confidence = 0.85 if car_present else 0.05
    if not car_present:
        accepted = False
        quality_label = "car_too_small"
        rejection_reason = "car_too_small"

    return {
        "accepted": accepted,
        "expected_slot": expected_slot,
        "predicted_view": predicted_view,
        "view_score": round(view_score, 4),
        "quality_label": quality_label,
        "quality_score": round(quality_score, 4),
        "raw_quality_label": quality_label_raw,
        "raw_view_label": raw_view_label,
        "normalized_view_label": predicted_view_raw,
        "heuristic_quality_label": heuristic_label,
        "symmetry_score": round(symmetry_score, 4),
        "trained_quality_threshold": round(quality_reject_threshold, 4),
        "view_reject_threshold": round(view_reject_threshold, 4),
        "rejection_reason": rejection_reason,
        "car_present": car_present,
        "car_confidence": round(car_confidence, 4),
        "car_bbox": {"x1": 0.08, "y1": 0.12, "x2": 0.92, "y2": 0.90},
        "model_backend": "real",
    }


# ── Mock inference ───────────────────────────────────────────────────

def _predict_mock(image_pil, expected_slot: str) -> dict:
    """Heuristic-based mock prediction (no model needed)."""
    blur = blur_score(image_pil)
    brightness = brightness_score(image_pil)

    quality_label = "good"
    rejection_reason = None
    accepted = True

    if brightness < 40:
        quality_label = "too_dark"
        rejection_reason = "too_dark"
        accepted = False
    elif brightness > 230:
        quality_label = "overexposed"
        rejection_reason = "overexposed"
        accepted = False
    elif blur < 60:
        quality_label = "too_blurry"
        rejection_reason = "too_blurry"
        accepted = False

    # Mock viewpoint: echo expected slot
    predicted_view = expected_slot if accepted else None
    view_score = 0.95 if accepted else 0.0

    # Mock car presence helper should only block obviously tiny uploads.
    car_present = image_pil.width >= 96 and image_pil.height >= 96
    car_confidence = 0.97 if car_present else 0.05
    car_bbox = {"x1": 0.08, "y1": 0.12, "x2": 0.92, "y2": 0.90}

    if not car_present:
        accepted = False
        quality_label = "car_too_small"
        rejection_reason = "car_too_small"

    return {
        "accepted": accepted,
        "expected_slot": expected_slot,
        "predicted_view": predicted_view,
        "view_score": view_score,
        "quality_label": quality_label,
        "quality_score": max(min((blur / 300.0), 1.0), 0.1),
        "rejection_reason": rejection_reason,
        "car_present": car_present,
        "car_confidence": car_confidence,
        "car_bbox": car_bbox,
        "model_backend": "mock",
    }


# ── Endpoint ─────────────────────────────────────────────────────────

@router.post("/predict")
async def predict(file: UploadFile = File(...), expected_slot: str = Form(...)):
    """Predict image quality and viewpoint.

    Returns:
        accepted: whether the photo passes quality + viewpoint checks
        quality_label: "good" | "too_dark" | "too_blurry" | "overexposed" | "car_too_small"
        predicted_view: the detected camera viewpoint
        view_score: confidence of viewpoint prediction
        rejection_reason: human-readable rejection reason (null if accepted)
    """
    data = await file.read()
    image = pil_from_bytes(data)

    backend = settings.inference_backend
    if backend in ("weights", "mlflow"):
        model, _ = get_qv_model()
        if model is not None:
            return _predict_real(image, expected_slot)
        logger.warning("QV model not loaded — falling back to mock")

    return _predict_mock(image, expected_slot)
