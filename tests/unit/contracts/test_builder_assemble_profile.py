"""Unit tests for builder-assemble cycle request profile (SIP-0071).

Validates that builder-assemble.yaml loads, passes schema validation,
and contains the expected builder-specific defaults.
"""
import pytest

from squadops.contracts.cycle_request_profiles import load_profile, list_profiles
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


class TestBuilderAssembleProfileLoads:
    def test_profile_loads(self):
        """builder-assemble.yaml loads and passes schema validation."""
        profile = load_profile("builder-assemble")
        assert isinstance(profile, CycleRequestProfile)
        assert profile.name == "builder-assemble"

    def test_has_build_tasks(self):
        """builder-assemble.yaml defaults contain builder.assemble task."""
        profile = load_profile("builder-assemble")
        build_tasks = profile.defaults.get("build_tasks")
        assert build_tasks is not None
        assert "development.develop" in build_tasks
        assert "builder.assemble" in build_tasks
        assert "qa.test" in build_tasks

    def test_three_step_build_pipeline(self):
        """builder-assemble.yaml has 3-step build pipeline."""
        profile = load_profile("builder-assemble")
        build_tasks = profile.defaults.get("build_tasks")
        assert len(build_tasks) == 3
        assert build_tasks[0] == "development.develop"
        assert build_tasks[1] == "builder.assemble"
        assert build_tasks[2] == "qa.test"

    def test_has_plan_review_gate(self):
        """builder-assemble.yaml has a plan-review gate after governance.review."""
        profile = load_profile("builder-assemble")
        gates = profile.defaults["task_flow_policy"]["gates"]
        assert len(gates) >= 1
        gate = gates[0]
        assert gate["name"] == "plan-review"
        assert "governance.review" in gate["after_task_types"]

    def test_includes_qa_handoff_artifact_type(self):
        """builder-assemble.yaml includes qa_handoff in expected_artifact_types."""
        profile = load_profile("builder-assemble")
        types = profile.defaults["expected_artifact_types"]
        assert "qa_handoff" in types

    def test_includes_build_profile(self):
        """builder-assemble.yaml specifies build_profile in defaults."""
        profile = load_profile("builder-assemble")
        assert profile.defaults.get("build_profile") == "python_cli_builder"

    def test_expected_artifact_types_complete(self):
        """builder-assemble.yaml includes standard artifact types."""
        profile = load_profile("builder-assemble")
        types = profile.defaults["expected_artifact_types"]
        assert "document" in types
        assert "source" in types
        assert "test" in types
        assert "config" in types


class TestBuilderAssembleInListing:
    def test_appears_in_listing(self):
        """builder-assemble appears in list_profiles()."""
        names = list_profiles()
        assert "builder-assemble" in names
