"""Balanced dataset builder for damage segmentation."""

from __future__ import annotations

import csv
import json
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from PIL import Image


DAMAGE_CLASSES = ["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"]
COCO_TO_YOLO_CLASS_MAP = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
SPLIT_MAP = {
    "instances_train2017.json": ("train2017", "train"),
    "instances_val2017.json": ("val2017", "val"),
    "instances_test2017.json": ("test2017", "test"),
}
VIEWPOINT_ID_TO_CLASS = {1: "front_valid", 2: "rear_valid", 3: "side_valid"}
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

DEFAULT_SEG_BUILD_CONFIG = {
    "seed": 42,
    "balance_mode": "capped",
    "positive_class_cap_ratio": 1.5,
    "negative_full_ratio": 0.15,
    "negative_crop_ratio": 0.05,
    "compcars_split": {"train": 0.70, "val": 0.15, "test": 0.15},
    "crop": {"min_fraction": 0.45, "max_fraction": 0.75, "min_side": 224},
}


@dataclass(frozen=True)
class PositiveRecord:
    image_path: Path
    file_name: str
    split: str
    label_lines: tuple[str, ...]
    class_counts: tuple[int, ...]


@dataclass(frozen=True)
class CompCarsRecord:
    image_path: Path
    bbox: tuple[int, int, int, int]
    viewpoint_id: int


def find_cardd_coco_dir(cardd_dir: Path) -> Path:
    candidates = [
        cardd_dir / "CarDD_release" / "CarDD_COCO",
        cardd_dir / "CarDD_COCO",
        cardd_dir,
    ]
    for candidate in candidates:
        if (candidate / "annotations").exists():
            return candidate
    raise FileNotFoundError(f"CarDD COCO annotations not found under {cardd_dir}")


def normalize_polygon(poly: Iterable[float], width: int, height: int) -> list[float]:
    pts: list[float] = []
    poly = list(poly)
    for i in range(0, len(poly), 2):
        x = min(max(poly[i] / width, 0.0), 1.0)
        y = min(max(poly[i + 1] / height, 0.0), 1.0)
        pts.extend([x, y])
    return pts


def ann_to_polygons(ann: dict) -> list[list[float]]:
    seg = ann.get("segmentation", [])
    if not seg or isinstance(seg, dict):
        return []
    return [poly for poly in seg if len(poly) >= 6]


def split_list(items: list, ratios: dict[str, float], seed: int) -> dict[str, list]:
    items = list(items)
    rnd = random.Random(seed)
    rnd.shuffle(items)

    n_total = len(items)
    n_train = int(n_total * ratios["train"])
    n_val = int(n_total * ratios["val"])
    return {
        "train": items[:n_train],
        "val": items[n_train : n_train + n_val],
        "test": items[n_train + n_val :],
    }


def _resolve_compcars_image(label_root: Path, image_root: Path, label_path: Path) -> Path | None:
    relative = label_path.relative_to(label_root).with_suffix("")
    for ext in IMAGE_EXTS:
        candidate = image_root / relative.with_suffix(ext)
        if candidate.exists():
            return candidate
    return None


def _parse_bbox(line: str) -> tuple[int, int, int, int] | None:
    parts = line.split()
    if len(parts) != 4:
        return None
    try:
        x1, y1, x2, y2 = (int(v) for v in parts)
    except ValueError:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def load_compcars_negative_pool(compcars_dir: Path) -> list[CompCarsRecord]:
    image_root = compcars_dir / "data" / "image"
    label_root = compcars_dir / "data" / "label"
    if not image_root.exists() or not label_root.exists():
        raise FileNotFoundError("CompCars full-car structure data/image + data/label not found")

    records: list[CompCarsRecord] = []
    for label_path in sorted(label_root.rglob("*.txt")):
        lines = label_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if len(lines) < 3:
            continue
        try:
            viewpoint_id = int(lines[0].strip())
        except ValueError:
            continue
        if viewpoint_id not in VIEWPOINT_ID_TO_CLASS:
            continue
        bbox = _parse_bbox(lines[2].strip())
        if bbox is None:
            continue
        image_path = _resolve_compcars_image(label_root, image_root, label_path)
        if image_path is None:
            continue
        records.append(CompCarsRecord(image_path=image_path, bbox=bbox, viewpoint_id=viewpoint_id))
    return records


