#!/usr/bin/env python3
"""Evaluate a YOLO segmentation checkpoint and persist metrics JSON.

Default behavior:
- checkpoint: DAMAGE_SEG_WEIGHTS_PATH from env/.env, else ml/damage_seg/weights/best_damage_seg.pt
- dataset: ml/data/cardd_yolo_seg/data.yaml
- output:   ml/damage_seg/weights/external/<checkpoint_stem>_metrics.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_YAML = ROOT / "ml" / "data" / "cardd_yolo_seg" / "data.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "ml" / "damage_seg" / "weights" / "external"
ENV_PATH = ROOT / ".env"


def _read_env_file_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return None


def _resolve_checkpoint(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    from_env = os.getenv("DAMAGE_SEG_WEIGHTS_PATH") or _read_env_file_value(ENV_PATH, "DAMAGE_SEG_WEIGHTS_PATH")
    if from_env:
        return Path(from_env).expanduser()
    return ROOT / "ml" / "damage_seg" / "weights" / "best_damage_seg.pt"


def _device_for_ultralytics() -> str:
    from ml.utils.device import get_device

    device = str(get_device())
    if device == "cuda":
        return "0"
    return device


def _collect_metrics(results: Any) -> dict[str, Any]:
    raw = getattr(results, "results_dict", None) or {}
    metrics = {}
    for key, value in raw.items():
        try:
            metrics[key] = float(value)
        except (TypeError, ValueError):
            continue

    return {
        "metric_name": "metrics/mAP50(M)",
        "metric_value": metrics.get("metrics/mAP50(M)"),
        "trainer_metrics": metrics,
    }


def evaluate_checkpoint(
    checkpoint_path: Path,
    data_yaml: Path,
    imgsz: int = 1024,
    split: str = "val",
) -> dict[str, Any]:
    from ultralytics import YOLO

    model = YOLO(str(checkpoint_path))
    results = model.val(
        data=str(data_yaml),
        split=split,
        imgsz=imgsz,
        device=_device_for_ultralytics(),
        plots=False,
        verbose=False,
    )
    payload = _collect_metrics(results)
    payload.update(
        {
            "checkpoint_path": str(checkpoint_path),
            "data_yaml": str(data_yaml),
            "imgsz": imgsz,
            "split": split,
        }
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--data-yaml", default=str(DEFAULT_DATA_YAML))
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--split", default="val")
    args = parser.parse_args()

    checkpoint_path = _resolve_checkpoint(args.checkpoint)
    data_yaml = Path(args.data_yaml).expanduser()

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"checkpoint not found: {checkpoint_path}")
    if not data_yaml.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_yaml}")

    metrics = evaluate_checkpoint(checkpoint_path, data_yaml, imgsz=args.imgsz, split=args.split)

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DEFAULT_OUTPUT_DIR / f"{checkpoint_path.stem}_metrics.json"
    output_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()

