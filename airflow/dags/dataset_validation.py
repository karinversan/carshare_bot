"""Airflow DAG: Validate offline dataset assets and manifests.

This DAG is intentionally lightweight for demo usage:
1. Check required dataset files exist.
2. Build a small validation report with sample counts.
3. Persist report to ml/evaluation/reports/dataset_validation_latest.json.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path("/app")
REPORT_PATH = PROJECT_ROOT / "ml" / "evaluation" / "reports" / "dataset_validation_latest.json"


def _ensure_path(path: Path, kind: str) -> None:
    if kind == "file" and not path.is_file():
        raise FileNotFoundError(f"Required file is missing: {path}")
    if kind == "dir" and not path.is_dir():
        raise FileNotFoundError(f"Required directory is missing: {path}")


def check_required_assets(**_: object) -> None:
    required = [
        (PROJECT_ROOT / "ml" / "data" / "cardd_yolo_seg" / "data.yaml", "file"),
        (PROJECT_ROOT / "ml" / "data" / "manifests" / "quality_dataset_manifest.csv", "file"),
        (PROJECT_ROOT / "ml" / "data" / "manifests" / "view_dataset_manifest.csv", "file"),
        (PROJECT_ROOT / "ml" / "data" / "cardd_yolo_seg" / "images", "dir"),
        (PROJECT_ROOT / "ml" / "data" / "cardd_yolo_seg" / "labels", "dir"),
    ]
    for path, kind in required:
        _ensure_path(path, kind)
        logger.info("OK: %s", path)


def build_validation_report(**_: object) -> None:
    image_root = PROJECT_ROOT / "ml" / "data" / "cardd_yolo_seg" / "images"
    label_root = PROJECT_ROOT / "ml" / "data" / "cardd_yolo_seg" / "labels"

    def _count_files(root: Path, ext: str) -> int:
        if not root.exists():
            return 0
        return sum(1 for path in root.rglob(f"*{ext}") if path.is_file())

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dataset_root": str(PROJECT_ROOT / "ml" / "data" / "cardd_yolo_seg"),
        "counts": {
            "images_jpg": _count_files(image_root, ".jpg"),
            "images_png": _count_files(image_root, ".png"),
            "labels_txt": _count_files(label_root, ".txt"),
        },
        "required_assets_ok": True,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Validation report saved: %s", REPORT_PATH)


with DAG(
    dag_id="dataset_validation",
    description="Validate dataset assets and write a compact report",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ml", "data", "validation"],
) as dag:
    t_check = PythonOperator(task_id="check_required_assets", python_callable=check_required_assets)
    t_report = PythonOperator(task_id="build_validation_report", python_callable=build_validation_report)
    t_check >> t_report

