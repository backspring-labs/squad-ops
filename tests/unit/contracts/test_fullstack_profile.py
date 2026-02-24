"""Contract tests for fullstack-fastapi-react cycle request profile (SIP-0072 Phase 3).

Validates the YAML profile loads, defaults are valid, and build pipeline
configuration matches the SIP-0072 specification.
"""
from __future__ import annotations

import pytest

from squadops.contracts.cycle_request_profiles import load_profile, list_profiles

pytestmark = [pytest.mark.domain_contracts]


class TestFullstackProfileLoads:
    def test_profile_in_list(self):
        assert "fullstack-fastapi-react" in list_profiles()

    def test_load_profile_succeeds(self):
        profile = load_profile("fullstack-fastapi-react")
        assert profile.name == "fullstack-fastapi-react"

    def test_has_description(self):
        profile = load_profile("fullstack-fastapi-react")
        assert len(profile.description) > 0


class TestFullstackProfileDefaults:
    def test_dev_capability(self):
        profile = load_profile("fullstack-fastapi-react")
        assert profile.defaults["dev_capability"] == "fullstack_fastapi_react"

    def test_build_profile(self):
        profile = load_profile("fullstack-fastapi-react")
        assert profile.defaults["build_profile"] == "fullstack_fastapi_react"

    def test_build_strategy_is_fresh(self):
        profile = load_profile("fullstack-fastapi-react")
        assert profile.defaults["build_strategy"] == "fresh"

    def test_build_tasks(self):
        profile = load_profile("fullstack-fastapi-react")
        assert profile.defaults["build_tasks"] == [
            "development.develop",
            "builder.assemble",
            "qa.test",
        ]

    def test_expected_artifact_types(self):
        profile = load_profile("fullstack-fastapi-react")
        types = profile.defaults["expected_artifact_types"]
        assert "source" in types
        assert "test" in types
        assert "config" in types
        assert "document" in types


class TestFullstackProfileGate:
    def test_has_plan_review_gate(self):
        profile = load_profile("fullstack-fastapi-react")
        policy = profile.defaults["task_flow_policy"]
        gates = policy["gates"]
        assert len(gates) == 1
        assert gates[0]["name"] == "plan-review"

    def test_gate_after_governance_review(self):
        profile = load_profile("fullstack-fastapi-react")
        policy = profile.defaults["task_flow_policy"]
        gate = policy["gates"][0]
        assert "governance.review" in gate["after_task_types"]
