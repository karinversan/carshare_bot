"""Airflow DAG: Dataset ingestion — download and convert CarDD dataset.

Runs on-demand (manual trigger). Steps:
1. Download CarDD dataset via gdown
2. Convert COCO annotations to YOLO segmentation format
3. Generate quality/view training splits (synthetic degradations)
4. Validate output
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = "/app"  # Container path


def download_cardd(**kwargs):
    """Download CarDD dataset via gdown."""
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from ml.utils.datasets import download_cardd
    from pathlib import Path

    output_dir = Path(PROJECT_ROOT) / "data" / "cardd_raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    download_cardd(output_dir)
    logger.info("CarDD downloaded to %s", output_dir)


def convert_coco_to_yolo(**kwargs):
    """Convert COCO annotations to YOLO segmentation format."""
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from ml.utils.datasets import coco_to_yolo_seg
    from pathlib import Path

    raw_dir = Path(PROJECT_ROOT) / "data" / "cardd_raw"
    yolo_dir = Path(PROJECT_ROOT) / "data" / "cardd_yolo"
    yolo_dir.mkdir(parents=True, exist_ok=True)

    for split in ["train", "val", "test"]:
        images_dir = raw_dir / split / "images"
        annotations = raw_dir / split / "annotations.json"
        if not annotations.exists():
            # Try alternative path
            annotations = raw_dir / split / "COCO_annotations.json"
        if annotations.exists() and images_dir.exists():
            coco_to_yolo_seg(str(annotations), str(images_dir), str(yolo_dir / split))
            logger.info("Converted %s split", split)

    # Create data.yaml
    data_yaml = yolo_dir / "data.yaml"
    data_yaml.write_text(
        f"path: {yolo_dir}\n"
        f"train: train/images\n"
        f"val: val/images\n"
        f"test: test/images\n"
        f"names:\n  0: scratch\n  1: dent\n  2: crack\n  3: broken_part\n"
    )
    logger.info("data.yaml created at %s", data_yaml)


def create_quality_view_splits(**kwargs):
    """Generate quality/view training data with synthetic degradations."""
    import sys
    sys.path.insert(0, PROJECT_ROOT)
    from ml.utils.datasets import create_quality_view_splits
    from pathlib import Path

    raw_dir = Path(PROJECT_ROOT) / "data" / "cardd_raw"
    out_dir = Path(PROJECT_ROOT) / "data" / "quality_view"
    out_dir.mkdir(parents=True, exist_ok=True)
    create_quality_view_splits(raw_dir, out_dir)
    logger.info("Quality/view splits → %s", out_dir)


def validate_output(**kwargs):
    """Quick validation that expected directories/files exist."""
    from pathlib import Path

    checks = [
        Path(PROJECT_ROOT) / "data" / "cardd_yolo" / "data.yaml",
        Path(PROJECT_ROOT) / "data" / "quality_view" / "train",
    ]
    for p in checks:
        if not p.exists():
            raise FileNotFoundError(f"Expected output not found: {p}")
        logger.info("OK: %s", p)
    logger.info("Dataset ingestion validation passed")


with DAG(
    dag_id="dataset_ingestion",
    description="Download and process CarDD dataset for training",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ml", "data"],
) as dag:

    t_download = PythonOperator(task_id="download_cardd", python_callable=download_cardd)
    t_convert = PythonOperator(task_id="convert_coco_to_yolo", python_callable=convert_coco_to_yolo)
    t_qv_splits = PythonOperator(task_id="create_quality_view_splits", python_callable=create_quality_view_splits)
    t_validate = PythonOperator(task_id="validate_output", python_callable=validate_output)

    t_download >> [t_convert, t_qv_splits] >> t_validate
