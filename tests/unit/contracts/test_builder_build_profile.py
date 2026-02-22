"""Unit tests for builder-build cycle request profile (SIP-0071 Phase 2).

Validates that builder-build.yaml loads, passes schema validation,
and contains the expected builder-specific defaults.
"""
import pytest

from squadops.contracts.cycle_request_profiles import load_profile, list_profiles
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


class TestBuilderBuildProfileLoads:
    def test_profile_loads(self):
        """builder-build.yaml loads and passes schema validation."""
        profile = load_profile("builder-build")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "builder-build"

    def test_has_build_tasks(self):
        """builder-build.yaml defaults contain builder.build task."""
        profile = load_profile("builder-build")
        build_tasks = profile.defaults.get("build_tasks")
        assert build_tasks is not None
        assert "builder.build" in build_tasks
        assert "qa.build_validate" in build_tasks

    def test_does_not_use_development_build(self):
        """builder-build.yaml must use builder.build, not development.build."""
        profile = load_profile("builder-build")
        build_tasks = profile.defaults.get("build_tasks")
        assert "development.build" not in build_tasks

    def test_has_plan_review_gate(self):
        """builder-build.yaml has a plan-review gate after governance.review."""
        profile = load_profile("builder-build")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert len(gates) >= 1
        gate = gates[0]
        assert gate["name"] == "plan-review"
        assert "governance.review" in gate["after_task_types"]

    def test_includes_qa_handoff_artifact_type(self):
        """builder-build.yaml includes qa_handoff in expected_artifact_types."""
        profile = load_profile("builder-build")
        types = profile.defaults["expected_artifact_types"]
        assert "qa_handoff" in types

    def test_includes_build_profile(self):
        """builder-build.yaml specifies build_profile in defaults."""
        profile = load_profile("builder-build")
        assert profile.defaults.get("build_profile") == "python_cli_builder"

    def test_expected_artifact_types_complete(self):
        """builder-build.yaml includes standard artifact types."""
        profile = load_profile("builder-build")
        types = profile.defaults["expected_artifact_types"]
        assert "document" in types
        assert "source" in types
        assert "test" in types
        assert "config" in types


class TestBuilderBuildInListing:
    def test_appears_in_listing(self):
        """builder-build appears in list_profiles()."""
        names = list_profiles()
        assert "builder-build" in names
