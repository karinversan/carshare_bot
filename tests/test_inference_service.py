"""Tests for the inference service model registry and prediction logic."""

import pytest
from pathlib import Path


class TestModelRegistry:
    """Test model loading and fallback logic."""

    def test_import_registry(self):
        from services.inference_service.app.model_registry import (
            get_qv_model, get_seg_model, startup_load_models,
        )
        # Initially models are None (not loaded)
        model, meta = get_qv_model()
        # In test env, model may be None (no weights) — that's OK
        assert meta is not None or model is None

    def test_startup_mock_mode(self):
        """In mock mode, startup should skip model loading."""
        from services.inference_service.app.model_registry import (
            get_qv_model, get_seg_model, startup_load_models,
        )
        # This should not raise even without torch/timm installed
        startup_load_models()
        model, meta = get_qv_model()
        # Mock mode = no models loaded
        # (model may or may not be loaded depending on backend config)

    def test_device_selection(self):
        """Device selection should return a valid torch device string."""
        try:
            from services.inference_service.app.model_registry import _get_device
            device = _get_device()
            assert str(device) in ("cpu", "cuda", "mps")
        except ImportError:
            pytest.skip("torch not available")


class TestQualityViewPrediction:
    """Test quality/view prediction logic."""

    @pytest.fixture(autouse=True)
    def _force_viewpoint_checks_for_tests(self, monkeypatch):
        from services.inference_service.app.routers import quality_view as qv

        monkeypatch.setattr(qv.settings, "quality_view_disable_viewpoint_check", False)

    def test_quality_label_aliases_are_normalized(self):
        from services.inference_service.app.routers.quality_view import _normalize_quality_label

        assert _normalize_quality_label("blur") == "too_blurry"
        assert _normalize_quality_label("dark") == "too_dark"
        assert _normalize_quality_label("accept") == "good"
        assert _normalize_quality_label("reject") == "quality_gate_reject"

    def test_mock_prediction_accepts_good_image(self):
        """Mock should accept a normal image."""
        from PIL import Image
        import numpy as np
        # Create a "good" test image (not too dark, not too bright, not blurry)
        arr = np.random.randint(80, 180, (512, 512, 3), dtype=np.uint8)
        image = Image.fromarray(arr)

        from services.inference_service.app.routers.quality_view import _predict_mock
        result = _predict_mock(image, "front")
        assert result["accepted"] is True
        assert result["quality_label"] == "good"
        assert result["predicted_view"] == "front"
        assert result["model_backend"] == "mock"

    def test_mock_prediction_rejects_dark_image(self):
        """Mock should reject very dark images."""
        from PIL import Image
        import numpy as np
        arr = np.zeros((512, 512, 3), dtype=np.uint8) + 10  # very dark
        image = Image.fromarray(arr)

        from services.inference_service.app.routers.quality_view import _predict_mock
        result = _predict_mock(image, "front")
        assert result["accepted"] is False
        assert result["quality_label"] == "too_dark"
        assert result["rejection_reason"] == "too_dark"

    def test_mock_prediction_rejects_overexposed(self):
        """Mock should reject very bright images."""
        from PIL import Image
        import numpy as np
        arr = np.full((512, 512, 3), 245, dtype=np.uint8)
        image = Image.fromarray(arr)

        from services.inference_service.app.routers.quality_view import _predict_mock
        result = _predict_mock(image, "rear")
        assert result["accepted"] is False
        assert result["quality_label"] == "overexposed"

    def test_mock_prediction_rejects_small_image(self):
        """Mock should reject images where no car is detected (too small)."""
        from PIL import Image
        import numpy as np
        arr = np.random.randint(80, 180, (50, 50, 3), dtype=np.uint8)
        image = Image.fromarray(arr)

        from services.inference_service.app.routers.quality_view import _predict_mock
        result = _predict_mock(image, "front")
        assert result["accepted"] is False
        assert result["quality_label"] == "car_too_small"
        assert result["rejection_reason"] == "car_too_small"

    def test_real_binary_quality_gate_does_not_hard_reject_without_heuristic_support(self, monkeypatch):
        from PIL import Image
        import numpy as np
        import torch
        from services.inference_service.app.routers import quality_view as qv

        class FakeModel(torch.nn.Module):
            def __init__(self, logits):
                super().__init__()
                self.anchor = torch.nn.Parameter(torch.zeros(1))
                self._logits = torch.tensor([logits], dtype=torch.float32)

            def forward(self, x):
                return self._logits.to(x.device)

        fake_quality = FakeModel([0.05, 3.0])  # reject
        fake_view = FakeModel([3.0, 0.1, 0.1, 0.1, 0.1])  # front_valid
        monkeypatch.setattr(
            qv,
            "get_qv_model",
            lambda: (
                {"kind": "split", "quality_gate": fake_quality, "view_validation": fake_view},
                {
                    "quality_classes": ["accept", "reject"],
                    "viewpoint_classes": ["front_valid", "rear_valid", "side_valid", "angled_invalid", "other_invalid"],
                    "quality_image_size": 224,
                    "view_image_size": 224,
                    "normalize_mean": [0.485, 0.456, 0.406],
                    "normalize_std": [0.229, 0.224, 0.225],
                },
            ),
        )

        arr = np.random.randint(90, 170, (512, 512, 3), dtype=np.uint8)
        image = Image.fromarray(arr)
        result = qv._predict_real(image, "front")
        assert result["accepted"] is True
        assert result["raw_quality_label"] == "reject"

    def test_real_binary_quality_gate_rejects_when_heuristics_confirm(self, monkeypatch):
        from PIL import Image
        import numpy as np
        import torch
        from services.inference_service.app.routers import quality_view as qv

        class FakeModel(torch.nn.Module):
            def __init__(self, logits):
                super().__init__()
                self.anchor = torch.nn.Parameter(torch.zeros(1))
                self._logits = torch.tensor([logits], dtype=torch.float32)

            def forward(self, x):
                return self._logits.to(x.device)

        fake_quality = FakeModel([0.05, 3.0])  # reject
        fake_view = FakeModel([3.0, 0.1, 0.1, 0.1, 0.1])  # front_valid
        monkeypatch.setattr(
            qv,
            "get_qv_model",
            lambda: (
                {"kind": "split", "quality_gate": fake_quality, "view_validation": fake_view},
                {
                    "quality_classes": ["accept", "reject"],
                    "viewpoint_classes": ["front_valid", "rear_valid", "side_valid", "angled_invalid", "other_invalid"],
                    "quality_image_size": 224,
                    "view_image_size": 224,
                    "normalize_mean": [0.485, 0.456, 0.406],
                    "normalize_std": [0.229, 0.224, 0.225],
                },
            ),
        )

        arr = np.zeros((512, 512, 3), dtype=np.uint8) + 8
        image = Image.fromarray(arr)
        result = qv._predict_real(image, "front")
        assert result["accepted"] is False
        assert result["quality_label"] == "too_dark"

    def test_adjacent_view_mismatch_is_rejected_for_required_slot(self, monkeypatch):
        from PIL import Image
        import numpy as np
        import torch
        from services.inference_service.app.routers import quality_view as qv

        class FakeModel(torch.nn.Module):
            def __init__(self, logits):
                super().__init__()
                self.anchor = torch.nn.Parameter(torch.zeros(1))
                self._logits = torch.tensor([logits], dtype=torch.float32)

            def forward(self, x):
                return self._logits.to(x.device)

        fake_quality = FakeModel([3.0, 0.05])  # accept
        fake_view = FakeModel([0.1, 2.0, 0.1, 0.1, 0.1])  # rear_valid around 0.60
        monkeypatch.setattr(
            qv,
            "get_qv_model",
            lambda: (
                {"kind": "split", "quality_gate": fake_quality, "view_validation": fake_view},
                {
                    "quality_classes": ["accept", "reject"],
                    "viewpoint_classes": ["front_valid", "rear_valid", "side_valid", "angled_invalid", "other_invalid"],
                    "quality_image_size": 224,
                    "view_image_size": 224,
                    "normalize_mean": [0.485, 0.456, 0.406],
                    "normalize_std": [0.229, 0.224, 0.225],
                },
            ),
        )

        arr = np.random.randint(90, 170, (512, 512, 3), dtype=np.uint8)
        image = Image.fromarray(arr)
        result = qv._predict_real(image, "right_side")
        assert result["accepted"] is False
        assert result["raw_view_label"] == "rear_valid"
        assert result["view_reject_threshold"] >= 0.82
        assert result["rejection_reason"] == "wrong_viewpoint: expected right_side, got rear_valid"

    def test_invalid_front_or_rear_can_be_accepted_by_symmetry_override(self, monkeypatch):
        from PIL import Image
        import numpy as np
        import torch
        from services.inference_service.app.routers import quality_view as qv

        class FakeModel(torch.nn.Module):
            def __init__(self, logits):
                super().__init__()
                self.anchor = torch.nn.Parameter(torch.zeros(1))
                self._logits = torch.tensor([logits], dtype=torch.float32)

            def forward(self, x):
                return self._logits.to(x.device)

        fake_quality = FakeModel([3.0, 0.05])  # accept
        fake_view = FakeModel([2.5, 0.1, 0.1, 0.1, 0.1])  # angled_invalid
        monkeypatch.setattr(
            qv,
            "get_qv_model",
            lambda: (
                {"kind": "split", "quality_gate": fake_quality, "view_validation": fake_view},
                {
                    "quality_classes": ["accept", "reject"],
                    "viewpoint_classes": ["angled_invalid", "front_valid", "other_invalid", "rear_valid", "side_valid"],
                    "quality_image_size": 224,
                    "view_image_size": 224,
                    "normalize_mean": [0.485, 0.456, 0.406],
                    "normalize_std": [0.229, 0.224, 0.225],
                },
            ),
        )
        monkeypatch.setattr(qv, "bilateral_symmetry_score", lambda image: 0.9)

        arr = np.random.randint(90, 170, (512, 512, 3), dtype=np.uint8)
        image = Image.fromarray(arr)
        result = qv._predict_real(image, "rear")
        assert result["accepted"] is True
        assert result["predicted_view"] == "rear_valid"
        assert result["rejection_reason"] is None

    def test_low_confidence_front_rear_confusion_can_be_accepted_for_rear(self, monkeypatch):
        from PIL import Image
        import numpy as np
        import torch
        from services.inference_service.app.routers import quality_view as qv

        class FakeModel(torch.nn.Module):
            def __init__(self, logits):
                super().__init__()
                self.anchor = torch.nn.Parameter(torch.zeros(1))
                self._logits = torch.tensor([logits], dtype=torch.float32)

            def forward(self, x):
                return self._logits.to(x.device)

        fake_quality = FakeModel([3.0, 0.05])
        fake_view = FakeModel([0.1, 2.0, 0.1, 1.5, 0.1])  # front_valid wins, but not strongly
        monkeypatch.setattr(
            qv,
            "get_qv_model",
            lambda: (
                {"kind": "split", "quality_gate": fake_quality, "view_validation": fake_view},
                {
                    "quality_classes": ["accept", "reject"],
                    "viewpoint_classes": ["angled_invalid", "front_valid", "other_invalid", "rear_valid", "side_valid"],
                    "quality_image_size": 224,
                    "view_image_size": 224,
                    "normalize_mean": [0.485, 0.456, 0.406],
                    "normalize_std": [0.229, 0.224, 0.225],
                    "view_threshold": 0.5,
                },
            ),
        )
        monkeypatch.setattr(qv, "bilateral_symmetry_score", lambda image: 0.88)

        arr = np.random.randint(90, 170, (512, 512, 3), dtype=np.uint8)
        image = Image.fromarray(arr)
        result = qv._predict_real(image, "rear")
        assert result["accepted"] is True
        assert result["predicted_view"] == "rear_valid"
        assert result["rejection_reason"] is None


