"""
Tests for SIP-0064 + SIP-0075 squad profile API routes.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.profiles import router
from squadops.cycles.models import (
    ActiveProfileDeletionError,
    AgentProfileEntry,
    ProfileNotFoundError,
    ProfileValidationError,
    SquadProfile,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_PROFILE = SquadProfile(
    profile_id="full-squad",
    name="Full Squad",
    description="All agents",
    version=1,
    agents=(AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),),
    created_at=NOW,
)


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    mock.list_profiles.return_value = [_PROFILE]
    mock.get_profile.return_value = _PROFILE
    mock.get_active_profile.return_value = _PROFILE
    mock.get_active_profile_id.return_value = "full-squad"
    mock.set_active_profile.return_value = None
    mock.activate_profile.return_value = _PROFILE
    mock.create_profile.side_effect = lambda p: p
    mock.update_profile.return_value = _PROFILE
    mock.delete_profile.return_value = None
    return mock


@pytest.fixture
def mock_llm_port():
    mock = AsyncMock()
    mock.refresh_models.return_value = ["qwen2.5:7b", "gpt-4"]
    return mock


@pytest.fixture
def client(mock_squad_profile, mock_llm_port, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_squad_profile", mock_squad_profile)
    monkeypatch.setattr(deps_mod, "_llm_port", mock_llm_port)
    return TestClient(app)


class TestListProfiles:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/squad-profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["profile_id"] == "full-squad"

    def test_includes_is_active(self, client):
        resp = client.get("/api/v1/squad-profiles")
        data = resp.json()
        assert data[0]["is_active"] is True


class TestGetActiveProfile:
    def test_returns_active(self, client):
        resp = client.get("/api/v1/squad-profiles/active")
        assert resp.status_code == 200
        assert resp.json()["profile_id"] == "full-squad"
        assert resp.json()["is_active"] is True


class TestSetActiveProfile:
    def test_sets_active(self, client):
        resp = client.post(
            "/api/v1/squad-profiles/active",
            json={"profile_id": "full-squad"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["active_profile_id"] == "full-squad"


class TestGetProfile:
    def test_returns_profile(self, client):
        resp = client.get("/api/v1/squad-profiles/full-squad")
        assert resp.status_code == 200
        assert resp.json()["profile_id"] == "full-squad"
        assert len(resp.json()["agents"]) == 1

    def test_not_found(self, client, mock_squad_profile):
        mock_squad_profile.get_profile.side_effect = ProfileNotFoundError("Not found")
        resp = client.get("/api/v1/squad-profiles/unknown")
        assert resp.status_code == 404


# --- SIP-0075 CRUD tests ---


class TestCreateProfile:
    def test_creates_profile(self, client):
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Test Profile",
                "agents": [
                    {"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"},
                ],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["profile_id"] == "test-profile"
        assert body["name"] == "Test Profile"

    def test_empty_model_rejected(self, client):
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Bad Profile",
                "agents": [
                    {"agent_id": "neo", "role": "dev", "model": ""},
                ],
            },
        )
        assert resp.status_code == 422

    def test_unknown_config_overrides_rejected(self, client):
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Bad Profile",
                "agents": [
                    {
                        "agent_id": "neo",
                        "role": "dev",
                        "model": "qwen2.5:7b",
                        "config_overrides": {"bad_key": 1},
                    },
                ],
            },
        )
        assert resp.status_code == 422

    def test_duplicate_agent_ids_rejected(self, client):
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Bad Profile",
                "agents": [
                    {"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"},
                    {"agent_id": "neo", "role": "qa", "model": "qwen2.5:7b"},
                ],
            },
        )
        assert resp.status_code == 422

    def test_collision_returns_422(self, client, mock_squad_profile):
        mock_squad_profile.create_profile.side_effect = ProfileValidationError("already exists")
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Full Squad",
                "agents": [
                    {"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"},
                ],
            },
        )
        assert resp.status_code == 422

    def test_extra_fields_rejected(self, client):
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Test",
                "agents": [{"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"}],
                "bogus": "bad",
            },
        )
        assert resp.status_code == 422

    def test_warns_on_unpulled_model(self, client, mock_llm_port):
        mock_llm_port.refresh_models.return_value = ["qwen2.5:7b"]
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Warn Profile",
                "agents": [
                    {"agent_id": "neo", "role": "dev", "model": "unpulled-model:latest"},
                ],
            },
        )
        assert resp.status_code == 200
        assert len(resp.json()["warnings"]) == 1
        assert "unpulled-model:latest" in resp.json()["warnings"][0]

    def test_no_warnings_when_model_pulled(self, client, mock_llm_port):
        mock_llm_port.refresh_models.return_value = ["qwen2.5:7b"]
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Good Profile",
                "agents": [
                    {"agent_id": "neo", "role": "dev", "model": "qwen2.5:7b"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["warnings"] == []

    def test_skips_warnings_when_ollama_unreachable(self, client, mock_llm_port):
        mock_llm_port.refresh_models.side_effect = Exception("Connection refused")
        resp = client.post(
            "/api/v1/squad-profiles",
            json={
                "name": "Offline Profile",
                "agents": [
                    {"agent_id": "neo", "role": "dev", "model": "anything:latest"},
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["warnings"] == []


class TestUpdateProfile:
    def test_updates_profile(self, client):
        resp = client.put(
            "/api/v1/squad-profiles/full-squad",
            json={"name": "Updated Squad"},
        )
        assert resp.status_code == 200

    def test_not_found(self, client, mock_squad_profile):
        mock_squad_profile.update_profile.side_effect = ProfileNotFoundError("Not found")
        resp = client.put(
            "/api/v1/squad-profiles/nonexistent",
            json={"name": "New Name"},
        )
        assert resp.status_code == 404


class TestCloneProfile:
    def test_clones_profile(self, client):
        resp = client.post(
            "/api/v1/squad-profiles/full-squad/clone",
            json={"name": "Cloned Squad"},
        )
        assert resp.status_code == 200
        assert resp.json()["profile_id"] == "cloned-squad"

    def test_source_not_found(self, client, mock_squad_profile):
        mock_squad_profile.get_profile.side_effect = ProfileNotFoundError("Not found")
        resp = client.post(
            "/api/v1/squad-profiles/nonexistent/clone",
            json={"name": "Clone"},
        )
        assert resp.status_code == 404


class TestDeleteProfile:
    def test_deletes_profile(self, client):
        resp = client.delete("/api/v1/squad-profiles/full-squad")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_not_found(self, client, mock_squad_profile):
        mock_squad_profile.delete_profile.side_effect = ProfileNotFoundError("Not found")
        resp = client.delete("/api/v1/squad-profiles/nonexistent")
        assert resp.status_code == 404

    def test_active_profile_rejected(self, client, mock_squad_profile):
        mock_squad_profile.delete_profile.side_effect = ActiveProfileDeletionError("Active")
        resp = client.delete("/api/v1/squad-profiles/full-squad")
        assert resp.status_code == 409


class TestActivateProfile:
    def test_activates_profile(self, client):
        resp = client.post("/api/v1/squad-profiles/full-squad/activate")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    def test_not_found(self, client, mock_squad_profile):
        mock_squad_profile.activate_profile.side_effect = ProfileNotFoundError("Not found")
        resp = client.post("/api/v1/squad-profiles/nonexistent/activate")
        assert resp.status_code == 404