def load_positive_records(cardd_dir: Path) -> tuple[dict[str, list[PositiveRecord]], dict[str, dict[str, int]]]:
    coco_dir = find_cardd_coco_dir(cardd_dir)
    split_records: dict[str, list[PositiveRecord]] = {}
    split_totals: dict[str, dict[str, int]] = {}

    for ann_filename, (img_dir_name, split_name) in SPLIT_MAP.items():
        ann_path = coco_dir / "annotations" / ann_filename
        img_dir = coco_dir / img_dir_name
        coco = json.loads(ann_path.read_text(encoding="utf-8"))
        images_by_id = {img["id"]: img for img in coco["images"]}
        anns_by_img: dict[int, list[dict]] = defaultdict(list)
        totals = Counter()

        for ann in coco["annotations"]:
            anns_by_img[ann["image_id"]].append(ann)

        records: list[PositiveRecord] = []
        for img_id, img_info in images_by_id.items():
            src_img = img_dir / img_info["file_name"]
            if not src_img.exists():
                continue

            class_counts = [0] * len(DAMAGE_CLASSES)
            lines: list[str] = []
            for ann in anns_by_img.get(img_id, []):
                cat_id = ann.get("category_id")
                if cat_id not in COCO_TO_YOLO_CLASS_MAP:
                    continue
                cls_idx = COCO_TO_YOLO_CLASS_MAP[cat_id]
                for poly in ann_to_polygons(ann):
                    norm = normalize_polygon(poly, img_info["width"], img_info["height"])
                    if len(norm) < 6:
                        continue
                    lines.append(f"{cls_idx} " + " ".join(f"{v:.6f}" for v in norm))
                    class_counts[cls_idx] += 1
                    totals[DAMAGE_CLASSES[cls_idx]] += 1

            if lines:
                records.append(
                    PositiveRecord(
                        image_path=src_img,
                        file_name=img_info["file_name"],
                        split=split_name,
                        label_lines=tuple(lines),
                        class_counts=tuple(class_counts),
                    )
                )

        split_records[split_name] = records
        split_totals[split_name] = dict(totals)
    return split_records, split_totals


def _greedy_select(records: list[PositiveRecord], target: int, seed: int) -> tuple[list[PositiveRecord], list[int]]:
    rnd = random.Random(seed)
    order = list(range(len(records)))
    rnd.shuffle(order)
    rank = {idx: pos for pos, idx in enumerate(order)}
    counts = [0] * len(DAMAGE_CLASSES)
    remaining = set(order)
    selected: list[PositiveRecord] = []

    while True:
        deficits = [target - count for count in counts]
        if all(deficit == 0 for deficit in deficits):
            break

        candidates = []
        for idx in remaining:
            rec = records[idx]
            if any(counts[i] + rec.class_counts[i] > target for i in range(len(DAMAGE_CLASSES))):
                continue
            benefit = sum(min(deficits[i], rec.class_counts[i]) for i in range(len(DAMAGE_CLASSES)))
            if benefit <= 0:
                continue
            covered_classes = sum(1 for i, value in enumerate(rec.class_counts) if value and deficits[i] > 0)
            total_instances = sum(rec.class_counts)
            active_classes = sum(1 for value in rec.class_counts if value)
            candidates.append((-benefit, active_classes, total_instances, -covered_classes, rank[idx], idx))

        if not candidates:
            break

        _, _, _, _, _, best_idx = min(candidates)
        rec = records[best_idx]
        selected.append(rec)
        remaining.remove(best_idx)
        counts = [counts[i] + rec.class_counts[i] for i in range(len(DAMAGE_CLASSES))]

    return selected, counts


def select_exact_balanced_positive_records(
    records: list[PositiveRecord], seed: int, retries: int = 12
) -> tuple[list[PositiveRecord], int, list[int], bool]:
    totals = [sum(rec.class_counts[i] for rec in records) for i in range(len(DAMAGE_CLASSES))]
    if not records or min(totals) == 0:
        raise RuntimeError("Cannot balance dataset with empty class counts")

    best_selection: list[PositiveRecord] = []
    best_counts = [0] * len(DAMAGE_CLASSES)
    best_target = 0

    target = min(totals)
    while target > 0:
        best_min_count_for_target = 0
        for retry in range(retries):
            selected, counts = _greedy_select(records, target=target, seed=seed + retry + (target * 1000))
            if all(count == target for count in counts):
                return selected, target, counts, True

            current_key = (min(counts), sum(counts))
            best_key = (min(best_counts), sum(best_counts))
            if current_key > best_key:
                best_selection = selected
                best_counts = counts
                best_target = target
            best_min_count_for_target = max(best_min_count_for_target, min(counts))

        next_target = min(target - 1, best_min_count_for_target)
        if next_target <= 0:
            break
        target = next_target

    return best_selection, best_target, best_counts, False


