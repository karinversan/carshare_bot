"""Damage segmentation prediction endpoint.

Supports three backends:
  - mock: deterministic seeded random damages
  - weights/mlflow: real YOLOv8s-seg model with polygon + bbox output

Returns damage instances with bboxes, polygons, centroids, and an overlay PNG.
"""

import logging
import uuid

import numpy as np
from fastapi import APIRouter, UploadFile, File, Form

from services.inference_service.app.core.config import settings
from services.inference_service.app.model_registry import get_seg_model
from services.inference_service.app.utils.image import (
    pil_from_bytes, seeded_rng, overlay_png_b64,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/damage-seg", tags=["damage-seg"])

DAMAGE_CLASSES = ["scratch", "dent", "crack", "broken_part"]


# ── Real YOLO inference ──────────────────────────────────────────────

_DAMAGE_CLASS_ALIASES = {
    "scratch": "scratch",
    "царапина": "scratch",
    "scratches": "scratch",
    "dent": "dent",
    "вмятина": "dent",
    "dents": "dent",
    "crack": "crack",
    "трещина": "crack",
    "cracks": "crack",
    "broken_part": "broken_part",
    "broken-part": "broken_part",
    "сломанная_деталь": "broken_part",
    "сломанная_часть": "broken_part",
}


def _normalize_damage_type(label: str) -> str:
    value = str(label).strip().lower().replace(" ", "_")
    return _DAMAGE_CLASS_ALIASES.get(value, value)

def _predict_real(image_pil, slot_code: str) -> dict:
    """Run trained YOLOv8s-seg model on image."""
    model, meta = get_seg_model()
    if model is None:
        return _predict_mock(image_pil, slot_code)

    damage_classes = meta.get("damage_classes", DAMAGE_CLASSES)
    conf_thresh = settings.damage_seg_confidence_threshold
    post_conf_thresh = max(settings.damage_seg_post_filter_confidence, conf_thresh)
    min_area = settings.damage_seg_min_area_norm
    max_area = settings.damage_seg_max_area_norm
    run_id = str(uuid.uuid4())

    try:
        # Determine device
        device_str = "cpu"
        try:
            import torch
            if torch.cuda.is_available():
                device_str = "0"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device_str = "mps"
        except ImportError:
            pass

        results = model.predict(
            source=image_pil,
            device=device_str,
            imgsz=settings.damage_seg_inference_imgsz,
            conf=conf_thresh,
            verbose=False,
        )
    except RuntimeError as e:
        if "MPS" in str(e) or "mps" in str(e):
            logger.warning("MPS failed, falling back to CPU: %s", e)
            results = model.predict(
                source=image_pil, device="cpu", imgsz=settings.damage_seg_inference_imgsz,
                conf=conf_thresh, verbose=False,
            )
        else:
            raise

    result = results[0]
    img_w, img_h = image_pil.size
    damages = []
    mask_polygons = None
    if getattr(result, "masks", None) is not None and getattr(result.masks, "xy", None) is not None:
        mask_polygons = result.masks.xy

    # Extract detections
    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes
        for i in range(len(boxes)):
            cls_idx = int(boxes.cls[i].item())
            confidence = float(boxes.conf[i].item())

            if cls_idx >= len(damage_classes):
                continue

            # Normalized bbox [x1, y1, x2, y2]
            xyxy = boxes.xyxy[i].cpu().numpy()
            x1 = float(xyxy[0]) / img_w
            y1 = float(xyxy[1]) / img_h
            x2 = float(xyxy[2]) / img_w
            y2 = float(xyxy[3]) / img_h

            bbox_norm = {
                "x1": round(x1, 6), "y1": round(y1, 6),
                "x2": round(x2, 6), "y2": round(y2, 6),
            }

            centroid_x = round((x1 + x2) / 2, 4)
            centroid_y = round((y1 + y2) / 2, 4)
            area_norm = round((x2 - x1) * (y2 - y1), 6)
            if confidence < post_conf_thresh:
                continue
            if area_norm < min_area or area_norm > max_area:
                continue

            # Extract polygon from segmentation mask if available
            polygon_json = None
            mask_rle = None
            polygon_source = "bbox_fallback"

            if mask_polygons is not None and i < len(mask_polygons):
                # Ultralytics provides one polygon array per detected mask.
                poly_px = mask_polygons[i]
                if hasattr(poly_px, "cpu"):
                    poly_px = poly_px.cpu().numpy()
                elif not isinstance(poly_px, np.ndarray):
                    poly_px = np.array(poly_px)

                if poly_px.ndim == 2 and poly_px.shape[0] >= 3 and poly_px.shape[1] >= 2:
                    # Normalize polygon coords
                    poly_norm = []
                    for pt in poly_px:
                        px, py = float(pt[0]) / img_w, float(pt[1]) / img_h
                        poly_norm.append([round(px, 6), round(py, 6)])
                    polygon_json = poly_norm
                    polygon_source = "seg_mask"

                    # Simplify polygon if too many points (for JSON efficiency)
                    if len(polygon_json) > 50:
                        try:
                            import cv2
                            pts_arr = np.array(poly_px, dtype=np.float32).reshape(-1, 1, 2)
                            epsilon = 0.005 * cv2.arcLength(pts_arr, True)
                            approx = cv2.approxPolyDP(pts_arr, epsilon, True)
                            simplified = approx.reshape(-1, 2)
                            polygon_json = [
                                [round(float(p[0]) / img_w, 6), round(float(p[1]) / img_h, 6)]
                                for p in simplified
                            ]
                        except Exception:
                            pass  # keep original

            if polygon_json is None:
                # Fallback: use bbox as polygon
                polygon_json = [
                    [x1, y1], [x2, y1], [x2, y2], [x1, y2],
                ]

            damages.append({
                "damage_type": _normalize_damage_type(damage_classes[cls_idx]),
                "confidence": round(confidence, 3),
                "bbox_norm": bbox_norm,
                "centroid_x": centroid_x,
                "centroid_y": centroid_y,
                "area_norm": area_norm,
                "polygon_json": polygon_json,
                "mask_rle": mask_rle,
                "polygon_source": polygon_source,
            })

    overlay = overlay_png_b64(image_pil, damages) if damages else None

    return {
        "model_name": meta.get("model", "yolov8s-seg"),
        "model_version": meta.get("model_version", "trained"),
        "model_backend": "real",
        "inference_run_id": run_id,
        "damage_instances": damages,
        "overlay_png_b64": overlay,
    }


# ── Mock inference ───────────────────────────────────────────────────

def _predict_mock(image_pil, slot_code: str) -> dict:
    """Deterministic mock using seeded RNG."""
    import io
    image_bytes = io.BytesIO()
    image_pil.save(image_bytes, format="JPEG")
    rng = seeded_rng(image_bytes.getvalue() + slot_code.encode("utf-8"))

    n = rng.choice([0, 1, 1, 2])
    damages = []
    for _ in range(n):
        w = rng.uniform(0.08, 0.18)
        h = rng.uniform(0.04, 0.12)
        x1 = rng.uniform(0.1, 0.75)
        y1 = rng.uniform(0.1, 0.75)
        x2 = min(0.98, x1 + w)
        y2 = min(0.98, y1 + h)
        bbox = {"x1": round(x1, 6), "y1": round(y1, 6), "x2": round(x2, 6), "y2": round(y2, 6)}
        polygon = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        area_norm = (x2 - x1) * (y2 - y1)
        damages.append({
            "damage_type": rng.choice(DAMAGE_CLASSES),
            "confidence": round(rng.uniform(0.42, 0.91), 3),
            "bbox_norm": bbox,
            "centroid_x": round((x1 + x2) / 2, 4),
            "centroid_y": round((y1 + y2) / 2, 4),
            "area_norm": round(area_norm, 6),
            "polygon_json": polygon,
            "mask_rle": None,
        })

    overlay = overlay_png_b64(image_pil, damages) if damages else None
    return {
        "model_name": "mock_damage_seg",
        "model_version": "0.1.0",
        "model_backend": "mock",
        "inference_run_id": str(uuid.uuid4()),
        "damage_instances": damages,
        "overlay_png_b64": overlay,
    }


# ── Endpoint ─────────────────────────────────────────────────────────

@router.post("/predict")
async def predict(file: UploadFile = File(...), slot_code: str = Form(...)):
    """Predict damage segmentation on a car image.

    Returns:
        damage_instances: list of detected damages with bboxes, polygons, confidence
        overlay_png_b64: base64-encoded transparent PNG overlay with color-coded damage regions
    """
    data = await file.read()
    image = pil_from_bytes(data)

    backend = settings.inference_backend
    if backend in ("weights", "mlflow"):
        model, _ = get_seg_model()
        if model is not None:
            return _predict_real(image, slot_code)
        logger.warning("Seg model not loaded — falling back to mock")

    return _predict_mock(image, slot_code)
