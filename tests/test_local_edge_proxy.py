import importlib

from fastapi.testclient import TestClient

import scripts.local_edge_proxy as proxy_module


def test_api_default_target_points_to_8000(monkeypatch):
    monkeypatch.delenv("EDGE_API_BASE", raising=False)
    reloaded = importlib.reload(proxy_module)
    assert reloaded.API_BASE == "http://127.0.0.1:8000"
    assert reloaded._target("/api/admin-cases")[0] == "http://127.0.0.1:8000"


def test_admin_upstream_unavailable_returns_503(monkeypatch):
    monkeypatch.setenv("ADMIN_FRONTEND_BASE", "http://127.0.0.1:9")
    reloaded = importlib.reload(proxy_module)
    client = TestClient(reloaded.app, raise_server_exceptions=False)

    response = client.get("/admin/")
    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "upstream_unavailable"