def select_capped_positive_records(
    records: list[PositiveRecord], seed: int, cap_ratio: float
) -> tuple[list[PositiveRecord], list[int], list[int], int]:
    totals = [sum(rec.class_counts[i] for rec in records) for i in range(len(DAMAGE_CLASSES))]
    if not records or min(totals) == 0:
        raise RuntimeError("Cannot balance dataset with empty class counts")
    if cap_ratio < 1.0:
        raise ValueError("cap_ratio must be >= 1.0")

    reference_count = min(totals)
    class_caps = [min(total, int(round(reference_count * cap_ratio))) for total in totals]
    class_caps = [max(cap, reference_count) for cap in class_caps]
    rarity_weights = [1.0 / total for total in totals]

    rnd = random.Random(seed)
    order = list(range(len(records)))
    rnd.shuffle(order)
    rank = {idx: pos for pos, idx in enumerate(order)}

    order.sort(
        key=lambda idx: (
            -sum((1 if records[idx].class_counts[i] else 0) * rarity_weights[i] for i in range(len(DAMAGE_CLASSES))),
            sum(1 for value in records[idx].class_counts if value),
            sum(records[idx].class_counts),
            rank[idx],
        )
    )

    counts = [0] * len(DAMAGE_CLASSES)
    selected: list[PositiveRecord] = []
    for idx in order:
        rec = records[idx]
        if any(counts[i] + rec.class_counts[i] > class_caps[i] for i in range(len(DAMAGE_CLASSES))):
            continue
        selected.append(rec)
        counts = [counts[i] + rec.class_counts[i] for i in range(len(DAMAGE_CLASSES))]

    return selected, counts, class_caps, reference_count


def select_positive_records(
    records: list[PositiveRecord],
    seed: int,
    balance_mode: str = "capped",
    positive_class_cap_ratio: float = 1.5,
    retries: int = 12,
) -> dict:
    if balance_mode == "exact":
        selected, target, counts, exact = select_exact_balanced_positive_records(records, seed=seed, retries=retries)
        return {
            "selected": selected,
            "counts": counts,
            "exact": exact,
            "reference_count": target,
            "class_caps": [target] * len(DAMAGE_CLASSES),
            "balance_mode": balance_mode,
        }
    if balance_mode == "capped":
        selected, counts, class_caps, reference_count = select_capped_positive_records(
            records,
            seed=seed,
            cap_ratio=positive_class_cap_ratio,
        )
        return {
            "selected": selected,
            "counts": counts,
            "exact": False,
            "reference_count": reference_count,
            "class_caps": class_caps,
            "balance_mode": balance_mode,
        }
    raise ValueError(f"Unsupported balance_mode: {balance_mode}")


def _save_rgb_image(src: Path, dst: Path) -> None:
    with Image.open(src) as image:
        image.convert("RGB").save(dst, quality=95)


def _make_negative_crop(image_path: Path, bbox: tuple[int, int, int, int], viewpoint_id: int, seed: int, cfg: dict) -> Image.Image:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        x1, y1, x2, y2 = bbox
        bw, bh = x2 - x1, y2 - y1
        rnd = random.Random(seed)

        crop_w = max(min(int(bw * rnd.uniform(cfg["min_fraction"], cfg["max_fraction"])), bw), 1)
        crop_h = max(min(int(bh * rnd.uniform(cfg["min_fraction"], cfg["max_fraction"])), bh), 1)

        preferred_templates = {
            1: [(0.5, 0.35), (0.5, 0.55), (0.35, 0.55)],
            2: [(0.5, 0.55), (0.5, 0.35), (0.65, 0.55)],
            3: [(0.3, 0.5), (0.7, 0.5), (0.5, 0.5)],
        }
        tx, ty = rnd.choice(preferred_templates.get(viewpoint_id, [(0.5, 0.5)]))
        span_x = max(bw - crop_w, 0)
        span_y = max(bh - crop_h, 0)
        crop_x1 = x1 + int(span_x * tx)
        crop_y1 = y1 + int(span_y * ty)
        crop_x1 = min(max(crop_x1, x1), x2 - crop_w)
        crop_y1 = min(max(crop_y1, y1), y2 - crop_h)

        crop = image.crop((crop_x1, crop_y1, crop_x1 + crop_w, crop_y1 + crop_h))
        min_side = cfg["min_side"]
        if min(crop.size) < min_side:
            scale = min_side / min(crop.size)
            crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.Resampling.LANCZOS)
        return crop


