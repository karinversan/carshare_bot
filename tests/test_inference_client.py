import pytest

from apps.api_service.app.services.inference_client import InferenceClient, InferenceServiceError


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.request = object()
        self.text = str(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError("HTTP error path is not expected in this test")

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, files=None, data=None):
        return _FakeResponse(self._payload)


def test_quality_view_does_not_fallback_to_mock_when_real_inference_is_required(monkeypatch):
    from apps.api_service.app.services import inference_client as inference_module

    monkeypatch.setattr(inference_module.settings, "require_real_inference", True)
    monkeypatch.setattr(inference_module.httpx, "Client", lambda timeout=60.0: _FakeClient({"model_backend": "mock"}))

    client = InferenceClient()
    monkeypatch.setattr(client, "_base_candidates", lambda: ["http://inference.local"])

    with pytest.raises(InferenceServiceError, match="Mock inference backend"):
        client.quality_view_predict(b"jpeg-bytes", "frame.jpg", "front")


def test_damage_seg_mock_fallback_is_allowed_only_when_real_inference_is_optional(monkeypatch):
    from apps.api_service.app.services import inference_client as inference_module

    monkeypatch.setattr(inference_module.settings, "require_real_inference", False)
    monkeypatch.setattr(inference_module.settings, "app_env", "dev")
    monkeypatch.setattr(
        inference_module.httpx,
        "Client",
        lambda timeout=60.0: _FakeClient({"model_backend": "mock", "damage_instances": []}),
    )

    client = InferenceClient()
    monkeypatch.setattr(client, "_base_candidates", lambda: ["http://inference.local"])

    payload = client.damage_seg_predict(b"jpeg-bytes", "frame.jpg", "front")
    assert payload["model_backend"] == "mock"
    assert payload["damage_instances"] == []
