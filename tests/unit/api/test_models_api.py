"""Tests for model management API routes (SIP-0075 §2.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.models import router
from squadops.cycles.models import AgentProfileEntry, SquadProfile
from squadops.llm.models import ModelInfo

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_api]


@pytest.fixture()
def mock_llm_port():
    """A provider declaring the capabilities these routes need.

    No longer an ``OllamaAdapter`` and no ``__class__`` fixup: the routes ask the
    port what it supports instead of what class it is (#313), so any conforming
    provider drives them.
    """
    from squadops.ports.llm.provider import LLMPort

    mock = AsyncMock(spec=LLMPort)
    mock.supports.return_value = True
    mock.list_available_models.return_value = [
        ModelInfo(name="qwen2.5:7b", size_bytes=4_000_000_000, modified_at="2026-01-01T00:00:00Z"),
        ModelInfo(
            name="llama3.2:latest", size_bytes=2_000_000_000, modified_at="2026-01-02T00:00:00Z"
        ),
    ]
    mock.pull_model.return_value = None
    mock.delete_model.return_value = None
    return mock


@pytest.fixture()
def incapable_llm_port():
    """A provider that declares neither listing nor management — a hosted
    backend serving models it cannot enumerate or pull."""
    from squadops.ports.llm.provider import LLMPort

    mock = AsyncMock(spec=LLMPort)
    mock.supports.return_value = False
    return mock


@pytest.fixture()
def mock_squad_profile():
    mock = AsyncMock()
    mock.get_active_profile_id.return_value = "full"
    mock.get_profile.return_value = SquadProfile(
        profile_id="full",
        name="Full Squad",
        description="All agents",
        version=1,
        agents=(AgentProfileEntry(agent_id="neo", role="dev", model="qwen2.5:7b", enabled=True),),
        created_at=NOW,
    )
    return mock


def _client_for(port, mock_squad_profile, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_llm_port", port)
    monkeypatch.setattr(deps_mod, "_squad_profile", mock_squad_profile)
    return TestClient(app)


@pytest.fixture()
def client(mock_llm_port, mock_squad_profile, monkeypatch):
    return _client_for(mock_llm_port, mock_squad_profile, monkeypatch)


@pytest.fixture()
def incapable_client(incapable_llm_port, mock_squad_profile, monkeypatch):
    return _client_for(incapable_llm_port, mock_squad_profile, monkeypatch)


class TestListPulledModels:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/models/pulled")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "qwen2.5:7b"

    def test_includes_active_profile_crossref(self, client):
        resp = client.get("/api/v1/models/pulled")
        data = resp.json()
        qwen = next(m for m in data if m["name"] == "qwen2.5:7b")
        assert qwen["in_active_profile"] is True
        assert "neo" in qwen["used_by_active_profile"]

        llama = next(m for m in data if m["name"] == "llama3.2:latest")
        assert llama["in_active_profile"] is False
        assert llama["used_by_active_profile"] == []

    def test_provider_unreachable(self, client, mock_llm_port):
        mock_llm_port.list_available_models.side_effect = Exception("Connection refused")
        resp = client.get("/api/v1/models/pulled")
        assert resp.status_code == 503


class TestPullModel:
    def test_returns_202(self, client):
        resp = client.post("/api/v1/models/pull", json={"name": "qwen2.5:7b"})
        assert resp.status_code == 202
        data = resp.json()
        assert "pull_id" in data
        assert data["model_name"] == "qwen2.5:7b"
        assert data["status"] == "pulling"

    def test_extra_fields_rejected(self, client):
        resp = client.post(
            "/api/v1/models/pull",
            json={"name": "qwen2.5:7b", "bogus": True},
        )
        assert resp.status_code == 422


class TestPullStatus:
    def test_unknown_pull_id_returns_404(self, client):
        resp = client.get("/api/v1/models/pull/nonexistent/status")
        assert resp.status_code == 404

    def test_known_pull_id(self, client):
        # First create a pull job
        resp = client.post("/api/v1/models/pull", json={"name": "qwen2.5:7b"})
        pull_id = resp.json()["pull_id"]

        resp = client.get(f"/api/v1/models/pull/{pull_id}/status")
        assert resp.status_code == 200
        assert resp.json()["pull_id"] == pull_id


class TestDeleteModel:
    def test_deletes_model(self, client):
        resp = client.delete("/api/v1/models/qwen2.5:7b")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_not_found(self, client, mock_llm_port):
        from squadops.llm.exceptions import LLMModelNotFoundError

        mock_llm_port.delete_model.side_effect = LLMModelNotFoundError("not found")
        resp = client.delete("/api/v1/models/nonexistent:latest")
        assert resp.status_code == 404

    def test_provider_unreachable(self, client, mock_llm_port):
        from squadops.llm.exceptions import LLMConnectionError

        mock_llm_port.delete_model.side_effect = LLMConnectionError("refused")
        resp = client.delete("/api/v1/models/qwen2.5:7b")
        assert resp.status_code == 503


class TestUndeclaredCapabilityIsRefused:
    """#313: a provider that cannot manage models gets a 503 naming the missing
    capability — not a vendor name, and never a silent success.

    The 503 itself is unchanged behavior; what changed is that a provider which
    *can* do the work is no longer refused for having the wrong class.
    """

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/api/v1/models/pulled"),
            ("post", "/api/v1/models/pull"),
            ("delete", "/api/v1/models/qwen2.5:7b"),
        ],
    )
    def test_routes_503_when_capability_undeclared(self, incapable_client, method, path):
        kwargs = {"json": {"name": "qwen2.5:7b"}} if method == "post" else {}
        resp = getattr(incapable_client, method)(path, **kwargs)

        assert resp.status_code == 503
        assert "does not support" in resp.json()["detail"]

    def test_registry_route_still_works_without_any_provider_capability(self, incapable_client):
        """The code-defined registry is not a provider surface; it must not be
        collateral damage of an incapable backend."""
        resp = incapable_client.get("/api/v1/models")
        assert resp.status_code == 200
        assert len(resp.json()) > 0
