#!/usr/bin/env python3
"""CLI: Train YOLOv8s-seg damage segmentation model.

Usage:
    python -m ml.damage_seg.training.train_yolo \
        --config ml/damage_seg/configs/yolo_seg_v1.yaml
"""
import argparse, json, logging, shutil, sys
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from ml.utils.device import get_device, seed_everything
from ml.damage_seg.checkpointing import MetricCheckpointSync


def train(cfg: dict):
    seed_everything(cfg.get("seed", 42))
    device = get_device()
    device_str = str(device)

    # Ultralytics uses device string
    if device_str == "cuda":
        device_str = "0"

    data_yaml = ROOT / "ml" / "data" / "cardd_yolo_seg" / "data.yaml"
    if not data_yaml.exists():
        logger.error("data.yaml not found at %s — run notebook 01 first.", data_yaml)
        sys.exit(1)

    from ultralytics import YOLO

    pretrained_ckpt = cfg["model"].get("pretrained_checkpoint", "yolov8s-seg.pt")
    model = YOLO(pretrained_ckpt)

    epochs = cfg["trainer"]["epochs"]
    patience = cfg["trainer"].get("patience", 10)
    imgsz = cfg["data"]["image_size"]
    batch = cfg["data"]["batch_size"]

    # Reduce batch for non-CUDA devices
    if device_str in ("cpu", "mps"):
        batch = min(batch, 4)
        logger.info("Reduced batch size to %d for device=%s", batch, device_str)

    best_metric = cfg.get("trainer", {}).get("best_metric", "metrics/mAP50(M)")
    runs_dir = ROOT / "ml" / "damage_seg" / "runs"
    weights_dir = ROOT / "ml" / "damage_seg" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    best_dst = weights_dir / "best_damage_seg.pt"
    best_meta = weights_dir / "best_damage_seg_metrics.json"

    metric_sync = MetricCheckpointSync(metric_name=best_metric, target_path=best_dst, metadata_path=best_meta)
    model.add_callback("on_fit_epoch_end", metric_sync)

    try:
        results = model.train(
            data=str(data_yaml),
            epochs=epochs,
            patience=patience,
            imgsz=imgsz,
            batch=batch,
            device=device_str,
            project=str(runs_dir),
            name=cfg.get("experiment_name", "yolo_seg_v1"),
            exist_ok=True,
            verbose=True,
        )
    except RuntimeError as e:
        if "MPS" in str(e) or "mps" in str(e):
            logger.warning("MPS failed, falling back to CPU: %s", e)
            results = model.train(
                data=str(data_yaml),
                epochs=epochs,
                patience=patience,
                imgsz=imgsz,
                batch=2,
                device="cpu",
                project=str(runs_dir),
                name=cfg.get("experiment_name", "yolo_seg_v1"),
                exist_ok=True,
            )
        else:
            raise

    # Fallback copy if callback did not run or training ended before any metric improvement.
    best_src = Path(results.save_dir) / "weights" / "best.pt"
    if not best_dst.exists() and best_src.exists():
        shutil.copy2(best_src, best_dst)
        logger.info("Copied best.pt → %s", best_dst)
    elif not best_src.exists():
        logger.warning("best.pt not found at %s", best_src)

    # Save metadata
    metrics = {}
    if hasattr(results, "results_dict"):
        metrics = {k: float(v) for k, v in results.results_dict.items() if isinstance(v, (int, float))}

    metadata = {
        "model": pretrained_ckpt,
        "epochs": epochs,
        "imgsz": imgsz,
        "device": device_str,
        "metrics": metrics,
        "best_metric": best_metric,
        "best_metric_value": None if metric_sync.best_value == float("-inf") else metric_sync.best_value,
    }
    (weights_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    # Optional MLflow registration
    try:
        mlflow_model_name = cfg.get("registry", {}).get("mlflow_model_name")
        if mlflow_model_name and best_dst.exists():
            import mlflow
            mlflow.set_tracking_uri(str(ROOT / "mlruns"))
            with mlflow.start_run(run_name=cfg.get("experiment_name", "yolo_seg")) as run:
                mlflow.log_params({"epochs": epochs, "imgsz": imgsz, "batch": batch})
                for k, v in metrics.items():
                    mlflow.log_metric(k.replace("/", "_"), v)
                mlflow.log_artifact(str(best_dst))
            logger.info("Registered in MLflow as %s", mlflow_model_name)
    except Exception as e:
        logger.info("MLflow registration skipped: %s", e)

    logger.info("Training complete. Weights → %s", best_dst)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    cfg = yaml.safe_load(Path(p.parse_args().config).read_text())
    train(cfg)

if __name__ == "__main__":
    main()
