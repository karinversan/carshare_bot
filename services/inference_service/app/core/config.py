from importlib.util import find_spec
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "mock" — heuristic/random stubs (no GPU needed)
    # "weights" — load from ml/<module>/weights/ (requires torch, timm, ultralytics)
    # "mlflow" — load from MLflow model registry
    inference_backend: str = "mock"

    # MLflow settings (used when inference_backend == "mlflow")
    mlflow_tracking_uri: str = "http://localhost:5000"
    quality_view_model_name: str = "quality_view"
    quality_view_model_alias: str = "champion"
    damage_seg_model_name: str = "damage_seg"
    damage_seg_model_alias: str = "champion"
    damage_seg_weights_path: str | None = None
    damage_seg_metadata_path: str | None = None
    damage_seg_inference_imgsz: int = 640

    # Confidence thresholds
    quality_view_rejection_confidence: float = 0.6
    quality_view_disable_viewpoint_check: bool = False
    damage_seg_confidence_threshold: float = 0.25
    damage_seg_post_filter_confidence: float = 0.45
    damage_seg_min_area_norm: float = 0.003
    damage_seg_max_area_norm: float = 0.35
    viewpoint_mismatch_threshold: float = 0.5  # reject if predicted view != expected with low confidence

    @model_validator(mode="after")
    def _prefer_weights_when_checkpoint_configured(self):
        has_torch = find_spec("torch") is not None
        has_ultralytics = find_spec("ultralytics") is not None
        deps_ready = has_torch and has_ultralytics

        project_root = Path(__file__).resolve().parents[4]
        damage_weights_dir = project_root / "ml" / "damage_seg" / "weights"
        fallback_damage_weights = [
            damage_weights_dir / "best_damage_seg.pt",
            damage_weights_dir / "best_damage_seg_full_baseline_mps.pt",
        ]
        configured_weight_path = (self.damage_seg_weights_path or "").strip()
        configured_weight_file = Path(configured_weight_path).expanduser() if configured_weight_path else None

        resolved_weight_file: Path | None = None
        if configured_weight_file:
            if configured_weight_file.exists():
                resolved_weight_file = configured_weight_file
            else:
                # Support Docker runtime where env may point to host path.
                # If file with same basename is present in project weights dir, use it.
                local_name_candidates = [
                    damage_weights_dir / configured_weight_file.name,
                    damage_weights_dir / "external" / configured_weight_file.name,
                ]
                for candidate in local_name_candidates:
                    if candidate.exists():
                        resolved_weight_file = candidate
                        break

        if resolved_weight_file is None:
            for candidate in fallback_damage_weights:
                if candidate.exists():
                    resolved_weight_file = candidate
                    break

        if resolved_weight_file is not None:
            self.damage_seg_weights_path = str(resolved_weight_file)

        weight_file_exists = resolved_weight_file is not None

        # "weights" mode should not crash service startup on slim/docker envs
        # where torch stack is intentionally absent.
        if self.inference_backend == "weights":
            if not deps_ready:
                self.inference_backend = "mock"
            elif configured_weight_path and not weight_file_exists:
                self.inference_backend = "mock"
            return self

        # In some envs duplicate INFERENCE_BACKEND vars leave backend="mock".
        # If deps and a valid checkpoint are present, prefer real weights.
        if self.inference_backend == "mock" and deps_ready and weight_file_exists:
            self.inference_backend = "weights"
        return self


settings = Settings()
