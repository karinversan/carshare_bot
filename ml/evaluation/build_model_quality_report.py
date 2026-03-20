#!/usr/bin/env python3
"""Build and persist a unified model-quality report for the demo project.

The script aggregates:
- quality gate metrics
- viewpoint validation metrics
- damage segmentation metrics
- paired pre/post diff evaluation metrics

Outputs:
- ml/evaluation/reports/model_quality_latest.json
- ml/evaluation/reports/model_quality_<timestamp>.json
- ml/evaluation/reports/model_quality_history.jsonl
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import random
import os

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "ml" / "evaluation" / "reports"
QUALITY_GATE_PATH = ROOT / "ml" / "quality_view" / "reports" / "quality_gate_test_report.json"
VIEW_VALIDATION_PATH = ROOT / "ml" / "quality_view" / "reports" / "view_validation_test_report.json"
PAIRED_CONFIG_PATH = ROOT / "ml" / "evaluation" / "paired_eval" / "configs" / "default.yaml"
PAIRED_REPORT_PATH = ROOT / "ml" / "evaluation" / "paired_eval_report.json"
SEG_WEIGHTS_DIR = ROOT / "ml" / "damage_seg" / "weights"
SEG_EXTERNAL_METRICS_DIR = SEG_WEIGHTS_DIR / "external"
ENV_PATH = ROOT / ".env"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_quality_gate_section(report: dict[str, Any]) -> dict[str, Any]:
    reject = report.get("reject", {})
    macro = report.get("macro avg", {})
    weighted = report.get("weighted avg", {})
    return {
        "accuracy": _safe_float(report.get("accuracy")),
        "macro_f1": _safe_float(macro.get("f1-score")),
        "weighted_f1": _safe_float(weighted.get("f1-score")),
        "reject_precision": _safe_float(reject.get("precision")),
        "reject_recall": _safe_float(reject.get("recall")),
        "support": int(report.get("macro avg", {}).get("support", 0)),
    }


def _build_view_section(report: dict[str, Any]) -> dict[str, Any]:
    macro = report.get("macro avg", {})
    classes = {
        "front_valid_f1": _safe_float(report.get("front_valid", {}).get("f1-score")),
        "rear_valid_f1": _safe_float(report.get("rear_valid", {}).get("f1-score")),
        "side_valid_f1": _safe_float(report.get("side_valid", {}).get("f1-score")),
        "angled_invalid_f1": _safe_float(report.get("angled_invalid", {}).get("f1-score")),
        "other_invalid_f1": _safe_float(report.get("other_invalid", {}).get("f1-score")),
    }
    return {
        "accuracy": _safe_float(report.get("accuracy")),
        "macro_f1": _safe_float(macro.get("f1-score")),
        "classes": classes,
        "support": int(report.get("macro avg", {}).get("support", 0)),
    }


def _select_latest_seg_metrics_file() -> Path | None:
    if not SEG_WEIGHTS_DIR.exists():
        return None
    candidates = sorted(SEG_WEIGHTS_DIR.glob("*_metrics.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _read_env_file_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() != key:
            continue
        return v.strip().strip('"').strip("'")
    return None


def _active_seg_checkpoint_path() -> Path:
    from_env = os.getenv("DAMAGE_SEG_WEIGHTS_PATH") or _read_env_file_value(ENV_PATH, "DAMAGE_SEG_WEIGHTS_PATH")
    if from_env:
        return Path(from_env).expanduser()
    return SEG_WEIGHTS_DIR / "best_damage_seg.pt"


def _metrics_candidates_for_checkpoint(ckpt_path: Path) -> list[Path]:
    stem = ckpt_path.stem
    return [
        ckpt_path.with_name(f"{stem}_metrics.json"),
        SEG_WEIGHTS_DIR / f"{stem}_metrics.json",
        SEG_EXTERNAL_METRICS_DIR / f"{stem}_metrics.json",
    ]


def _select_seg_metrics_file_for_active_checkpoint() -> tuple[Path | None, Path]:
    ckpt_path = _active_seg_checkpoint_path()
    for candidate in _metrics_candidates_for_checkpoint(ckpt_path):
        if candidate.exists():
            return candidate, ckpt_path

    # Legacy fallback for old local naming.
    if ckpt_path.name == "best_damage_seg.pt":
        legacy = SEG_WEIGHTS_DIR / "best_damage_seg_metrics.json"
        if legacy.exists():
            return legacy, ckpt_path

    return None, ckpt_path


def _build_segmentation_section(metrics_path: Path) -> dict[str, Any]:
    payload = _load_json(metrics_path)
    trainer = payload.get("trainer_metrics", payload)
    return {
        "source": str(metrics_path),
        "metric_name": payload.get("metric_name"),
        "metric_value": _safe_float(payload.get("metric_value")),
        "precision_m": _safe_float(trainer.get("metrics/precision(M)")),
        "recall_m": _safe_float(trainer.get("metrics/recall(M)")),
        "map50_m": _safe_float(trainer.get("metrics/mAP50(M)")),
        "map50_95_m": _safe_float(trainer.get("metrics/mAP50-95(M)")),
        "epoch": payload.get("epoch"),
    }


def _run_paired_eval_if_requested(refresh_paired: bool) -> None:
    if not refresh_paired:
        return

    cfg = {"diff_version": "v1", "thresholds": {"strong_match": 0.65, "weak_match": 0.45}}
    if PAIRED_CONFIG_PATH.exists():
        try:
            import yaml  # type: ignore

            cfg = yaml.safe_load(PAIRED_CONFIG_PATH.read_text(encoding="utf-8")) or cfg
        except Exception:
            # Keep default thresholds if yaml dependency is unavailable.
            pass

    from apps.api_service.app.domain.comparisons import (
        area_similarity,
        bbox_iou,
        centroid_distance_normalized,
        match_score,
    )

    def _generate_synthetic_pair() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        random.seed(42)
        damage_types = ["scratch", "dent", "crack", "broken_part"]
        slots = ["front_left_3q", "front_right_3q", "rear_left_3q", "rear_right_3q"]
        pre: list[dict[str, Any]] = []
        post: list[dict[str, Any]] = []
        for slot in slots:
            n_pre = random.randint(0, 3)
            for _ in range(n_pre):
                x1, y1 = random.uniform(0.1, 0.7), random.uniform(0.1, 0.7)
                w, h = random.uniform(0.05, 0.2), random.uniform(0.05, 0.2)
                dmg = {
                    "slot": slot,
                    "damage_type": random.choice(damage_types),
                    "bbox_norm": {"x1": x1, "y1": y1, "x2": x1 + w, "y2": y1 + h},
                    "centroid_x": x1 + (w / 2),
                    "centroid_y": y1 + (h / 2),
                    "area_norm": w * h,
                }
                pre.append(dmg)
                if random.random() < 0.7:
                    shift_x = random.uniform(-0.03, 0.03)
                    shift_y = random.uniform(-0.03, 0.03)
                    post.append(
                        {
                            **dmg,
                            "bbox_norm": {
                                "x1": dmg["bbox_norm"]["x1"] + shift_x,
                                "y1": dmg["bbox_norm"]["y1"] + shift_y,
                                "x2": dmg["bbox_norm"]["x2"] + shift_x,
                                "y2": dmg["bbox_norm"]["y2"] + shift_y,
                            },
                            "centroid_x": dmg["centroid_x"] + shift_x,
                            "centroid_y": dmg["centroid_y"] + shift_y,
                        }
                    )
            if random.random() < 0.3:
                x1, y1 = random.uniform(0.1, 0.7), random.uniform(0.1, 0.7)
                w, h = random.uniform(0.05, 0.15), random.uniform(0.05, 0.15)
                post.append(
                    {
                        "slot": slot,
                        "damage_type": random.choice(damage_types),
                        "bbox_norm": {"x1": x1, "y1": y1, "x2": x1 + w, "y2": y1 + h},
                        "centroid_x": x1 + (w / 2),
                        "centroid_y": y1 + (h / 2),
                        "area_norm": w * h,
                    }
                )
        return pre, post

    pre_damages, post_damages = _generate_synthetic_pair()
    strong_threshold = float(cfg["thresholds"]["strong_match"])
    weak_threshold = float(cfg["thresholds"]["weak_match"])
    slots = sorted({d["slot"] for d in (pre_damages + post_damages)})

    matched = 0
    new_confirmed = 0
    possible_new = 0
    details: list[dict[str, Any]] = []

    for slot in slots:
        pre_slot = [d for d in pre_damages if d["slot"] == slot]
        post_slot = [d for d in post_damages if d["slot"] == slot]
        for post in post_slot:
            best_score = -1.0
            for pre in pre_slot:
                if pre["damage_type"] != post["damage_type"]:
                    continue
                iou = bbox_iou(pre["bbox_norm"], post["bbox_norm"])
                cdist = centroid_distance_normalized(
                    (pre["centroid_x"], pre["centroid_y"]),
                    (post["centroid_x"], post["centroid_y"]),
                )
                asim = area_similarity(pre["area_norm"], post["area_norm"])
                score = match_score(iou, cdist, asim)
                best_score = max(best_score, score)
            best_score = max(best_score, 0.0)

            if best_score >= strong_threshold:
                status = "matched_existing"
                matched += 1
            elif best_score >= weak_threshold:
                status = "possible_match"
                possible_new += 1
            else:
                status = "new_confirmed"
                new_confirmed += 1

            details.append(
                {
                    "slot": slot,
                    "status": status,
                    "match_score": round(best_score, 4),
                    "damage_type": post["damage_type"],
                }
            )

    paired_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "diff_version": cfg.get("diff_version", "v1"),
        "thresholds": cfg["thresholds"],
        "pre_damage_count": len(pre_damages),
        "post_damage_count": len(post_damages),
        "matched_count": matched,
        "new_confirmed_count": new_confirmed,
        "possible_new_count": possible_new,
        "details": details,
    }
    PAIRED_REPORT_PATH.write_text(json.dumps(paired_report, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_paired_section(report: dict[str, Any]) -> dict[str, Any]:
    post_count = int(report.get("post_damage_count", 0))
    new_confirmed = int(report.get("new_confirmed_count", 0))
    matched = int(report.get("matched_count", 0))
    possible_new = int(report.get("possible_new_count", 0))
    new_rate = (new_confirmed / post_count) if post_count else 0.0
    return {
        "post_damage_count": post_count,
        "matched_count": matched,
        "new_confirmed_count": new_confirmed,
        "possible_new_count": possible_new,
        "new_confirmed_rate": round(new_rate, 6),
        "diff_version": report.get("diff_version"),
        "thresholds": report.get("thresholds", {}),
    }


def build_model_quality_report(refresh_paired: bool) -> dict[str, Any]:
    _run_paired_eval_if_requested(refresh_paired)

    generated_at = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "quality_gate": None,
        "view_validation": None,
        "damage_segmentation": None,
        "paired_comparison": None,
        "notes": [],
    }

    if QUALITY_GATE_PATH.exists():
        report["quality_gate"] = _build_quality_gate_section(_load_json(QUALITY_GATE_PATH))
    else:
        report["notes"].append(f"quality_gate report missing: {QUALITY_GATE_PATH}")

    if VIEW_VALIDATION_PATH.exists():
        report["view_validation"] = _build_view_section(_load_json(VIEW_VALIDATION_PATH))
    else:
        report["notes"].append(f"view_validation report missing: {VIEW_VALIDATION_PATH}")

    seg_metrics_path, seg_ckpt_path = _select_seg_metrics_file_for_active_checkpoint()
    if seg_metrics_path is not None:
        report["damage_segmentation"] = _build_segmentation_section(seg_metrics_path)
        report["damage_segmentation"]["checkpoint_path"] = str(seg_ckpt_path)
    else:
        fallback = _select_latest_seg_metrics_file()
        if fallback is not None:
            report["damage_segmentation"] = _build_segmentation_section(fallback)
            report["damage_segmentation"]["checkpoint_path"] = str(seg_ckpt_path)
            report["notes"].append(
                "no metrics for active segmentation checkpoint; fallback metrics were used"
            )
        else:
            report["notes"].append(
                "damage_segmentation metrics are missing for the active segmentation checkpoint"
            )

    if PAIRED_REPORT_PATH.exists():
        report["paired_comparison"] = _build_paired_section(_load_json(PAIRED_REPORT_PATH))
    else:
        report["notes"].append(f"paired comparison report missing: {PAIRED_REPORT_PATH}")

    return report


def persist_report(report: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = REPORTS_DIR / "model_quality_latest.json"
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = REPORTS_DIR / f"model_quality_{ts}.json"
    snapshot_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    history_path = REPORTS_DIR / "model_quality_history.jsonl"
    with history_path.open("a", encoding="utf-8") as history_file:
        history_file.write(json.dumps(report, ensure_ascii=False) + "\n")

    return latest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-paired", action="store_true", default=False)
    args = parser.parse_args()

    report = build_model_quality_report(refresh_paired=args.refresh_paired)
    output = persist_report(report)
    print(output)


if __name__ == "__main__":
    main()
