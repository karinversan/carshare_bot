"""
Dataset download and preparation utilities.

Supported datasets:
- CarDD: Car Damage Detection dataset (main bootstrap)
- Custom viewpoint/quality dataset generation helpers

All datasets are downloaded to ml/data/ by default.
"""

import os
import shutil
import zipfile
import tarfile
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# CarDD Dataset
# ---------------------------------------------------------------------------
# CarDD is hosted on GitHub / Google Drive. Since direct programmatic access
# to Google Drive links can be flaky, we support multiple download strategies.
# The primary method uses gdown (pip install gdown) for Google Drive links.
# Fallback: manual download instructions are printed.
# ---------------------------------------------------------------------------

CARDD_INFO = {
    "name": "CarDD",
    "description": "Car Damage Detection dataset with segmentation masks",
    "url_segmentation": "https://drive.google.com/uc?id=1bEDq8g0VCC_kl8RkBsK4gE1MRGmjQW3v",
    "url_detection": "https://drive.google.com/uc?id=1OPrwk6gPbI3KZsoxIuhqMfJl2R0GCLO8",
    "license": "Research use only (CC BY-NC-SA 4.0)",
    "citation": "Wang et al., CarDD: A New Dataset for Vision-based Car Damage Detection, IEEE T-ITS 2023",
}


def download_cardd(dest: Path | None = None, subset: str = "segmentation") -> Path:
    """Download the CarDD dataset using gdown.

    Args:
        dest: Target directory. Defaults to ml/data/CarDD.
        subset: 'segmentation' or 'detection'.

    Returns:
        Path to the extracted dataset directory.
    """
    try:
        import gdown
    except ImportError:
        raise ImportError(
            "gdown is required to download CarDD. Install with: pip install gdown"
        )

    dest = dest or DATA_ROOT / "CarDD"
    dest.mkdir(parents=True, exist_ok=True)

    url = CARDD_INFO[f"url_{subset}"]
    zip_path = dest / f"CarDD_{subset}.zip"

    if (dest / subset).exists() and any((dest / subset).iterdir()):
        print(f"[CarDD] {subset} already exists at {dest / subset}, skipping download.")
        return dest / subset

    print(f"[CarDD] Downloading {subset} subset...")
    gdown.download(url, str(zip_path), quiet=False)

    print(f"[CarDD] Extracting to {dest}...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)

    zip_path.unlink()

    # CarDD extracts into a nested folder - flatten if needed
    extracted = _find_extracted_root(dest, subset)
    print(f"[CarDD] {subset} ready at {extracted}")
    return extracted


def _find_extracted_root(dest: Path, subset: str) -> Path:
    """Find the actual data root after extraction (handles nested dirs)."""
    # Check common patterns
    for candidate in [dest / subset, dest / "CarDD" / subset, dest / f"CarDD_{subset}"]:
        if candidate.exists():
            return candidate
    # Fallback: return dest itself
    return dest


# ---------------------------------------------------------------------------
# COCO-format to YOLO-format conversion
# ---------------------------------------------------------------------------

def coco_to_yolo_seg(coco_json_path: str, images_dir: str, output_dir: str, class_map: dict | None = None):
    """Convert COCO instance segmentation annotations to YOLO segmentation format.

    Args:
        coco_json_path: Path to COCO JSON annotations file.
        images_dir: Path to the images directory.
        output_dir: Output directory. Will create images/ and labels/ subdirs.
        class_map: Optional mapping from COCO category_id to YOLO class index.
    """
    import json

    with open(coco_json_path) as f:
        coco = json.load(f)

    out_path = Path(output_dir)
    (out_path / "images").mkdir(parents=True, exist_ok=True)
    (out_path / "labels").mkdir(parents=True, exist_ok=True)

    # Build lookups
    img_lookup = {img["id"]: img for img in coco["images"]}
    cat_lookup = {cat["id"]: cat["name"] for cat in coco["categories"]}

    if class_map is None:
        class_map = {cat["id"]: i for i, cat in enumerate(coco["categories"])}

    # Group annotations by image
    anns_by_img: dict[int, list] = {}
    for ann in coco["annotations"]:
        anns_by_img.setdefault(ann["image_id"], []).append(ann)

    converted = 0
    for img_id, img_info in img_lookup.items():
        filename = img_info["file_name"]
        w, h = img_info["width"], img_info["height"]

        # Copy image
        src_img = Path(images_dir) / filename
        if src_img.exists():
            shutil.copy2(src_img, out_path / "images" / filename)

        # Write label
        label_name = Path(filename).stem + ".txt"
        anns = anns_by_img.get(img_id, [])
        lines = []
        for ann in anns:
            cat_id = ann["category_id"]
            if cat_id not in class_map:
                continue
            cls_idx = class_map[cat_id]
            seg = ann.get("segmentation", [])
            if not seg or isinstance(seg, dict):
                continue  # Skip RLE for now
            for poly in seg:
                # Normalize coordinates
                norm_pts = []
                for i in range(0, len(poly), 2):
                    nx = poly[i] / w
                    ny = poly[i + 1] / h
                    norm_pts.extend([nx, ny])
                pts_str = " ".join(f"{v:.6f}" for v in norm_pts)
                lines.append(f"{cls_idx} {pts_str}")

        with open(out_path / "labels" / label_name, "w") as f:
            f.write("\n".join(lines))
        converted += 1

    print(f"[COCO->YOLO] Converted {converted} images to {output_dir}")
    return out_path


# ---------------------------------------------------------------------------
# Quality/View dataset helpers
# ---------------------------------------------------------------------------

def create_quality_view_splits(
    source_dir: str,
    output_dir: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    seed: int = 42,
):
    """Split images into train/val/test by car identity if available, else random.

    Expects source_dir to contain subdirectories per viewpoint class.
    """
    import random

    random.seed(seed)
    src = Path(source_dir)
    out = Path(output_dir)

    classes = sorted([d.name for d in src.iterdir() if d.is_dir()])
    if not classes:
        raise ValueError(f"No class subdirectories found in {source_dir}")

    for split in ["train", "val", "test"]:
        for cls in classes:
            (out / split / cls).mkdir(parents=True, exist_ok=True)

    for cls in classes:
        images = sorted((src / cls).glob("*.*"))
        random.shuffle(images)
        n = len(images)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        for i, img in enumerate(images):
            if i < n_train:
                split = "train"
            elif i < n_train + n_val:
                split = "val"
            else:
                split = "test"
            shutil.copy2(img, out / split / cls / img.name)

    print(f"[QualityView] Split {sum(len(list((src / c).glob('*.*'))) for c in classes)} images into train/val/test at {out}")
    return out
