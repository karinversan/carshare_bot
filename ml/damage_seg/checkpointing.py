"""Checkpoint helpers for damage segmentation training."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


class MetricCheckpointSync:
    """Copy the latest checkpoint to a stable path when a metric improves."""

    def __init__(self, metric_name: str, target_path: str | Path, metadata_path: str | Path | None = None):
        self.metric_name = metric_name
        self.target_path = Path(target_path)
        self.metadata_path = Path(metadata_path) if metadata_path else self.target_path.with_name(
            f"{self.target_path.stem}_metrics.json"
        )
        self.best_value = float("-inf")
        self.best_epoch = 0

    def __call__(self, trainer: Any) -> None:
        metrics = getattr(trainer, "metrics", {}) or {}
        metric_value = metrics.get(self.metric_name)
        if metric_value is None:
            return

        metric_value = float(metric_value)
        if metric_value <= self.best_value:
            return

        last_path = Path(getattr(trainer, "last", ""))
        if not last_path.exists():
            return

        self.best_value = metric_value
        self.best_epoch = int(getattr(trainer, "epoch", -1)) + 1
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(last_path, self.target_path)

        payload = {
            "metric_name": self.metric_name,
            "metric_value": metric_value,
            "epoch": self.best_epoch,
            "source_checkpoint": str(last_path),
            "trainer_best_fitness": float(getattr(trainer, "best_fitness", 0.0) or 0.0),
            "trainer_metrics": {k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))},
        }
        self.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def metrics_to_dict(metrics: Any) -> dict[str, float]:
    """Extract scalar metrics from Ultralytics results objects."""
    results_dict = getattr(metrics, "results_dict", None)
    if isinstance(results_dict, dict):
        return {k: float(v) for k, v in results_dict.items() if isinstance(v, (int, float))}
    return {}

