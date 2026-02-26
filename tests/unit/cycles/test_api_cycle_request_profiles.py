"""
Tests for cycle request profile API routes (SIP-0074 §5.9).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.routes.cycles.cycle_request_profiles import router

pytestmark = [pytest.mark.domain_contracts]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestListCycleRequestProfiles:
    def test_returns_list(self, client):
        resp = client.get("/api/v1/cycle-request-profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_each_profile_has_name(self, client):
        resp = client.get("/api/v1/cycle-request-profiles")
        data = resp.json()
        for profile in data:
            assert "name" in profile
            assert isinstance(profile["name"], str)

    def test_default_profile_present(self, client):
        resp = client.get("/api/v1/cycle-request-profiles")
        data = resp.json()
        names = [p["name"] for p in data]
        assert "default" in names

    def test_profiles_have_defaults_dict(self, client):
        resp = client.get("/api/v1/cycle-request-profiles")
        data = resp.json()
        for profile in data:
            assert "defaults" in profile
            assert isinstance(profile["defaults"], dict)

    def test_profiles_have_prompts_dict(self, client):
        resp = client.get("/api/v1/cycle-request-profiles")
        data = resp.json()
        for profile in data:
            assert "prompts" in profile
            assert isinstance(profile["prompts"], dict)

    def test_cache_control_header(self, client):
        resp = client.get("/api/v1/cycle-request-profiles")
        assert resp.headers.get("cache-control") == "public, max-age=300"


class TestGetCycleRequestProfile:
    def test_known_profile(self, client):
        resp = client.get("/api/v1/cycle-request-profiles/default")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "default"

    def test_unknown_profile_404(self, client):
        resp = client.get("/api/v1/cycle-request-profiles/nonexistent")
        assert resp.status_code == 404

    def test_cache_control_header(self, client):
        resp = client.get("/api/v1/cycle-request-profiles/default")
        assert resp.headers.get("cache-control") == "public, max-age=300"

    def test_prompts_metadata_serialized(self, client):
        """Profiles with prompts should serialize prompt metadata fields (SIP-0074 §5.8)."""
        resp = client.get("/api/v1/cycle-request-profiles")
        data = resp.json()
        for profile in data:
            for key, meta in profile["prompts"].items():
                assert "label" in meta
                assert "help_text" in meta
                assert "choices" in meta
                assert "type" in meta
                assert "required" in meta
