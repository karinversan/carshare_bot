"""Airflow DAG: Register best available model artifacts in MLflow.

This DAG is demo-oriented and safe:
- it skips missing artifacts
- it writes a local registration report even if MLflow is unavailable
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
REPORT_PATH = PROJECT_ROOT / "ml" / "evaluation" / "reports" / "mlflow_registration_latest.json"


def _artifact_candidates() -> dict[str, Path]:
    return {
        "quality_view": PROJECT_ROOT / "ml" / "quality_view" / "weights" / "best_quality_view.pt",
        "damage_seg": PROJECT_ROOT / "ml" / "damage_seg" / "weights" / "best_damage_seg.pt",
    }


def register_best_model(**_: object) -> None:
    artifacts = _artifact_candidates()
    report: dict[str, object] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "tracking_uri": "http://mlflow:5000",
        "models": {},
        "notes": [],
    }

    for name, path in artifacts.items():
        report["models"][name] = {
            "artifact_path": str(path),
            "exists": path.exists(),
            "registered": False,
            "run_id": None,
            "error": None,
        }

    try:
        import mlflow  # type: ignore

        mlflow.set_tracking_uri("http://mlflow:5000")

        for name, path in artifacts.items():
            model_info = report["models"][name]
            if not path.exists():
                continue

            with mlflow.start_run(run_name=f"{name}_register_airflow") as run:
                mlflow.log_artifact(str(path))
                model_info["registered"] = True
                model_info["run_id"] = run.info.run_id
                logger.info("Registered artifact for %s (run_id=%s)", name, run.info.run_id)
    except Exception as exc:  # pragma: no cover
        msg = f"MLflow registration skipped: {exc}"
        logger.warning(msg)
        report["notes"].append(msg)
        for name in artifacts:
            if report["models"][name]["exists"]:
                report["models"][name]["error"] = str(exc)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Registration report saved: %s", REPORT_PATH)


with DAG(
    dag_id="register_best_model",
    description="Register current best model artifacts to MLflow (demo-safe)",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ml", "registry", "mlflow"],
) as dag:
    PythonOperator(task_id="register_best_model", python_callable=register_best_model)

