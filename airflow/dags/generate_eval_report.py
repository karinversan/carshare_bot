"""Airflow DAG: Generate compact markdown summary from latest model-quality JSON."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path("/app")
QUALITY_JSON = PROJECT_ROOT / "ml" / "evaluation" / "reports" / "model_quality_latest.json"
SUMMARY_MD = PROJECT_ROOT / "ml" / "evaluation" / "reports" / "model_quality_summary.md"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def generate_eval_report(**_: object) -> None:
    if not QUALITY_JSON.exists():
        raise FileNotFoundError(
            f"Missing {QUALITY_JSON}. Run evaluate_models DAG before generating summary."
        )

    payload = json.loads(QUALITY_JSON.read_text(encoding="utf-8"))
    q = payload.get("quality_gate") or {}
    v = payload.get("view_validation") or {}
    s = payload.get("damage_segmentation") or {}
    p = payload.get("paired_comparison") or {}

    lines = [
        "# Model Quality Summary",
        "",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        "",
        "## Quality Gate",
        f"- Accuracy: {_fmt_pct(q.get('accuracy'))}",
        f"- Macro F1: {_fmt_pct(q.get('macro_f1'))}",
        f"- Reject precision: {_fmt_pct(q.get('reject_precision'))}",
        f"- Reject recall: {_fmt_pct(q.get('reject_recall'))}",
        "",
        "## View Validation",
        f"- Accuracy: {_fmt_pct(v.get('accuracy'))}",
        f"- Macro F1: {_fmt_pct(v.get('macro_f1'))}",
        "",
        "## Damage Segmentation",
        f"- mAP50 (mask): {_fmt_pct(s.get('map50_m'))}",
        f"- mAP50-95 (mask): {_fmt_pct(s.get('map50_95_m'))}",
        f"- Precision (mask): {_fmt_pct(s.get('precision_m'))}",
        f"- Recall (mask): {_fmt_pct(s.get('recall_m'))}",
        "",
        "## Paired Comparison",
        f"- Post damages: {p.get('post_damage_count', 'n/a')}",
        f"- Matched existing: {p.get('matched_count', 'n/a')}",
        f"- New confirmed: {p.get('new_confirmed_count', 'n/a')}",
        f"- Possible new: {p.get('possible_new_count', 'n/a')}",
        "",
    ]

    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Generated evaluation summary: %s", SUMMARY_MD)


with DAG(
    dag_id="generate_eval_report",
    description="Generate markdown summary from latest evaluation report",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ml", "evaluation", "report"],
) as dag:
    PythonOperator(task_id="generate_eval_report", python_callable=generate_eval_report)

