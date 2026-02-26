"""
Tests for model registry API routes (SIP-0074 §5.9).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.models import router

pytestmark = [pytest.mark.domain_contracts]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestListModels:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_each_model_has_required_fields(self, client):
        resp = client.get("/api/v1/models")
        data = resp.json()
        for model in data:
            assert "name" in model
            assert "context_window" in model
            assert "default_max_completion" in model

    def test_known_model_present(self, client):
        resp = client.get("/api/v1/models")
        data = resp.json()
        names = [m["name"] for m in data]
        assert "qwen2.5:7b" in names

    def test_context_window_exceeds_completion(self, client):
        resp = client.get("/api/v1/models")
        data = resp.json()
        for model in data:
            assert model["context_window"] > model["default_max_completion"], (
                f"{model['name']}: context_window must exceed default_max_completion"
            )

    def test_cache_control_header(self, client):
        resp = client.get("/api/v1/models")
        assert resp.headers.get("cache-control") == "public, max-age=300"
