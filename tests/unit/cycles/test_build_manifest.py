"""Tests for BuildTaskManifest model (SIP-0086 Phase 1a)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from squadops.cycles.build_manifest import BuildTaskManifest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_MANIFEST_YAML = """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123

tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend models"
    description: "Create data models"
    expected_artifacts:
      - "backend/models.py"
    acceptance_criteria:
      - "RunEvent model has id and title fields"
    depends_on: []

  - task_index: 1
    task_type: development.develop
    role: dev
    focus: "Backend API"
    description: "Create endpoints"
    expected_artifacts:
      - "backend/main.py"
    depends_on: [0]

  - task_index: 2
    task_type: qa.test
    role: qa
    focus: "Backend tests"
    description: "Write tests"
    expected_artifacts:
      - "tests/test_api.py"
    depends_on: [0, 1]

summary:
  total_dev_tasks: 2
  total_qa_tasks: 1
  total_tasks: 3
  estimated_layers: [backend, test]
"""


@dataclass
class _FakeAgent:
    role: str
    enabled: bool = True


@dataclass
class _FakeProfile:
    agents: list[_FakeAgent]
    profile_id: str = "test-profile"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestBuildTaskManifestParsing:
    def test_valid_manifest_round_trips(self):
        manifest = BuildTaskManifest.from_yaml(VALID_MANIFEST_YAML)

        assert manifest.version == 1
        assert manifest.project_id == "group_run"
        assert manifest.cycle_id == "cyc_test"
        assert manifest.prd_hash == "abc123"
        assert len(manifest.tasks) == 3
        assert manifest.summary.total_tasks == 3

    def test_task_fields_populated(self):
        manifest = BuildTaskManifest.from_yaml(VALID_MANIFEST_YAML)
        task0 = manifest.tasks[0]

        assert task0.task_index == 0
        assert task0.task_type == "development.develop"
        assert task0.role == "dev"
        assert task0.focus == "Backend models"
        assert task0.expected_artifacts == ["backend/models.py"]
        assert task0.acceptance_criteria == ["RunEvent model has id and title fields"]
        assert task0.depends_on == []

    def test_dependency_chain_parsed(self):
        manifest = BuildTaskManifest.from_yaml(VALID_MANIFEST_YAML)

        assert manifest.tasks[1].depends_on == [0]
        assert manifest.tasks[2].depends_on == [0, 1]

    def test_acceptance_criteria_optional(self):
        """Tasks without acceptance_criteria default to empty list."""
        manifest = BuildTaskManifest.from_yaml(VALID_MANIFEST_YAML)

        # Task 1 has no acceptance_criteria in the YAML
        assert manifest.tasks[1].acceptance_criteria == []

    def test_to_dict_serializes(self):
        manifest = BuildTaskManifest.from_yaml(VALID_MANIFEST_YAML)
        d = manifest.to_dict()

        assert d["version"] == 1
        assert len(d["tasks"]) == 3
        assert d["tasks"][0]["focus"] == "Backend models"


# ---------------------------------------------------------------------------
# Schema validation errors
# ---------------------------------------------------------------------------


class TestBuildTaskManifestValidation:
    def test_malformed_yaml_raises(self):
        with pytest.raises(ValueError, match="Malformed YAML"):
            BuildTaskManifest.from_yaml("{{not: valid: yaml::")

    def test_non_mapping_raises(self):
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            BuildTaskManifest.from_yaml("- just a list")

    def test_missing_required_field_raises(self):
        yaml_str = """\
version: 1
project_id: test
# missing cycle_id, prd_hash, tasks, summary
"""
        with pytest.raises(ValueError, match="Missing required field"):
            BuildTaskManifest.from_yaml(yaml_str)

    def test_empty_tasks_raises(self):
        yaml_str = """\
version: 1
project_id: test
cycle_id: cyc_test
prd_hash: abc
tasks: []
summary:
  total_tasks: 0
"""
        with pytest.raises(ValueError, match="at least one task"):
            BuildTaskManifest.from_yaml(yaml_str)

    def test_unknown_task_type_raises(self):
        yaml_str = """\
version: 1
project_id: test
cycle_id: cyc_test
prd_hash: abc
tasks:
  - task_index: 0
    task_type: unknown.task
    role: dev
    focus: test
    description: test
summary:
  total_tasks: 1
"""
        with pytest.raises(ValueError, match="unknown task_type"):
            BuildTaskManifest.from_yaml(yaml_str)

    def test_missing_task_field_raises(self):
        yaml_str = """\
version: 1
project_id: test
cycle_id: cyc_test
prd_hash: abc
tasks:
  - task_index: 0
    task_type: development.develop
    # missing role, focus, description
summary:
  total_tasks: 1
"""
        with pytest.raises(ValueError, match="missing required field"):
            BuildTaskManifest.from_yaml(yaml_str)

    def test_depends_on_out_of_range_raises(self):
        yaml_str = """\
version: 1
project_id: test
cycle_id: cyc_test
prd_hash: abc
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: test
    description: test
    depends_on: [99]
summary:
  total_tasks: 1
"""
        with pytest.raises(ValueError, match="non-existent task_index 99"):
            BuildTaskManifest.from_yaml(yaml_str)

    def test_dependency_cycle_raises(self):
        yaml_str = """\
version: 1
project_id: test
cycle_id: cyc_test
prd_hash: abc
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: task A
    description: test
    depends_on: [1]
  - task_index: 1
    task_type: development.develop
    role: dev
    focus: task B
    description: test
    depends_on: [0]
summary:
  total_tasks: 2
"""
        with pytest.raises(ValueError, match="Dependency cycle"):
            BuildTaskManifest.from_yaml(yaml_str)

    def test_duplicate_task_index_raises(self):
        yaml_str = """\
version: 1
project_id: test
cycle_id: cyc_test
prd_hash: abc
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: task A
    description: test
  - task_index: 0
    task_type: qa.test
    role: qa
    focus: task B
    description: test
summary:
  total_tasks: 2
"""
        with pytest.raises(ValueError, match="Duplicate task_index"):
            BuildTaskManifest.from_yaml(yaml_str)


# ---------------------------------------------------------------------------
# Profile validation
# ---------------------------------------------------------------------------


class TestValidateAgainstProfile:
    def test_valid_profile_returns_no_errors(self):
        manifest = BuildTaskManifest.from_yaml(VALID_MANIFEST_YAML)
        profile = _FakeProfile(agents=[_FakeAgent("dev"), _FakeAgent("qa")])

        errors = manifest.validate_against_profile(profile)

        assert errors == []

    def test_missing_role_returns_error(self):
        manifest = BuildTaskManifest.from_yaml(VALID_MANIFEST_YAML)
        profile = _FakeProfile(agents=[_FakeAgent("dev")])  # no qa

        errors = manifest.validate_against_profile(profile)

        assert len(errors) == 1
        assert "role 'qa' not in profile" in errors[0]

    def test_disabled_agent_treated_as_missing(self):
        manifest = BuildTaskManifest.from_yaml(VALID_MANIFEST_YAML)
        profile = _FakeProfile(
            agents=[_FakeAgent("dev"), _FakeAgent("qa", enabled=False)]
        )

        errors = manifest.validate_against_profile(profile)

        assert len(errors) == 1
        assert "qa" in errors[0]
