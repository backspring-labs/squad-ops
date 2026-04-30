"""Tests for ImplementationPlan model (SIP-0086 Phase 1a + SIP-0092 M1.1)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from squadops.cycles.acceptance_check_spec import CHECK_SPECS
from squadops.cycles.implementation_plan import ImplementationPlan, TypedCheck


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


class TestImplementationPlanParsing:
    def test_valid_manifest_round_trips(self):
        manifest = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)

        assert manifest.version == 1
        assert manifest.project_id == "group_run"
        assert manifest.cycle_id == "cyc_test"
        assert manifest.prd_hash == "abc123"
        assert len(manifest.tasks) == 3
        assert manifest.summary.total_tasks == 3

    def test_task_fields_populated(self):
        manifest = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)
        task0 = manifest.tasks[0]

        assert task0.task_index == 0
        assert task0.task_type == "development.develop"
        assert task0.role == "dev"
        assert task0.focus == "Backend models"
        assert task0.expected_artifacts == ["backend/models.py"]
        assert task0.acceptance_criteria == ["RunEvent model has id and title fields"]
        assert task0.depends_on == []

    def test_dependency_chain_parsed(self):
        manifest = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)

        assert manifest.tasks[1].depends_on == [0]
        assert manifest.tasks[2].depends_on == [0, 1]

    def test_acceptance_criteria_optional(self):
        """Tasks without acceptance_criteria default to empty list."""
        manifest = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)

        # Task 1 has no acceptance_criteria in the YAML
        assert manifest.tasks[1].acceptance_criteria == []

    def test_to_dict_serializes(self):
        manifest = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)
        d = manifest.to_dict()

        assert d["version"] == 1
        assert len(d["tasks"]) == 3
        assert d["tasks"][0]["focus"] == "Backend models"


# ---------------------------------------------------------------------------
# Schema validation errors
# ---------------------------------------------------------------------------


class TestImplementationPlanValidation:
    def test_malformed_yaml_raises(self):
        with pytest.raises(ValueError, match="Malformed YAML"):
            ImplementationPlan.from_yaml("{{not: valid: yaml::")

    def test_non_mapping_raises(self):
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            ImplementationPlan.from_yaml("- just a list")

    def test_missing_required_field_raises(self):
        yaml_str = """\
version: 1
project_id: test
# missing cycle_id, prd_hash, tasks, summary
"""
        with pytest.raises(ValueError, match="Missing required field"):
            ImplementationPlan.from_yaml(yaml_str)

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
            ImplementationPlan.from_yaml(yaml_str)

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
            ImplementationPlan.from_yaml(yaml_str)

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
            ImplementationPlan.from_yaml(yaml_str)

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
            ImplementationPlan.from_yaml(yaml_str)

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
            ImplementationPlan.from_yaml(yaml_str)

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
            ImplementationPlan.from_yaml(yaml_str)


# ---------------------------------------------------------------------------
# Profile validation
# ---------------------------------------------------------------------------


class TestValidateAgainstProfile:
    def test_valid_profile_returns_no_errors(self):
        manifest = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)
        profile = _FakeProfile(agents=[_FakeAgent("dev"), _FakeAgent("qa")])

        errors = manifest.validate_against_profile(profile)

        assert errors == []

    def test_missing_role_returns_error(self):
        manifest = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)
        profile = _FakeProfile(agents=[_FakeAgent("dev")])  # no qa

        errors = manifest.validate_against_profile(profile)

        assert len(errors) == 1
        assert "role 'qa' not in profile" in errors[0]

    def test_disabled_agent_treated_as_missing(self):
        manifest = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)
        profile = _FakeProfile(
            agents=[_FakeAgent("dev"), _FakeAgent("qa", enabled=False)]
        )

        errors = manifest.validate_against_profile(profile)

        assert len(errors) == 1
        assert "qa" in errors[0]


# ---------------------------------------------------------------------------
# SIP-0092 M1.1 — Typed acceptance criteria
# ---------------------------------------------------------------------------


def _plan_with_criteria(criteria_yaml: str) -> str:
    """Helper: build a minimal valid plan with a custom acceptance_criteria block."""
    return f"""\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123

tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Backend"
    description: "Build endpoints"
    expected_artifacts:
      - "backend/routes.py"
    acceptance_criteria:
{criteria_yaml}
    depends_on: []

summary:
  total_dev_tasks: 1
  total_qa_tasks: 0
  total_tasks: 1
"""


class TestTypedAcceptanceParsing:
    """SIP-0092 M1.1: parser normalizes mixed prose+typed lists into TypedCheck."""

    def test_mixed_prose_and_typed_preserved(self):
        yaml_block = """\
      - "Endpoint exists"
      - check: regex_match
        file: backend/routes.py
        pattern: "status_code\\\\s*=\\\\s*409"
"""
        plan = ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))
        criteria = plan.tasks[0].acceptance_criteria
        assert len(criteria) == 2
        assert criteria[0] == "Endpoint exists"
        assert isinstance(criteria[1], TypedCheck)
        assert criteria[1].check == "regex_match"

    def test_typed_only_list_parses(self):
        yaml_block = """\
      - check: regex_match
        file: backend/routes.py
        pattern: "status_code"
      - check: count_at_least
        glob: "tests/**/*.py"
        min_count: 1
