"""Airflow DAG: Train Quality + View multitask model.

Trigger manually or schedule weekly. Steps:
1. Verify dataset exists
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
CONFIG_PATH = "ml/quality_view/configs/efficientnet_b0_multitask.yaml"


def check_dataset(**kwargs):
    from pathlib import Path
    d = Path(PROJECT_ROOT) / "data" / "quality_view" / "train"
    if not d.exists() or not list(d.iterdir()):
        raise FileNotFoundError(f"Training data not found at {d}. Run dataset_ingestion DAG first.")
    logger.info("Training data found at %s", d)


def validate_weights(**kwargs):
    from pathlib import Path
    w = Path(PROJECT_ROOT) / "ml" / "quality_view" / "weights" / "best_quality_view.pt"
    m = Path(PROJECT_ROOT) / "ml" / "quality_view" / "weights" / "metadata.json"
    if not w.exists():
        raise FileNotFoundError(f"Weights not found at {w}")
    if not m.exists():
        raise FileNotFoundError(f"Metadata not found at {m}")
    logger.info("Weights validated: %s (%.2f MB)", w, w.stat().st_size / 1e6)


def register_mlflow(**kwargs):
    try:
        import mlflow, json
        from pathlib import Path
        meta = json.loads((Path(PROJECT_ROOT) / "ml" / "quality_view" / "weights" / "metadata.json").read_text())
        mlflow.set_tracking_uri("http://mlflow:5000")
        with mlflow.start_run(run_name="quality_view_airflow") as run:
            mlflow.log_params(meta)
            mlflow.log_artifact(str(Path(PROJECT_ROOT) / "ml" / "quality_view" / "weights" / "best_quality_view.pt"))
        logger.info("Registered in MLflow: run_id=%s", run.info.run_id)
    except Exception as e:
        logger.warning("MLflow registration skipped: %s", e)


with DAG(
    dag_id="train_quality_view_model",
    description="Train EfficientNet-B0 quality+view multitask model",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ml", "training"],
) as dag:

    t_check = PythonOperator(task_id="check_dataset", python_callable=check_dataset)

    t_train = BashOperator(
        task_id="train_model",
        bash_command=f"cd {PROJECT_ROOT} && python -m ml.quality_view.training.train --config {CONFIG_PATH}",
    )

    t_validate = PythonOperator(task_id="validate_weights", python_callable=validate_weights)
    t_register = PythonOperator(task_id="register_mlflow", python_callable=register_mlflow)

    t_check >> t_train >> t_validate >> t_register
