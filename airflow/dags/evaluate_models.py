"""Airflow DAG: Run offline model evaluation and build a unified report.

Flow:
1. Run paired diff-engine evaluation.
2. Aggregate quality/view + segmentation + paired metrics into one JSON report.
3. Validate report presence for downstream bot/admin usage.
"""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path("/app")
PAIRED_CFG = "ml/evaluation/paired_eval/configs/default.yaml"
REPORT_PATH = PROJECT_ROOT / "ml" / "evaluation" / "reports" / "model_quality_latest.json"


def validate_report(**_: object) -> None:
    if not REPORT_PATH.exists():
        raise FileNotFoundError(f"Unified evaluation report not found: {REPORT_PATH}")
    logger.info("Unified evaluation report is ready: %s", REPORT_PATH)


with DAG(
    dag_id="evaluate_models",
    description="Run paired evaluation and generate unified model quality report",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ml", "evaluation"],
) as dag:
    t_paired_eval = BashOperator(
        task_id="run_paired_eval",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            f"python -m ml.evaluation.paired_eval.run_paired_eval --config {PAIRED_CFG}"
        ),
    )
    t_build_unified_report = BashOperator(
        task_id="build_model_quality_report",
        bash_command=(
            f"cd {PROJECT_ROOT} && "
            "python -m ml.evaluation.build_model_quality_report --refresh-paired"
        ),
    )
    t_validate = PythonOperator(task_id="validate_report", python_callable=validate_report)

    t_paired_eval >> t_build_unified_report >> t_validate

