"""Model registry — loads trained models from local weights or MLflow.

Supports two backends:
  - "weights": loads directly from ml/<module>/weights/ directory
  - "mlflow": loads from MLflow model registry (champion alias)

Falls back to mock mode if models are not available.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # services/inference_service/app -> project root
QV_WEIGHTS_DIR = PROJECT_ROOT / "ml" / "quality_view" / "weights"
SEG_WEIGHTS_DIR = PROJECT_ROOT / "ml" / "damage_seg" / "weights"
QV_CONFIG_DIR = PROJECT_ROOT / "ml" / "quality_view" / "configs"
SEG_RUNS_DIR = PROJECT_ROOT / "ml" / "damage_seg" / "runs"

# ── Global singletons ────────────────────────────────────────────────
_qv_model = None
_qv_metadata: dict = {}
_seg_model = None
_seg_metadata: dict = {}
_device = None


def _get_device():
    """CUDA > MPS > CPU — cached."""
    global _device
    if _device is not None:
        return _device
    import torch
    if torch.cuda.is_available():
        _device = torch.device("cuda")
        logger.info("Inference device: CUDA (%s)", torch.cuda.get_device_name(0))
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        _device = torch.device("mps")
        logger.info("Inference device: MPS (Apple Silicon)")
    else:
        _device = torch.device("cpu")
        logger.info("Inference device: CPU")
    return _device


# ─── Quality / Viewpoint Model ──────────────────────────────────────


def _build_qv_model(num_vp: int = 4, num_qc: int = 4, backbone: str = "efficientnet_b0"):
    """Reconstruct the multitask model architecture (must match training code)."""
    import torch.nn as nn
    import timm

    class QualityViewMultitaskModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone = timm.create_model(backbone, pretrained=False, num_classes=0)
            feat_dim = self.backbone.num_features
            self.dropout = nn.Dropout(p=0.3)
            self.viewpoint_head = nn.Linear(feat_dim, num_vp)
            self.quality_head = nn.Linear(feat_dim, num_qc)

        def forward(self, x):
            features = self.dropout(self.backbone(x))
            return self.viewpoint_head(features), self.quality_head(features)

    return QualityViewMultitaskModel()


def _build_classifier(num_classes: int, backbone: str = "efficientnet_b0"):
    import timm

    return timm.create_model(backbone, pretrained=False, num_classes=num_classes)


def _extract_state_dict(checkpoint):
    state = checkpoint.get("model_state_dict") or checkpoint.get("state_dict") or checkpoint
    if isinstance(state, dict):
        return {str(key).removeprefix("module."): value for key, value in state.items()}
    return state


def load_quality_view_model(backend: str = "weights") -> bool:
    """Try to load quality/view model. Returns True if successful."""
    global _qv_model, _qv_metadata

    if backend == "mlflow":
        return _load_qv_from_mlflow()
    return _load_qv_from_weights()


def _load_qv_from_weights() -> bool:
    global _qv_model, _qv_metadata
    import torch

    quality_gate_path = QV_WEIGHTS_DIR / "quality_gate_best.pt"
    view_validation_path = QV_WEIGHTS_DIR / "view_validation_best.pt"
    if quality_gate_path.exists() and view_validation_path.exists():
        try:
            device = _get_device()
            quality_cfg = {}
            view_cfg = {}
            quality_cfg_path = QV_CONFIG_DIR / "quality_gate_config.json"
            view_cfg_path = QV_CONFIG_DIR / "view_validation_config.json"
            if quality_cfg_path.exists():
                quality_cfg = json.loads(quality_cfg_path.read_text())
            if view_cfg_path.exists():
                view_cfg = json.loads(view_cfg_path.read_text())

            quality_ckpt = torch.load(quality_gate_path, map_location=device, weights_only=False)
            view_ckpt = torch.load(view_validation_path, map_location=device, weights_only=False)

            quality_classes = quality_ckpt.get("classes") or ["accept", "reject"]
            view_classes = view_ckpt.get("classes") or [
                "front_valid",
                "rear_valid",
                "side_valid",
                "angled_invalid",
                "other_invalid",
            ]

            quality_model = _build_classifier(
                num_classes=len(quality_classes),
                backbone=quality_cfg.get("model_name", "efficientnet_b0"),
            )
            view_model = _build_classifier(
                num_classes=len(view_classes),
                backbone=view_cfg.get("model_name", "efficientnet_b0"),
            )

            quality_model.load_state_dict(_extract_state_dict(quality_ckpt))
            view_model.load_state_dict(_extract_state_dict(view_ckpt))
            quality_model = quality_model.to(device)
            view_model = view_model.to(device)
            quality_model.eval()
            view_model.eval()

            _qv_model = {
                "kind": "split",
                "quality_gate": quality_model,
                "view_validation": view_model,
            }
            _qv_metadata = {
                "kind": "split",
                "quality_classes": quality_classes,
                "viewpoint_classes": view_classes,
                "quality_image_size": quality_cfg.get("image_size", 224),
                "view_image_size": view_cfg.get("image_size", 224),
                "quality_reject_threshold": quality_ckpt.get("reject_threshold"),
                "view_threshold": view_ckpt.get("threshold"),
                "normalize_mean": [0.485, 0.456, 0.406],
                "normalize_std": [0.229, 0.224, 0.225],
            }
            logger.info("Split QV models loaded from %s and %s", quality_gate_path, view_validation_path)
            return True
        except Exception as e:
            logger.warning("Split QV load failed (%s) — trying multitask checkpoint", e)

    ckpt_path = QV_WEIGHTS_DIR / "best_quality_view.pt"
    meta_path = QV_WEIGHTS_DIR / "metadata.json"

    if not ckpt_path.exists():
        logger.warning("QV weights not found at %s — using mock", ckpt_path)
        return False

    try:
        device = _get_device()
        checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)

        # Load metadata (from checkpoint or separate file)
        if "config" in checkpoint:
            cfg = checkpoint["config"]
            backbone = cfg.get("model", {}).get("backbone", "efficientnet_b0")
        else:
            backbone = "efficientnet_b0"

        vp_classes = (
            checkpoint.get("viewpoint_classes")
            or checkpoint.get("view_classes")
            or ["front_left_3q", "front_right_3q", "rear_left_3q", "rear_right_3q"]
        )
        qc_classes = (
            checkpoint.get("quality_classes")
            or checkpoint.get("qc_classes")
            or ["good", "blur", "dark", "overexposed"]
        )

        model = _build_qv_model(
            num_vp=len(vp_classes),
            num_qc=len(qc_classes),
            backbone=backbone,
        )

        state = _extract_state_dict(checkpoint)
        model.load_state_dict(state)
        model = model.to(device)
        model.eval()

        _qv_model = model
        _qv_metadata = {
            "viewpoint_classes": vp_classes,
            "quality_classes": qc_classes,
            "image_size": checkpoint.get("config", {}).get("data", {}).get("image_size", 384),
            "normalize_mean": [0.485, 0.456, 0.406],
            "normalize_std": [0.229, 0.224, 0.225],
        }

        if meta_path.exists():
            _qv_metadata.update(json.loads(meta_path.read_text()))
            if "viewpoint_classes" not in _qv_metadata and "view_classes" in _qv_metadata:
                _qv_metadata["viewpoint_classes"] = _qv_metadata["view_classes"]

        logger.info(
            "QV model loaded from %s (backbone=%s, vp=%d, qc=%d)",
            ckpt_path, backbone, len(vp_classes), len(qc_classes),
        )
        return True
    except Exception as e:
        logger.error("Failed to load QV model: %s", e, exc_info=True)
        return False


def _load_qv_from_mlflow() -> bool:
    global _qv_model, _qv_metadata
    try:
        import mlflow
        from services.inference_service.app.core.config import settings
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        model_uri = f"models:/{settings.quality_view_model_name}@{settings.quality_view_model_alias}"
        _qv_model = mlflow.pytorch.load_model(model_uri, map_location=str(_get_device()))
        _qv_model.eval()
        _qv_metadata = {
            "viewpoint_classes": ["front_left_3q", "front_right_3q", "rear_left_3q", "rear_right_3q"],
            "quality_classes": ["good", "too_dark", "too_blurry", "overexposed"],
            "image_size": 384,
            "normalize_mean": [0.485, 0.456, 0.406],
            "normalize_std": [0.229, 0.224, 0.225],
        }
        logger.info("QV model loaded from MLflow: %s", model_uri)
        return True
    except Exception as e:
        logger.warning("MLflow QV load failed (%s) — falling back to weights", e)
        return _load_qv_from_weights()


def get_qv_model():
    """Return (model, metadata) or (None, {}) if unavailable."""
    return _qv_model, _qv_metadata


# ─── Damage Segmentation Model ──────────────────────────────────────


def load_damage_seg_model(backend: str = "weights") -> bool:
    """Try to load damage segmentation model. Returns True if successful."""
    global _seg_model, _seg_metadata

    if backend == "mlflow":
        return _load_seg_from_mlflow()
    return _load_seg_from_weights()


def _load_seg_from_weights() -> bool:
    global _seg_model, _seg_metadata
    from services.inference_service.app.core.config import settings

    configured_ckpt_path = Path(settings.damage_seg_weights_path).expanduser() if settings.damage_seg_weights_path else None
    configured_meta_path = Path(settings.damage_seg_metadata_path).expanduser() if settings.damage_seg_metadata_path else None

    candidates = []
    if configured_ckpt_path:
        candidates.append(configured_ckpt_path)
    else:
        best_direct = SEG_WEIGHTS_DIR / "best_damage_seg.pt"
        if best_direct.exists():
            candidates.append(best_direct)
        if SEG_RUNS_DIR.exists():
            run_candidates = sorted(
                SEG_RUNS_DIR.rglob("weights/best.pt"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            candidates.extend(run_candidates)
    ckpt_path = candidates[0] if candidates else SEG_WEIGHTS_DIR / "best_damage_seg.pt"
    meta_path = configured_meta_path or ckpt_path.with_name("metadata.json")
    if not meta_path.exists():
        meta_path = SEG_WEIGHTS_DIR / "metadata.json"

    if not ckpt_path.exists():
        logger.warning("Damage seg weights not found at %s — using mock", ckpt_path)
        return False

    try:
        from ultralytics import YOLO
        device = _get_device()

        model = YOLO(str(ckpt_path))
        _seg_model = model

        if meta_path.exists():
            _seg_metadata = json.loads(meta_path.read_text())
        else:
            names = getattr(model.model, "names", None)
            if isinstance(names, dict):
                damage_classes = [names[i] for i in sorted(names)]
            elif isinstance(names, list):
                damage_classes = names
            else:
                damage_classes = ["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"]
            _seg_metadata = {"damage_classes": damage_classes}

        if "damage_classes" in _seg_metadata:
            normalized = []
            for cls in _seg_metadata["damage_classes"]:
                if not isinstance(cls, str):
                    normalized.append(cls)
                    continue
                normalized.append(cls.replace(" ", "_"))
            _seg_metadata["damage_classes"] = normalized
        _seg_metadata.setdefault("weights_path", str(ckpt_path))

        logger.info("Damage seg model loaded from %s", ckpt_path)
        return True
    except Exception as e:
        logger.error("Failed to load damage seg model: %s", e, exc_info=True)
        return False


def _load_seg_from_mlflow() -> bool:
    global _seg_model, _seg_metadata
    try:
        import mlflow
        from services.inference_service.app.core.config import settings
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        model_uri = f"models:/{settings.damage_seg_model_name}@{settings.damage_seg_model_alias}"
        artifact_path = mlflow.artifacts.download_artifacts(model_uri)
        from ultralytics import YOLO
        # MLflow stores YOLO model as artifact; find .pt file
        from pathlib import Path
        pt_files = list(Path(artifact_path).rglob("*.pt"))
        if not pt_files:
            raise FileNotFoundError(f"No .pt found in MLflow artifact: {artifact_path}")
        _seg_model = YOLO(str(pt_files[0]))
        names = getattr(_seg_model.model, "names", None)
        if isinstance(names, dict):
            damage_classes = [names[i] for i in sorted(names)]
        elif isinstance(names, list):
            damage_classes = names
        else:
            damage_classes = ["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"]
        _seg_metadata = {"damage_classes": damage_classes}
        logger.info("Damage seg model loaded from MLflow: %s", model_uri)
        return True
    except Exception as e:
        logger.warning("MLflow seg load failed (%s) — falling back to weights", e)
        return _load_seg_from_weights()


def get_seg_model():
    """Return (model, metadata) or (None, {}) if unavailable."""
    return _seg_model, _seg_metadata


# ─── Startup ────────────────────────────────────────────────────────


def startup_load_models():
    """Called at service startup to preload models."""
    from services.inference_service.app.core.config import settings
    backend = settings.inference_backend  # "mock", "weights", or "mlflow"

    if backend == "mock":
        logger.info("Inference backend = mock — skipping model loading")
        return

    qv_ok = load_quality_view_model(backend)
    seg_ok = load_damage_seg_model(backend)

    logger.info(
        "Model loading complete: quality_view=%s, damage_seg=%s (backend=%s)",
        "OK" if qv_ok else "MOCK_FALLBACK",
        "OK" if seg_ok else "MOCK_FALLBACK",
        backend,
    )