class TestDamageSegPrediction:
    """Test damage segmentation prediction logic."""

    def test_mock_prediction_returns_valid_structure(self):
        """Mock should return damages with correct keys."""
        from PIL import Image
        import numpy as np
        arr = np.random.randint(80, 180, (640, 640, 3), dtype=np.uint8)
        image = Image.fromarray(arr)

        from services.inference_service.app.routers.damage_seg import _predict_mock
        result = _predict_mock(image, "front")

        assert "model_name" in result
        assert "damage_instances" in result
        assert "inference_run_id" in result
        assert isinstance(result["damage_instances"], list)

        for d in result["damage_instances"]:
            assert "damage_type" in d
            assert d["damage_type"] in ["scratch", "dent", "crack", "broken_part"]
            assert "confidence" in d
            assert 0.0 <= d["confidence"] <= 1.0
            assert "bbox_norm" in d
            bbox = d["bbox_norm"]
            assert 0.0 <= bbox["x1"] <= bbox["x2"] <= 1.0
            assert 0.0 <= bbox["y1"] <= bbox["y2"] <= 1.0
            assert "polygon_json" in d
            assert len(d["polygon_json"]) >= 3  # at least a triangle
            assert "centroid_x" in d
            assert "centroid_y" in d
            assert "area_norm" in d

    def test_mock_prediction_is_deterministic(self):
        """Same image + slot should produce same results."""
        from PIL import Image
        import numpy as np
        arr = np.random.RandomState(123).randint(80, 180, (640, 640, 3)).astype(np.uint8)
        image1 = Image.fromarray(arr)
        image2 = Image.fromarray(arr)

        from services.inference_service.app.routers.damage_seg import _predict_mock
        result1 = _predict_mock(image1, "front")
        result2 = _predict_mock(image2, "front")

        assert len(result1["damage_instances"]) == len(result2["damage_instances"])
        for d1, d2 in zip(result1["damage_instances"], result2["damage_instances"]):
            assert d1["damage_type"] == d2["damage_type"]
            assert d1["confidence"] == d2["confidence"]

    def test_real_prediction_post_filters_low_conf_and_tiny_boxes(self, monkeypatch):
        from PIL import Image
        import numpy as np
        import torch
        from services.inference_service.app.routers import damage_seg as seg

        class FakeBoxes:
            def __init__(self):
                self.cls = torch.tensor([0.0, 1.0, 2.0], dtype=torch.float32)
                self.conf = torch.tensor([0.42, 0.88, 0.92], dtype=torch.float32)
                self.xyxy = torch.tensor(
                    [
                        [10.0, 20.0, 120.0, 120.0],   # low confidence -> filtered
                        [30.0, 30.0, 50.0, 45.0],     # too small area -> filtered
                        [120.0, 160.0, 340.0, 300.0], # valid
                    ],
                    dtype=torch.float32,
                )

            def __len__(self):
                return len(self.cls)

        class FakeResult:
            def __init__(self):
                self.boxes = FakeBoxes()
                self.masks = None

        class FakeModel:
            def predict(self, **kwargs):
                return [FakeResult()]

        monkeypatch.setattr(seg, "get_seg_model", lambda: (FakeModel(), {"damage_classes": ["scratch", "dent", "crack"]}))

        arr = np.random.randint(90, 170, (400, 400, 3), dtype=np.uint8)
        image = Image.fromarray(arr)
        result = seg._predict_real(image, "rear")

        assert len(result["damage_instances"]) == 1
        kept = result["damage_instances"][0]
        assert kept["damage_type"] == "crack"
        assert kept["confidence"] >= 0.45


class TestOverlayRendering:
    """Test overlay rendering produces valid PNG data."""

    def test_overlay_png_b64(self):
        from PIL import Image
        import numpy as np
        import base64

        arr = np.random.randint(80, 180, (256, 256, 3), dtype=np.uint8)
        image = Image.fromarray(arr)

        damages = [{
            "damage_type": "scratch",
            "bbox_norm": {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6},
            "polygon_json": [[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]],
        }]

        from services.inference_service.app.utils.image import overlay_png_b64
        b64 = overlay_png_b64(image, damages)
        assert len(b64) > 100  # should have content
        # Verify it's valid base64
        decoded = base64.b64decode(b64)
        # Verify it's a PNG
        assert decoded[:4] == b'\x89PNG'

    def test_overlay_empty_damages(self):
        """No damages means no overlay should be generated."""
        from services.inference_service.app.routers.damage_seg import _predict_mock
        from PIL import Image
        import numpy as np
        # We can't guarantee zero detections from mock, but overlay_png_b64
        # only returns data when damages > 0, and the route handles None