"""
        plan = ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))
        assert all(isinstance(c, TypedCheck) for c in plan.tasks[0].acceptance_criteria)

    def test_params_excludes_reserved_keys(self):
        """flat-YAML normalization: params = entry minus {check, severity, description}."""
        yaml_block = """\
      - check: regex_match
        severity: warning
        description: "Coverage"
        file: backend/routes.py
        pattern: "status_code"
"""
        plan = ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))
        tc = plan.tasks[0].acceptance_criteria[0]
        assert isinstance(tc, TypedCheck)
        assert tc.severity == "warning"
        assert tc.description == "Coverage"
        assert set(tc.params.keys()) == {"file", "pattern"}
        # Reserved keys must NOT appear in params
        assert "check" not in tc.params
        assert "severity" not in tc.params
        assert "description" not in tc.params

    def test_default_severity_is_error(self):
        yaml_block = """\
      - check: regex_match
        file: backend/routes.py
        pattern: "x"
"""
        plan = ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))
        tc = plan.tasks[0].acceptance_criteria[0]
        assert isinstance(tc, TypedCheck)
        assert tc.severity == "error"

    def test_round_trip_re_serialize(self):
        """from_yaml → to_dict → re-emit YAML → from_yaml produces equal task criteria."""
        import yaml as _yaml

        original_yaml = """\
      - "Prose entry"
      - check: regex_match
        severity: warning
        file: backend/routes.py
        pattern: "x"
"""
        plan = ImplementationPlan.from_yaml(_plan_with_criteria(original_yaml))
        serialized = _yaml.safe_dump(plan.to_dict())
        plan2 = ImplementationPlan.from_yaml(serialized)
        assert plan.tasks[0].acceptance_criteria == plan2.tasks[0].acceptance_criteria


class TestTypedAcceptanceRejections:
    """RC-11 authoring-time validation: parser rejects malformed typed criteria."""

    def test_unknown_check_raises_with_name_in_message(self):
        yaml_block = """\
      - check: invented_check
        file: foo.py
"""
        with pytest.raises(ValueError, match="invented_check"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    @pytest.mark.parametrize(
        "check_name,present_param",
        [
            ("regex_match", "pattern"),  # missing 'file'
            ("count_at_least", "min_count"),  # missing 'glob'
            ("import_present", "module"),  # missing 'file'
        ],
    )
    def test_missing_required_param_raises(self, check_name, present_param):
        yaml_block = f"""\
      - check: {check_name}
        {present_param}: "x"
"""
        with pytest.raises(ValueError, match="missing required param"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    def test_wrong_param_type_raises(self):
        """methods_paths: "GET /runs" as string instead of list → ValueError."""
        yaml_block = """\
      - check: endpoint_defined
        file: backend/routes.py
        methods_paths: "GET /runs"
"""
        with pytest.raises(ValueError, match="methods_paths.*must be list"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    def test_unknown_severity_raises(self):
        yaml_block = """\
      - check: regex_match
        severity: critical
        file: backend/routes.py
        pattern: "x"
"""
        with pytest.raises(ValueError, match="unknown severity"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    def test_unknown_param_raises(self):
        yaml_block = """\
      - check: regex_match
        file: backend/routes.py
        pattern: "x"
        bogus_param: 1
"""
        with pytest.raises(ValueError, match="unknown param"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    def test_absolute_path_raises(self):
        yaml_block = """\
      - check: regex_match
        file: "/etc/passwd"
        pattern: "x"
"""
        with pytest.raises(ValueError, match="absolute"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    def test_dotdot_traversal_raises(self):
        yaml_block = """\
      - check: regex_match
        file: "../../etc/passwd"
        pattern: "x"
"""
        with pytest.raises(ValueError, match=r"'\.\.' traversal"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    def test_typed_entry_missing_check_key_raises(self):
        yaml_block = """\
      - file: backend/routes.py
        pattern: "x"
"""
        with pytest.raises(ValueError, match="missing required key 'check'"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    def test_non_str_non_dict_entry_raises(self):
        yaml_block = """\
      - 42
"""
        with pytest.raises(ValueError, match="string.*or mapping"):
            ImplementationPlan.from_yaml(_plan_with_criteria(yaml_block))

    def test_acceptance_criteria_must_be_list(self):
        yaml = """\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "x"
    description: "x"
    acceptance_criteria: "not a list"
    depends_on: []
summary:
  total_dev_tasks: 1
  total_qa_tasks: 0
  total_tasks: 1
"""
        with pytest.raises(ValueError, match="acceptance_criteria must be a list"):
            ImplementationPlan.from_yaml(yaml)


class TestTypedCheckRegistryCoverage:
    """The CHECK_SPECS registry is the single source of truth — sanity-check it."""

    def test_all_rev1_checks_registered(self):
        rev1 = {
            "endpoint_defined",
            "import_present",
            "field_present",
            "regex_match",
            "count_at_least",
            "command_exit_zero",
        }
        assert rev1.issubset(CHECK_SPECS.keys())

    def test_each_spec_path_params_subset_of_declared_params(self):
        """A path_param key must be a declared (required or optional) param."""
        for name, spec in CHECK_SPECS.items():
            declared = spec.required_params | spec.optional_params
            stragglers = spec.path_params - declared
            assert not stragglers, (
                f"CHECK_SPECS[{name!r}].path_params declares "
                f"{stragglers} which are not in required ∪ optional params"
            )
