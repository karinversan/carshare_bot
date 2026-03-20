#!/usr/bin/env python3
"""CLI: Run paired pre/post trip evaluation.

Evaluates the diff engine by comparing pre-trip and post-trip final damage states
using the comparison domain logic. Generates a JSON evaluation report.

Usage:
    python -m ml.evaluation.paired_eval.run_paired_eval \
        --config ml/evaluation/paired_eval/configs/default.yaml
"""
import argparse, json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from apps.api_service.app.domain.comparisons import (
    bbox_iou, centroid_distance_normalized, area_similarity, match_score,
)


def generate_synthetic_pair():
    """Generate a synthetic pre/post damage pair for testing the diff engine."""
    import random
    random.seed(42)

    damage_types = ["scratch", "dent", "crack", "broken_part"]
    slots = ["front_left_3q", "front_right_3q", "rear_left_3q", "rear_right_3q"]

    pre_damages = []
    post_damages = []

    for slot in slots:
        n_pre = random.randint(0, 3)
        for _ in range(n_pre):
            x1, y1 = random.uniform(0.1, 0.7), random.uniform(0.1, 0.7)
            w, h = random.uniform(0.05, 0.2), random.uniform(0.05, 0.2)
            d = {
                "slot": slot,
                "damage_type": random.choice(damage_types),
                "bbox_norm": {"x1": x1, "y1": y1, "x2": x1 + w, "y2": y1 + h},
                "centroid_x": x1 + w / 2,
                "centroid_y": y1 + h / 2,
                "area_norm": w * h,
            }
            pre_damages.append(d)
            # 70% chance same damage persists in post with slight shift
            if random.random() < 0.7:
                shift_x = random.uniform(-0.03, 0.03)
                shift_y = random.uniform(-0.03, 0.03)
                pd = {**d}
                pd["bbox_norm"] = {
                    "x1": d["bbox_norm"]["x1"] + shift_x,
                    "y1": d["bbox_norm"]["y1"] + shift_y,
                    "x2": d["bbox_norm"]["x2"] + shift_x,
                    "y2": d["bbox_norm"]["y2"] + shift_y,
                }
                pd["centroid_x"] = d["centroid_x"] + shift_x
                pd["centroid_y"] = d["centroid_y"] + shift_y
                post_damages.append(pd)

        # Add new damages in post
        if random.random() < 0.3:
            x1, y1 = random.uniform(0.1, 0.7), random.uniform(0.1, 0.7)
            w, h = random.uniform(0.05, 0.15), random.uniform(0.05, 0.15)
            post_damages.append({
                "slot": slot,
                "damage_type": random.choice(damage_types),
                "bbox_norm": {"x1": x1, "y1": y1, "x2": x1 + w, "y2": y1 + h},
                "centroid_x": x1 + w / 2,
                "centroid_y": y1 + h / 2,
                "area_norm": w * h,
            })

    return pre_damages, post_damages


def run_eval(cfg: dict):
    strong_threshold = cfg["thresholds"]["strong_match"]
    weak_threshold = cfg["thresholds"]["weak_match"]

    pre_damages, post_damages = generate_synthetic_pair()
    logger.info("Pre-trip damages: %d, Post-trip damages: %d", len(pre_damages), len(post_damages))

    slots = set(d["slot"] for d in pre_damages + post_damages)
    results = []
    matched = possible_new = new_confirmed = 0

    for slot in sorted(slots):
        pre_slot = [d for d in pre_damages if d["slot"] == slot]
        post_slot = [d for d in post_damages if d["slot"] == slot]

        for post in post_slot:
            best_score_val = -1.0
            best_pre = None

            for pre in pre_slot:
                if pre["damage_type"] != post["damage_type"]:
                    continue
                iou = bbox_iou(pre["bbox_norm"], post["bbox_norm"])
                cdist = centroid_distance_normalized(
                    (pre["centroid_x"], pre["centroid_y"]),
                    (post["centroid_x"], post["centroid_y"]),
                )
                asim = area_similarity(pre["area_norm"], post["area_norm"])
                sc = match_score(iou, cdist, asim)
                if sc > best_score_val:
                    best_score_val = sc
                    best_pre = pre

            if best_pre and best_score_val >= strong_threshold:
                status = "matched_existing"
                matched += 1
            elif best_pre and best_score_val >= weak_threshold:
                status = "possible_match"
            else:
                status = "new_confirmed"
                new_confirmed += 1

            results.append({
                "slot": slot,
                "status": status,
                "match_score": round(max(best_score_val, 0.0), 4),
                "damage_type": post["damage_type"],
            })

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "diff_version": cfg.get("diff_version", "v1"),
        "thresholds": cfg["thresholds"],
        "pre_damage_count": len(pre_damages),
        "post_damage_count": len(post_damages),
        "matched_count": matched,
        "new_confirmed_count": new_confirmed,
        "possible_new_count": len([r for r in results if r["status"] == "possible_match"]),
        "details": results,
    }

    out_dir = ROOT / "ml" / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "paired_eval_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    logger.info("Evaluation report → %s", out_path)
    logger.info("Matched: %d | New confirmed: %d | Total post: %d", matched, new_confirmed, len(post_damages))

    # Validate scores are in proper range
    for r in results:
        assert 0.0 <= r["match_score"] <= 1.0, f"Score out of range: {r['match_score']}"

    logger.info("All match scores in [0, 1] — PASS")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    cfg = yaml.safe_load(Path(p.parse_args().config).read_text())
    run_eval(cfg)


if __name__ == "__main__":
    main()
