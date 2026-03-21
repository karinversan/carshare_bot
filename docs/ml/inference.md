# Inference

The inference service supports three backends:

- `mock` for lightweight local bring-up
- `weights` for repo/local checkpoint loading
- `mlflow` for production-like registered model loading

Current runtime behavior:

- quality/view validation loads local EfficientNet checkpoints when available
- damage segmentation loads local YOLO segmentation checkpoints when available
- service startup preloads both models through `startup_load_models()`
- API-side fallback to `mock` is blocked when `REQUIRE_REAL_INFERENCE=true`

Recommended local setup for product verification:

1. Run `inference-service` as a long-lived Docker Compose service, not as an ad-hoc shell session.
2. Keep `INFERENCE_BACKEND=weights`.
3. Keep `REQUIRE_REAL_INFERENCE=true`.
4. Wait for `/health` before starting API/bot smoke checks.
