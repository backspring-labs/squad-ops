"""
Unit tests for build and build-only CRP profiles (SIP-Enhanced-Agent-Build-Capabilities).

Validates that the build.yaml and build-only.yaml profiles load, pass
schema validation, and contain the expected build_tasks and gate config.

Part of Phase 4.
"""

import pytest

from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


class TestBuildProfileLoads:
    def test_build_profile_loads(self):
        """build.yaml loads and passes schema validation."""
        profile = load_profile("build")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "build"

    def test_build_profile_has_build_tasks(self):
        """build.yaml defaults enable build_tasks."""
        profile = load_profile("build")
        build_tasks = profile.defaults.get("build_tasks")
        assert build_tasks is not None
        assert build_tasks is True

    def test_build_profile_has_plan_review_gate(self):
        """build.yaml has a progress_plan_review gate after governance.review."""
        profile = load_profile("build")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert len(gates) >= 1
        gate = gates[0]
        assert gate["name"] == "progress_plan_review"
        assert "governance.review" in gate["after_task_types"]

    def test_build_profile_expected_artifact_types(self):
        """build.yaml includes source, test, config in expected_artifact_types."""
        profile = load_profile("build")
        types = profile.defaults["expected_artifact_types"]
        assert "source" in types
        assert "test" in types
        assert "config" in types
        assert "document" in types


class TestBuildOnlyProfileLoads:
    def test_build_only_profile_loads(self):
        """build-only.yaml loads and passes schema validation."""
        profile = load_profile("build-only")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "build-only"

    def test_build_only_has_build_tasks(self):
        """build-only.yaml defaults contain build_tasks list."""
        profile = load_profile("build-only")
        build_tasks = profile.defaults.get("build_tasks")
        assert build_tasks is not None
        assert "development.develop" in build_tasks
        assert "qa.test" in build_tasks

    def test_build_only_has_no_gates(self):
        """build-only.yaml has no gates (build-only skips planning)."""
        profile = load_profile("build-only")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert gates == []

    def test_build_only_plan_tasks_false(self):
        """build-only.yaml sets plan_tasks: false."""
        profile = load_profile("build-only")
        assert profile.defaults.get("plan_tasks") is False

    def test_build_only_no_documentation_type(self):
        """build-only.yaml does not include documentation in expected_artifact_types."""
        profile = load_profile("build-only")
        types = profile.defaults["expected_artifact_types"]
        assert "document" not in types
        assert "source" in types
        assert "test" in types


class TestBuildProfilesInListing:
    def test_build_profiles_appear_in_listing(self):
        """Both build and build-only appear in list_profiles()."""
        names = list_profiles()
        assert "build" in names
        assert "build-only" in names
