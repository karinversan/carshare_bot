"""Airflow DAG: Train YOLOv8s-seg damage segmentation model.

Trigger manually. Steps:
1. Verify YOLO dataset exists
2. Run training CLI
3. Validate weights output
4. (Optional) Register model in MLflow
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
PROJECT_ROOT = "/app"
CONFIG_PATH = "ml/damage_seg/configs/yolo_seg_v1.yaml"


def check_dataset(**kwargs):
    from pathlib import Path
    dy = Path(PROJECT_ROOT) / "ml" / "data" / "cardd_yolo_seg" / "data.yaml"
    if not dy.exists():
        raise FileNotFoundError(f"data.yaml not found at {dy}. Run dataset_ingestion DAG first.")
    logger.info("YOLO dataset config found at %s", dy)


def validate_weights(**kwargs):
    from pathlib import Path
    w = Path(PROJECT_ROOT) / "ml" / "damage_seg" / "weights" / "best_damage_seg.pt"
    m = Path(PROJECT_ROOT) / "ml" / "damage_seg" / "weights" / "metadata.json"
    if not w.exists():
        raise FileNotFoundError(f"Weights not found at {w}")
    if not m.exists():
        raise FileNotFoundError(f"Metadata not found at {m}")
    logger.info("Weights validated: %s (%.2f MB)", w, w.stat().st_size / 1e6)


def register_mlflow(**kwargs):
    try:
        import mlflow, json
        from pathlib import Path
        meta = json.loads((Path(PROJECT_ROOT) / "ml" / "damage_seg" / "weights" / "metadata.json").read_text())
        mlflow.set_tracking_uri("http://mlflow:5000")
        with mlflow.start_run(run_name="damage_seg_airflow") as run:
            for k, v in meta.get("metrics", {}).items():
                mlflow.log_metric(k.replace("/", "_"), v)
            mlflow.log_artifact(str(Path(PROJECT_ROOT) / "ml" / "damage_seg" / "weights" / "best_damage_seg.pt"))
        logger.info("Registered in MLflow: run_id=%s", run.info.run_id)
    except Exception as e:
        logger.warning("MLflow registration skipped: %s", e)


with DAG(
    dag_id="train_damage_seg_model",
    description="Train YOLOv8s-seg damage segmentation model",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ml", "training"],
) as dag:

    t_check = PythonOperator(task_id="check_dataset", python_callable=check_dataset)

    t_train = BashOperator(
        task_id="train_model",
        bash_command=f"cd {PROJECT_ROOT} && python -m ml.damage_seg.training.train_yolo --config {CONFIG_PATH}",
    )

    t_validate = PythonOperator(task_id="validate_weights", python_callable=validate_weights)
    t_register = PythonOperator(task_id="register_mlflow", python_callable=register_mlflow)

    t_check >> t_train >> t_validate >> t_register
