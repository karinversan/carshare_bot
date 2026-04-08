"""Smoke tests for API service — validates FastAPI app instantiation and health endpoint.

These tests use TestClient and do NOT require a running database or external services.
"""
from urllib.parse import urlsplit

import pytest


def test_health_endpoint():
    """Health endpoint should return 200 without any dependencies."""
    from apps.api_service.app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_bot_health_endpoint():
    """Bot service health endpoint."""
    from apps.bot_service.app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["service"] == "bot-service"


def test_s3_asset_route(monkeypatch):
    from apps.api_service.app.main import app
    from apps.api_service.app.services.storage_service import StorageService, storage_service
    from fastapi.testclient import TestClient

    monkeypatch.setattr(StorageService, "get_object", lambda self, bucket, key: (b"ok", "text/plain"))

    client = TestClient(app, raise_server_exceptions=False)
    signed_path = storage_service.presigned_url("raw-images", "demo/file.txt")
    url = urlsplit(signed_path)
    request_path = url.path.removeprefix("/api")
    request_target = f"{request_path}?{url.query}" if url.query else request_path
    resp = client.get(request_target)
    assert resp.status_code == 200
    assert resp.text == "ok"
    assert resp.headers["content-type"].startswith("text/plain")