def build_balanced_damage_seg_dataset(
    cardd_dir: Path,
    output_dir: Path,
    compcars_dir: Path | None = None,
    clear_existing: bool = True,
    seed: int = 42,
    balance_mode: str = "capped",
    positive_class_cap_ratio: float = 1.5,
    negative_full_ratio: float = 0.15,
    negative_crop_ratio: float = 0.05,
    split_ratios: dict[str, float] | None = None,
    crop_cfg: dict | None = None,
) -> dict:
    split_ratios = split_ratios or DEFAULT_SEG_BUILD_CONFIG["compcars_split"]
    crop_cfg = crop_cfg or DEFAULT_SEG_BUILD_CONFIG["crop"]

    if clear_existing and output_dir.exists():
        for subdir in ["images", "labels"]:
            target = output_dir / subdir
            if target.exists():
                shutil.rmtree(target)
        for artifact in ["data.yaml", "build_manifest.csv", "build_stats.json"]:
            target = output_dir / artifact
            if target.exists():
                target.unlink()

    output_dir.mkdir(parents=True, exist_ok=True)
    split_records, split_totals = load_positive_records(cardd_dir)

    manifest_rows: list[dict[str, str | int]] = []
    summary = {"seed": seed, "splits": {}, "source_positive_counts": split_totals}

    for split_name, records in split_records.items():
        out_images = output_dir / "images" / split_name
        out_labels = output_dir / "labels" / split_name
        out_images.mkdir(parents=True, exist_ok=True)
        out_labels.mkdir(parents=True, exist_ok=True)

        selection = select_positive_records(
            records,
            seed=seed,
            balance_mode=balance_mode,
            positive_class_cap_ratio=positive_class_cap_ratio,
        )
        selected = selection["selected"]
        counts = selection["counts"]
        for rec in selected:
            shutil.copy2(rec.image_path, out_images / rec.file_name)
            (out_labels / f"{Path(rec.file_name).stem}.txt").write_text("\n".join(rec.label_lines), encoding="utf-8")
            manifest_rows.append(
                {
                    "split": split_name,
                    "kind": "positive",
                    "file_name": rec.file_name,
                    "source": "cardd",
                    "class_counts": json.dumps(rec.class_counts),
                }
            )

        summary["splits"][split_name] = {
            "positive_images": len(selected),
            "positive_balance_mode": selection["balance_mode"],
            "positive_reference_count": selection["reference_count"],
            "positive_class_caps": {name: selection["class_caps"][i] for i, name in enumerate(DAMAGE_CLASSES)},
            "positive_class_counts": {name: counts[i] for i, name in enumerate(DAMAGE_CLASSES)},
            "positive_exact_balance": selection["exact"],
        }

    if compcars_dir and (negative_full_ratio > 0 or negative_crop_ratio > 0):
        compcars_pool = load_compcars_negative_pool(compcars_dir)
        compcars_splits = split_list(compcars_pool, ratios=split_ratios, seed=seed)

        for split_name, pool in compcars_splits.items():
            split_seed = {"train": 11, "val": 17, "test": 23}[split_name]
            rnd = random.Random(seed + split_seed)
            pool = list(pool)
            rnd.shuffle(pool)

            positive_images = summary["splits"][split_name]["positive_images"]
            full_target = int(round(positive_images * negative_full_ratio))
            crop_target = int(round(positive_images * negative_crop_ratio))
            out_images = output_dir / "images" / split_name
            out_labels = output_dir / "labels" / split_name

            saved_full = 0
            for record in pool:
                if saved_full >= full_target:
                    break
                file_name = f"compcars_neg_{saved_full:05d}.jpg"
                try:
                    _save_rgb_image(record.image_path, out_images / file_name)
                except Exception:
                    continue
                (out_labels / f"{Path(file_name).stem}.txt").write_text("", encoding="utf-8")
                manifest_rows.append(
                    {
                        "split": split_name,
                        "kind": "negative_full",
                        "file_name": file_name,
                        "source": "compcars",
                        "class_counts": json.dumps([0] * len(DAMAGE_CLASSES)),
                    }
                )
                saved_full += 1

            saved_crop = 0
            for idx, record in enumerate(pool[saved_full:]):
                if saved_crop >= crop_target:
                    break
                file_name = f"compcars_crop_neg_{saved_crop:05d}.jpg"
                try:
                    crop = _make_negative_crop(record.image_path, record.bbox, record.viewpoint_id, seed + idx, crop_cfg)
                    crop.save(out_images / file_name, quality=95)
                except Exception:
                    continue
                (out_labels / f"{Path(file_name).stem}.txt").write_text("", encoding="utf-8")
                manifest_rows.append(
                    {
                        "split": split_name,
                        "kind": "negative_crop",
                        "file_name": file_name,
                        "source": "compcars_crop",
                        "class_counts": json.dumps([0] * len(DAMAGE_CLASSES)),
                    }
                )
                saved_crop += 1

            summary["splits"][split_name]["negative_full_images"] = saved_full
            summary["splits"][split_name]["negative_crop_images"] = saved_crop

    data_yaml = {
        "path": str(output_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {i: name for i, name in enumerate(DAMAGE_CLASSES)},
    }
    (output_dir / "data.yaml").write_text(
        yaml.safe_dump(data_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with (output_dir / "build_manifest.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["split", "kind", "file_name", "source", "class_counts"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    (output_dir / "build_stats.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_full_cardd_damage_seg_dataset(
    cardd_dir: Path,
    output_dir: Path,
    clear_existing: bool = True,
    seed: int = 42,
) -> dict:
    """Build baseline YOLO-seg dataset from all CarDD positives using original splits."""
    if clear_existing and output_dir.exists():
        for subdir in ["images", "labels"]:
            target = output_dir / subdir
            if target.exists():
                shutil.rmtree(target)
        for artifact in ["data.yaml", "build_manifest.csv", "build_stats.json"]:
            target = output_dir / artifact
            if target.exists():
                target.unlink()

    output_dir.mkdir(parents=True, exist_ok=True)
    split_records, split_totals = load_positive_records(cardd_dir)

    manifest_rows: list[dict[str, str | int]] = []
    summary = {"seed": seed, "mode": "full_cardd_baseline", "splits": {}, "source_positive_counts": split_totals}

    for split_name, records in split_records.items():
        out_images = output_dir / "images" / split_name
        out_labels = output_dir / "labels" / split_name
        out_images.mkdir(parents=True, exist_ok=True)
        out_labels.mkdir(parents=True, exist_ok=True)

        counts = [0] * len(DAMAGE_CLASSES)
        for rec in records:
            shutil.copy2(rec.image_path, out_images / rec.file_name)
            (out_labels / f"{Path(rec.file_name).stem}.txt").write_text("\n".join(rec.label_lines), encoding="utf-8")
            counts = [counts[i] + rec.class_counts[i] for i in range(len(DAMAGE_CLASSES))]
            manifest_rows.append(
                {
                    "split": split_name,
                    "kind": "positive",
                    "file_name": rec.file_name,
                    "source": "cardd",
                    "class_counts": json.dumps(rec.class_counts),
                }
            )

        summary["splits"][split_name] = {
            "positive_images": len(records),
            "positive_balance_mode": "full",
            "positive_reference_count": min(counts) if counts else 0,
            "positive_class_caps": {name: counts[i] for i, name in enumerate(DAMAGE_CLASSES)},
            "positive_class_counts": {name: counts[i] for i, name in enumerate(DAMAGE_CLASSES)},
            "positive_exact_balance": False,
            "negative_full_images": 0,
            "negative_crop_images": 0,
        }

    data_yaml = {
        "path": str(output_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {i: name for i, name in enumerate(DAMAGE_CLASSES)},
    }
    (output_dir / "data.yaml").write_text(
        yaml.safe_dump(data_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with (output_dir / "build_manifest.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["split", "kind", "file_name", "source", "class_counts"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    (output_dir / "build_stats.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
