from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
LATEST_REPORT_PATH = ROOT / "ml" / "evaluation" / "reports" / "model_quality_latest.json"


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_float(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def load_latest_quality_report() -> dict[str, Any] | None:
    if not LATEST_REPORT_PATH.exists():
        return None
    try:
        return json.loads(LATEST_REPORT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def format_quality_report_message(report: dict[str, Any]) -> str:
    generated_at = report.get("generated_at")
    generated_human = generated_at or "n/a"
    if isinstance(generated_at, str):
        try:
            generated_human = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            generated_human = generated_at

    lines = [
        "<b>Качество моделей</b>",
        f"Обновлено: {generated_human}",
        "",
    ]

    quality_gate = report.get("quality_gate")
    if quality_gate:
        lines.extend(
            [
                "<b>1) Quality Gate</b>",
                f"• Accuracy: {_fmt_pct(quality_gate.get('accuracy'))}",
                f"• Macro F1: {_fmt_pct(quality_gate.get('macro_f1'))}",
                f"• Reject precision: {_fmt_pct(quality_gate.get('reject_precision'))}",
                f"• Reject recall: {_fmt_pct(quality_gate.get('reject_recall'))}",
                "",
            ]
        )

    view_validation = report.get("view_validation")
    if view_validation:
        classes = view_validation.get("classes", {})
        lines.extend(
            [
                "<b>2) View Validation</b>",
                f"• Accuracy: {_fmt_pct(view_validation.get('accuracy'))}",
                f"• Macro F1: {_fmt_pct(view_validation.get('macro_f1'))}",
                f"• F1 front_valid: {_fmt_pct(classes.get('front_valid_f1'))}",
                f"• F1 side_valid: {_fmt_pct(classes.get('side_valid_f1'))}",
                f"• F1 rear_valid: {_fmt_pct(classes.get('rear_valid_f1'))}",
                "",
            ]
        )

    damage_seg = report.get("damage_segmentation")
    if damage_seg:
        lines.extend(
            [
                "<b>3) Damage Segmentation</b>",
                f"• mAP50 (mask): {_fmt_float(damage_seg.get('map50_m'))}",
                f"• mAP50-95 (mask): {_fmt_float(damage_seg.get('map50_95_m'))}",
                f"• Precision (mask): {_fmt_float(damage_seg.get('precision_m'))}",
                f"• Recall (mask): {_fmt_float(damage_seg.get('recall_m'))}",
                "",
            ]
        )

    paired = report.get("paired_comparison")
    if paired:
        lines.extend(
            [
                "<b>4) Diff Engine (paired eval)</b>",
                f"• Matched existing: {paired.get('matched_count', 'n/a')}",
                f"• New confirmed: {paired.get('new_confirmed_count', 'n/a')}",
                f"• Possible new: {paired.get('possible_new_count', 'n/a')}",
                f"• New rate: {_fmt_pct(paired.get('new_confirmed_rate'))}",
                "",
            ]
        )

    notes = report.get("notes") or []
    sanitized_notes: list[str] = []
    for note in notes:
        text = str(note)
        lowered = text.lower()
        if "checkpoint" in lowered or "metrics file" in lowered:
            sanitized_notes.append("Использованы служебные артефакты оценки сегментации (детали пути скрыты).")
            continue
        sanitized_notes.append(text)
    if notes:
        lines.append("<b>Примечания</b>")
        lines.extend(f"• {note}" for note in sanitized_notes[:5])
        lines.append("")

    lines.append("Нажмите «Обновить оценку», чтобы пересобрать отчёт и сохранить новый снимок.")
    return "\n".join(lines).strip()


async def refresh_quality_report(timeout_sec: int = 180) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "ml.evaluation.build_model_quality_report", "--refresh-paired"]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return False, "Оценка не завершилась вовремя (таймаут)."

    if process.returncode != 0:
        err_text = (stderr.decode("utf-8", errors="ignore") or stdout.decode("utf-8", errors="ignore")).strip()
        return False, f"Не удалось обновить оценку: {err_text or 'unknown error'}"

    report = load_latest_quality_report()
    if not report:
        return False, "Оценка завершилась, но файл отчёта не найден."
    return True, format_quality_report_message(report)
