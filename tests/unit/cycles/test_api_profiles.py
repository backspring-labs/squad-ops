"""
Tests for SIP-0064 squad profile API routes.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.profiles import router
from squadops.cycles.models import AgentProfileEntry, CycleError, SquadProfile

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

_PROFILE = SquadProfile(
    profile_id="full-squad",
    name="Full Squad",
    description="All agents",
    version=1,
    agents=(
        AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
    ),
    created_at=NOW,
)


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    mock.list_profiles.return_value = [_PROFILE]
    mock.get_profile.return_value = _PROFILE
    mock.get_active_profile.return_value = _PROFILE
    mock.set_active_profile.return_value = None
    return mock


@pytest.fixture
def client(mock_squad_profile, monkeypatch):
    app = FastAPI()
    app.include_router(router)
    import squadops.api.runtime.deps as deps_mod

    monkeypatch.setattr(deps_mod, "_squad_profile", mock_squad_profile)
    return TestClient(app)


class TestListProfiles:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/squad-profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["profile_id"] == "full-squad"


class TestGetActiveProfile:
    def test_returns_active(self, client):
        resp = client.get("/api/v1/squad-profiles/active")
        assert resp.status_code == 200
        assert resp.json()["profile_id"] == "full-squad"


class TestSetActiveProfile:
    def test_sets_active(self, client):
        resp = client.post(
            "/api/v1/squad-profiles/active",
            json={"profile_id": "full-squad"},
        )
        assert resp.status_code == 200
        assert resp.json()["active_profile_id"] == "full-squad"


class TestGetProfile:
    def test_returns_profile(self, client):
        resp = client.get("/api/v1/squad-profiles/full-squad")
        assert resp.status_code == 200
        assert resp.json()["profile_id"] == "full-squad"
        assert len(resp.json()["agents"]) == 1

    def test_not_found(self, client, mock_squad_profile):
        mock_squad_profile.get_profile.side_effect = CycleError("Not found")
        resp = client.get("/api/v1/squad-profiles/unknown")
        assert resp.status_code == 500  # CycleError (base) → 500
