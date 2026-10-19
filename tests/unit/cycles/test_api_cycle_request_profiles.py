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

    def test_a_frozen_name_is_not_listed_but_still_resolves(self, client):
        """#316 (R2.4): the listing is the operator's, and every old name still resolves by name.
        Bug caught: dropping a frozen profile from the route along with the listing, so a pinned
        config that names it 404s."""
        names = [p["name"] for p in client.get("/api/v1/cycle-request-profiles").json()]
        resp = client.get("/api/v1/cycle-request-profiles/default")

        assert "default" not in names
        assert resp.status_code == 200
        assert resp.json()["name"] == "default"

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


class TestTheStacksAProfileOffers:
    def test_an_operator_profile_offers_the_stacks_and_every_other_profile_none(self, client):
        """#2520. Bug caught: the console unable to put an operator profile on a stack, so a
        squad with a builder fails at its plan with no build_profile; or a campaign or frozen
        profile, which pins its own stack or takes none, offered one that would change it."""
        from squadops.stacks.request_defaults import STACK_REQUEST_DEFAULTS

        listed = {
            p["name"]: p["stacks"] for p in client.get("/api/v1/cycle-request-profiles").json()
        }
        pinned = client.get("/api/v1/cycle-request-profiles/validated-fullstack").json()

        assert listed["validate"] == ["fullstack_fastapi_react", "nextjs_ts"]
        assert all(stacks == sorted(STACK_REQUEST_DEFAULTS) for stacks in listed.values())
        assert pinned["stacks"] == []


class TestResolveCycleRequest:
    """#2520: the console resolves a profile's name into the cycle-create body here, with the
    builder the CLI and a campaign's launches use."""

    @pytest.mark.parametrize("stack", ["fullstack_fastapi_react", "nextjs_ts"])
    def test_an_operator_profile_on_a_stack_resolves_to_exactly_the_clis_body(self, client, stack):
        """Bug caught: the console creating a different cycle from the CLI's for the same request:
        an operator profile on a stack without the stack's required checks, time budget and
        manifest attempts beneath it (#316, R2.3), as the console's own body builder did."""
        from squadops.contracts.cycle_request_profiles import cycle_request_body
        from squadops.stacks.request_defaults import request_defaults_for

        values = {"build_profile": stack, "max_correction_attempts": 2}
        resp = client.post(
            "/api/v1/cycle-request-profiles/validate/resolve",
            json={"squad_profile_id": "full", "values": values, "prd_ref": "art_prd", "notes": "n"},
        )
        cli = cycle_request_body(
            "validate", squad_profile_id="full", user_values=values, notes="n", prd_ref="art_prd"
        )

        assert resp.status_code == 200
        body = resp.json()
        assert {k: body[k] for k in cli} == cli
        stack_keys = set(request_defaults_for(stack))
        assert stack_keys and stack_keys <= set(body["applied_defaults"])
        assert body["execution_overrides"]["max_correction_attempts"] == 2

    @pytest.mark.parametrize(
        ("path", "payload", "status"),
        [
            ("no-such-profile", {"squad_profile_id": "full"}, 404),
            (
                "validate",
                {"squad_profile_id": "full", "values": {"build_strategy": "sideways"}},
                422,
            ),
            ("validate", {"squad_profile_id": "full", "applied_defaults": {}}, 422),
            ("validate", {}, 422),
        ],
        ids=[
            "unknown-profile",
            "a-body-create-refuses",
            "a-field-the-caller-may-not-set",
            "no-squad",
        ],
    )
    def test_a_request_that_cant_resolve_is_refused_before_anything_is_created(
        self, client, path, payload, status
    ):
        """Bug caught: a value the create route refuses resolved anyway, so the console's preview
        shows a cycle it then fails to create; or the caller setting the resolved fields itself,
        which is the second builder this route replaces."""
        resp = client.post(f"/api/v1/cycle-request-profiles/{path}/resolve", json=payload)

        assert resp.status_code == status
