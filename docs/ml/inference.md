# Inference

The inference service supports two backends:
- `mock` for immediate local demo bring-up
- `mlflow` for production-like registered model loading

Current implementation:
- quality/view endpoint computes blur and brightness heuristics
- damage segmentation endpoint emits deterministic mock polygons

Replace those endpoints with real model adapters after training.
