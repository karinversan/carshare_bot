"""Quick single-image inference for damage segmentation checkpoints.

Example:
    . .venv/bin/activate && python ml/damage_seg/inference/run_quick_inference.py \
        --image path/to/image.jpg \
        --weights ml/damage_seg/weights/external/car-dd-segmentation-yolov11-best.pt
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WEIGHTS = ROOT / "ml" / "damage_seg" / "weights" / "external" / "car-dd-segmentation-yolov11-best.pt"
DEFAULT_METADATA = ROOT / "ml" / "damage_seg" / "weights" / "external" / "metadata.json"
DEFAULT_OUTPUT_DIR = ROOT / "ml" / "damage_seg" / "reports" / "quick_inference"


def _load_metadata(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_classes(classes: list[str], aliases: dict[str, str]) -> list[str]:
    return [aliases.get(cls, cls.replace(" ", "_")) for cls in classes]


def _detect_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "0"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _serialize_results(result, damage_classes: list[str], image_size: tuple[int, int]) -> list[dict]:
    img_w, img_h = image_size
    detections: list[dict] = []
    if result.boxes is None or len(result.boxes) == 0:
        return detections

    for i in range(len(result.boxes)):
        cls_idx = int(result.boxes.cls[i].item())
        if cls_idx >= len(damage_classes):
            continue

        xyxy = result.boxes.xyxy[i].cpu().numpy()
        x1 = float(xyxy[0]) / img_w
        y1 = float(xyxy[1]) / img_h
        x2 = float(xyxy[2]) / img_w
        y2 = float(xyxy[3]) / img_h

        polygon_json = None
        if result.masks is not None and i < len(result.masks):
            mask = result.masks[i]
            if mask.xy is not None and len(mask.xy) > 0:
                poly_px = mask.xy[0] if isinstance(mask.xy, list) else mask.xy
                if hasattr(poly_px, "cpu"):
                    poly_px = poly_px.cpu().numpy()
                elif not isinstance(poly_px, np.ndarray):
                    poly_px = np.array(poly_px)
                polygon_json = [
                    [round(float(pt[0]) / img_w, 6), round(float(pt[1]) / img_h, 6)]
                    for pt in poly_px
                ]

        if polygon_json is None:
            polygon_json = [
                [round(x1, 6), round(y1, 6)],
                [round(x2, 6), round(y1, 6)],
                [round(x2, 6), round(y2, 6)],
                [round(x1, 6), round(y2, 6)],
            ]

        detections.append(
            {
                "damage_type": damage_classes[cls_idx],
                "confidence": round(float(result.boxes.conf[i].item()), 4),
                "bbox_norm": {
                    "x1": round(x1, 6),
                    "y1": round(y1, 6),
                    "x2": round(x2, 6),
                    "y2": round(y2, 6),
                },
                "polygon_json": polygon_json,
            }
        )
    return detections


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to image file")
    parser.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=1024)
    args = parser.parse_args()

    image_path = Path(args.image).expanduser().resolve()
    weights_path = Path(args.weights).expanduser().resolve()
    metadata_path = Path(args.metadata).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = _load_metadata(metadata_path)
    aliases = metadata.get("class_aliases", {})

    model = YOLO(str(weights_path))
    names = getattr(model.model, "names", None)
    if isinstance(names, dict):
        raw_classes = [names[i] for i in sorted(names)]
    elif isinstance(names, list):
        raw_classes = names
    else:
        raw_classes = metadata.get("damage_classes", [])
    damage_classes = _normalize_classes(raw_classes, aliases)

    image = Image.open(image_path).convert("RGB")
    device = _detect_device()
    results = model.predict(
        source=image,
        imgsz=args.imgsz,
        conf=args.conf,
        device=device,
        verbose=False,
    )
    result = results[0]

    detections = _serialize_results(result, damage_classes, image.size)
    overlay = Image.fromarray(result.plot())

    stem = image_path.stem
    json_path = output_dir / f"{stem}_predictions.json"
    overlay_path = output_dir / f"{stem}_overlay.jpg"

    json_path.write_text(
        json.dumps(
            {
                "image": str(image_path),
                "weights": str(weights_path),
                "device": device,
                "imgsz": args.imgsz,
                "conf": args.conf,
                "damage_classes": damage_classes,
                "detections": detections,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    overlay.save(overlay_path, format="JPEG", quality=95)

    print(f"Detections: {len(detections)}")
    print(f"JSON: {json_path}")
    print(f"Overlay: {overlay_path}")


if __name__ == "__main__":
    main()
