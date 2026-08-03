"""Tests for ImplementationPlan model (SIP-0086 Phase 1a + SIP-0092 M1.1)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from squadops.cycles.acceptance_check_spec import CHECK_SPECS
from squadops.cycles.implementation_plan import (
    ImplementationPlan,
    TypedCheck,
    planner_build_task_types,
)

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
        profile = _FakeProfile(agents=[_FakeAgent("dev"), _FakeAgent("qa", enabled=False)])

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


class TestPlannerBuildTaskTypes:
    """Bug this guards: the plan author offering ``builder.assemble`` to a
    builder-less squad. In production (cyc_0024e1a0b6b5) that produced a plan
    whose first task aborted at dispatch with 'No handler for capability:
    builder.assemble', failing the whole implementation run 9 minutes in. The
    planner must only offer task types the squad can actually execute.
    """

    def test_builder_squad_gets_full_known_set(self):
        assert planner_build_task_types(has_builder=True) == {
            "development.develop",
            "qa.test",
            "builder.assemble",
        }

    def test_builderless_squad_drops_builder_assemble_but_keeps_build_path(self):
        offered = planner_build_task_types(has_builder=False)
        # The offending capability is gone...
        assert "builder.assemble" not in offered
        # ...but the dev/qa build path remains, so builder-less squads still build.
        assert offered == {"development.develop", "qa.test"}

    def test_result_is_a_fresh_set_callers_cannot_corrupt_constants(self):
        """Returning the module constant itself would let one caller's mutation
        leak into the next cycle's offered task types."""
        result = planner_build_task_types(has_builder=True)
        result.add("bogus.capability")
        assert "bogus.capability" not in planner_build_task_types(has_builder=True)
        assert "bogus.capability" not in planner_build_task_types(has_builder=False)


# ---------------------------------------------------------------------------
# Command-safelist authoring lint (#422)
# ---------------------------------------------------------------------------


def _plan_yaml_with_command(argv_yaml: str) -> str:
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
    description: "Build the backend"
    expected_artifacts:
      - "backend/main.py"
    acceptance_criteria:
      - check: command_exit_zero
        description: "command check"
        argv: {argv_yaml}
    depends_on: []
summary:
  total_tasks: 1
"""


class TestCommandSafelistLint:
    """Authoring-boundary rejection of commands the evaluator can never run.

    Live failure this pins: cycle cyc_bc325a67417d authored `npm test` /
    `pytest --cov` / `make build` acceptance commands that passed plan
    validation, then deterministically died at evaluation with
    command_not_in_safelist after the correction budget was spent.
    """

    @pytest.mark.parametrize(
        "argv",
        [
            '["npm", "test"]',
            '["pytest", "--cov=backend"]',
            '["make", "build"]',
            '["python", "setup.py", "install"]',
            '["python", "-m", "pytest", "tests/"]',
        ],
    )
    def test_authoring_rejects_non_safelisted_command(self, argv):
        with pytest.raises(ValueError, match=r"Task 0\.acceptance_criteria\[0\].*safelist"):
            ImplementationPlan.from_yaml(
                _plan_yaml_with_command(argv), enforce_command_safelist=True
            )

    def test_rejection_message_teaches_allowed_forms(self):
        """The ValueError text becomes the merger's corrective feedback —
        it must name concrete allowed forms, not just say 'no'."""
        with pytest.raises(ValueError, match=r"python -m py_compile <file>"):
            ImplementationPlan.from_yaml(
                _plan_yaml_with_command('["npm", "test"]'), enforce_command_safelist=True
            )

    @pytest.mark.parametrize(
        "argv,parsed_argv",
        [
            (
                '["python", "-m", "py_compile", "backend/main.py"]',
                ["python", "-m", "py_compile", "backend/main.py"],
            ),
            ('["python", "-m", "mypy", "src/"]', ["python", "-m", "mypy", "src/"]),
            ('["node", "--check", "app.js"]', ["node", "--check", "app.js"]),
            ('["ruff", "check", "."]', ["ruff", "check", "."]),
            ('["tsc", "--noEmit"]', ["tsc", "--noEmit"]),
            ('["eslint", "src/"]', ["eslint", "src/"]),
            ('["pyflakes", "main.py"]', ["pyflakes", "main.py"]),
        ],
    )
    def test_authoring_accepts_every_safelisted_form(self, argv, parsed_argv):
        plan = ImplementationPlan.from_yaml(
            _plan_yaml_with_command(argv), enforce_command_safelist=True
        )
        criterion = plan.tasks[0].acceptance_criteria[0]
        assert isinstance(criterion, TypedCheck)
        assert criterion.params["argv"] == parsed_argv

    def test_default_parse_accepts_non_safelisted_command(self):
        """Dispatch-time re-parse must stay permissive: flipping the default
        would break loading pre-lint plans and demote out-of-safelist commands
        from blocking evaluation errors to unparseable (fail-open)."""
        plan = ImplementationPlan.from_yaml(_plan_yaml_with_command('["npm", "test"]'))
        criterion = plan.tasks[0].acceptance_criteria[0]
        assert isinstance(criterion, TypedCheck)
        assert criterion.params["argv"] == ["npm", "test"]

    def test_authoring_rejects_non_string_argv_items(self):
        with pytest.raises(ValueError, match="every argv item must be a string"):
            ImplementationPlan.from_yaml(
                _plan_yaml_with_command('["python", 1]'), enforce_command_safelist=True
            )


class TestValidateCriteriaScope:
    """#464: regex_match on a source file is a style lottery — 3.9/3.10 both
    burned on framing-invented criteria unwinnable by correct code. The scope
    validator rejects them at the plan level so the gate fails in seconds
    instead of the run failing after an hour of correction budget."""

    def _plan(self, criteria_yaml: str) -> ImplementationPlan:
        return ImplementationPlan.from_yaml(f"""\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: "Frontend view"
    description: "Fill stubs"
    expected_artifacts: ["frontend/src/views/RunDetailView.jsx"]
    depends_on: []
    acceptance_criteria:
{criteria_yaml}
summary:
  total_dev_tasks: 1
  total_qa_tasks: 0
  total_tasks: 1
  estimated_layers: [frontend]
""")

    def test_regex_on_source_file_rejected(self):
        """The 3.10 reproduction: quote-delimited regex against a .jsx file."""
        plan = self._plan(
            "      - {check: regex_match, file: frontend/src/views/RunDetailView.jsx, "
            "pattern: 'apiFetch\\(', count_min: 1}"
        )
        errors = plan.validate_criteria_scope()
        assert len(errors) == 1
        assert "RunDetailView.jsx" in errors[0]
        assert "#464" in errors[0]

    def test_regex_on_document_allowed(self):
        plan = self._plan(
            "      - {check: regex_match, file: qa_handoff.md, "
            "pattern: '## How to Test', count_min: 1}"
        )
        assert plan.validate_criteria_scope() == []

    def test_non_regex_source_checks_and_prose_untouched(self):
        """Only regex_match is scoped: AST checks on source files and prose
        criteria must not be rejected."""
        plan = self._plan(
            "      - {check: import_present, file: frontend/src/views/RunDetailView.jsx, "
            "module: react}\n"
            "      - Renders the participant list"
        )
        assert plan.validate_criteria_scope() == []

    def test_taught_example_is_scope_legal(self):
        """Guard: the regex_match exemplar rendered to proposers must satisfy
        the scope rule — teaching a forbidden shape re-creates the lottery."""
        from squadops.cycles.acceptance_check_spec import (
            CHECK_SPECS,
            regex_target_is_document,
        )

        assert regex_target_is_document(CHECK_SPECS["regex_match"].example["file"])

    def test_warning_severity_regex_on_source_tolerated(self):
        """A warning-severity regex-on-source is a soft slip — tolerated by the
        scope validator (RC-9: a warning check can't block a build, so it must not
        kill the cycle at plan validation), surfaced by soft_criteria_violations."""
        plan = self._plan(
            "      - {check: regex_match, file: frontend/src/views/RunDetailView.jsx, "
            "pattern: 'apiFetch', severity: warning}"
        )
        assert plan.validate_criteria_scope() == []
        soft = plan.soft_criteria_violations()
        assert len(soft) == 1
        assert "RunDetailView.jsx" in soft[0]
        assert "severity=warning" in soft[0]

    def test_info_severity_regex_on_source_tolerated(self):
        plan = self._plan(
            "      - {check: regex_match, file: frontend/src/views/RunDetailView.jsx, "
            "pattern: 'x', severity: info}"
        )
        assert plan.validate_criteria_scope() == []
        assert len(plan.soft_criteria_violations()) == 1

    def test_error_severity_regex_on_source_still_rejected(self):
        """The severity split keeps error-severity structural violations fatal —
        the author asserted it matters, so honor the rejection."""
        plan = self._plan(
            "      - {check: regex_match, file: frontend/src/views/RunDetailView.jsx, "
            "pattern: 'apiFetch', severity: error}"
        )
        errors = plan.validate_criteria_scope()
        assert len(errors) == 1
        assert "#464" in errors[0]
        assert plan.soft_criteria_violations() == []

    def test_document_regex_never_a_soft_violation(self):
        """A document regex is legal at any severity — never fatal, never soft."""
        plan = self._plan(
            "      - {check: regex_match, file: qa_handoff.md, "
            "pattern: '## How to Test', severity: warning}"
        )
        assert plan.validate_criteria_scope() == []
        assert plan.soft_criteria_violations() == []


class TestQaArtifactOwnership:
    """pf-39: a qa.test task declaring scaffold- or dev-owned files is unsatisfiable.

    Write authorization already refuses those emissions (``unauthorized_slot_emission``),
    so the plan admits a task that cannot produce its own declared outputs. The real
    damage is downstream: a correction repair is scoped to the *failing task's*
    expected artifacts, so when such a task fails the repair is aimed at files that were
    never the defect. In pf-39 a qa.test task declared the three view fill slots, the
    analyzer correctly diagnosed a backend status-code defect in another task's file,
    and the repair rewrote the views — an entire correction attempt that could not have
    fixed anything.
    """

    @staticmethod
    def _contract():
        from pathlib import Path

        from squadops.capabilities.scaffold import InterfaceManifest
        from squadops.capabilities.scaffold_contract import emit_contract_dict
        from squadops.cycles.verification_contract import VerificationContract

        path = (
            Path(__file__).resolve().parents[3]
            / "examples"
            / "03_group_run"
            / "interface_manifest.yaml"
        )
        manifest = InterfaceManifest.from_yaml(path.read_text(encoding="utf-8"))
        return VerificationContract.from_dict(emit_contract_dict(manifest))

    @staticmethod
    def _plan_with(task_type: str, artifact: str) -> ImplementationPlan:
        return ImplementationPlan.from_yaml(
            "version: 1\n"
            "project_id: group_run\n"
            "cycle_id: cyc_test\n"
            "prd_hash: abc123\n"
            "tasks:\n"
            "  - task_index: 0\n"
            f"    task_type: {task_type}\n"
            f"    role: {'qa' if task_type == 'qa.test' else 'dev'}\n"
            '    focus: "Frontend compilation and view sanity"\n'
            '    description: "check the views"\n'
            "    expected_artifacts:\n"
            f'      - "{artifact}"\n'
            "    depends_on: []\n"
            "summary:\n"
            "  total_dev_tasks: 0\n"
            "  total_qa_tasks: 1\n"
            "  total_tasks: 1\n"
            "  estimated_layers: []\n"
        )

    def test_rejects_qa_task_declaring_a_dev_fill_slot(self):
        """The exact pf-39 shape: qa.test declaring a view component."""
        errors = self._plan_with(
            "qa.test", "frontend/src/views/RunsListView.jsx"
        ).validate_qa_artifact_ownership(self._contract())

        assert len(errors) == 1
        assert "RunsListView.jsx" in errors[0]
        assert "fill slot (dev-owned)" in errors[0]

    def test_rejects_qa_task_declaring_a_frozen_scaffold_file(self):
        errors = self._plan_with("qa.test", "backend/main.py").validate_qa_artifact_ownership(
            self._contract()
        )

        assert len(errors) == 1
        assert "frozen (scaffold-owned)" in errors[0]

    def test_accepts_qa_task_declaring_its_own_test_file(self):
        """Must not over-reject: a QA task owning a test file is the normal case."""
        assert (
            self._plan_with("qa.test", "backend/tests/test_runs.py").validate_qa_artifact_ownership(
                self._contract()
            )
            == []
        )

    def test_dev_task_may_declare_a_fill_slot(self):
        """The rule is scoped to qa.test — a dev task owning routes.py is exactly
        how bind mode is supposed to work, and rejecting it would break every plan."""
        assert (
            self._plan_with(
                "development.develop", "backend/routes.py"
            ).validate_qa_artifact_ownership(self._contract())
            == []
        )


class TestFrozenArtifactOwnership:
    """#658: frozen files are claimable by nobody, regardless of role.

    fay-12's approved plan carried a ``development.develop`` task with
    ``expected_artifacts: [frontend/src/api.js]`` and prose-only criteria — it
    slipped between the qa.test ownership rule and the typed-criteria frozen
    rule. Scaffold enforcement restores frozen bytes at emission, so such a
    task can never satisfy its declared outputs through an accepted write.
    """

    _contract = staticmethod(TestQaArtifactOwnership._contract)
    _plan_with = staticmethod(TestQaArtifactOwnership._plan_with)

    def test_rejects_dev_task_declaring_a_frozen_file(self):
        """The exact fay-12 shape: dev claiming the frozen api client."""
        errors = self._plan_with(
            "development.develop", "frontend/src/api.js"
        ).validate_frozen_artifact_ownership(self._contract())

        assert len(errors) == 1
        assert "frontend/src/api.js" in errors[0]
        assert "frozen (scaffold-owned)" in errors[0]
        assert "development.develop" in errors[0]

    def test_rejects_builder_task_declaring_a_frozen_file(self):
        """Any role: the rule keys on the frozen surface, not the task type."""
        errors = self._plan_with(
            "builder.assemble", "backend/main.py"
        ).validate_frozen_artifact_ownership(self._contract())

        assert len(errors) == 1
        assert "backend/main.py" in errors[0]

    def test_dev_task_fill_slot_is_not_rejected(self):
        """Fill slots are dev-owned deliverables — claiming them is bind mode
        working as designed; rejecting them would break every plan."""
        assert (
            self._plan_with(
                "development.develop", "backend/routes.py"
            ).validate_frozen_artifact_ownership(self._contract())
            == []
        )

    def test_qa_task_is_not_double_reported(self):
        """qa.test frozen claims are the qa ownership rule's report — one
        defect must not produce two rejection lines."""
        assert (
            self._plan_with("qa.test", "backend/main.py").validate_frozen_artifact_ownership(
                self._contract()
            )
            == []
        )


class TestValidateModuleExistence:
    """#671: an error-severity import_present may not require a module the closed
    scaffold surface cannot provide.

    fay-17's approved framing-2 plan (cyc_e175cae83a6f, art_b12c08f02557)
    authored a blocking ``import_present: module: app.routes`` — no ``app``
    package exists, so satisfying the check guarantees a collection-dead suite
    while omitting it fails acceptance. A regression here means that exact plan
    would be admitted again. Scope is deliberately narrow (zero third-party
    false positives): only wrong-root hallucinations of real scaffold leaves
    and nonexistent submodules under a scaffold root reject; relative/dotless
    specs (#441 author-intent semantics, the contract's own ``.errors`` form)
    and third-party dotted modules stay out of scope, and
    ``harness_boundary.entry_modules`` is exempt — entries there are a
    FORBIDDEN-import list whose scaffold convention seeds nonexistent
    wrong-guess traps (``app.main``) on purpose.
    """

    _contract = staticmethod(TestQaArtifactOwnership._contract)

    @staticmethod
    def _fay_plan(name: str) -> ImplementationPlan:
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "fixtures" / "fay_plans" / name
        return ImplementationPlan.from_yaml(path.read_text(encoding="utf-8"))

    @staticmethod
    def _plan_with_import(module: str, severity: str = "error") -> ImplementationPlan:
        return ImplementationPlan.from_yaml(
            "version: 1\n"
            "project_id: group_run\n"
            "cycle_id: cyc_test\n"
            "prd_hash: abc123\n"
            "tasks:\n"
            "  - task_index: 0\n"
            "    task_type: qa.test\n"
            "    role: qa\n"
            '    focus: "Backend API pytest suite"\n'
            '    description: "exercise the routes"\n'
            "    expected_artifacts:\n"
            '      - "backend/tests/test_api.py"\n'
            "    acceptance_criteria:\n"
            '      - {check: import_present, file: "backend/tests/test_api.py", '
            f'module: "{module}", severity: "{severity}"}}\n'
            "    depends_on: []\n"
            "summary:\n"
            "  total_dev_tasks: 0\n"
            "  total_qa_tasks: 1\n"
            "  total_tasks: 1\n"
            "  estimated_layers: []\n"
        )

    def test_fay17_stored_plan_trips_on_app_routes(self):
        """Stored-artifact replay: the real fay-17 framing-2 plan must reject,
        solely on its task-4 ``app.routes`` import."""
        errors = self._fay_plan(
            "fay17_framing2_implementation_plan.yaml"
        ).validate_module_existence(self._contract())

        assert len(errors) == 1
        assert "Task 4" in errors[0]
        assert "'app.routes'" in errors[0]
        assert "scaffold surface does not provide" in errors[0]

    def test_wrong_root_hallucination_of_a_scaffold_leaf_rejected(self):
        """``app.routes``: the leaf is a real scaffold module, the root is not —
        the pf-26 wrong-package-root class as an authored check."""
        errors = self._plan_with_import("app.routes").validate_module_existence(self._contract())

        assert len(errors) == 1
        assert "'app.routes'" in errors[0]

    def test_nonexistent_submodule_under_scaffold_root_rejected(self):
        """``backend.handlers``: the scaffold owns everything under backend/, so
        the closed surface proves absence."""
        errors = self._plan_with_import("backend.handlers").validate_module_existence(
            self._contract()
        )

        assert len(errors) == 1
        assert "'backend.handlers'" in errors[0]

    @pytest.mark.parametrize(
        "module",
        [
            "backend.routes",  # surface module
            "conftest",  # dotless surface module
            "fastapi.testclient",  # third-party dotted: out of scope by design
            ".errors",  # relative — the contract authors this form itself
            "errors",  # dotless (#441 author-intent-relative)
            "pytest",  # dotless third-party
        ],
    )
    def test_legitimate_modules_accepted(self, module):
        """Must not over-reject: surface modules, relative/dotless specs, and
        third-party imports all pass — a false positive here would reject
        working plans (and the contract's own resolved criteria)."""
        assert self._plan_with_import(module).validate_module_existence(self._contract()) == []

    def test_warning_severity_tolerated(self):
        """RC-9 parity with the #645 rules: a warning check cannot block a build,
        so it must not kill the cycle at plan validation."""
        assert (
            self._plan_with_import("app.routes", severity="warning").validate_module_existence(
                self._contract()
            )
            == []
        )

    def test_fay16_entry_modules_are_exempt(self):
        """Stored-artifact replay pinning the narrowed scope: fay-16's plan
        (cyc_c51568b00b64) lists ``app.main`` in harness_boundary entry_modules
        at three sites — a forbidden-import list where nonexistent entries are
        protective, matching the scaffold's own ``_HARNESS_ENTRY_MODULES``
        convention. Existence-netting it would reject plans for copying the
        scaffold's own convention (see #671 scope note)."""
        assert (
            self._fay_plan("fay16_implementation_plan.yaml").validate_module_existence(
                self._contract()
            )
            == []
        )

    def test_fay19_clean_stored_plan_passes(self):
        """Stored-artifact replay: the window's cleanest accepted plan (green,
        cyc_96e72accb2b3 framing-2) must pass untouched."""
        assert (
            self._fay_plan("fay19_framing2_implementation_plan.yaml").validate_module_existence(
                self._contract()
            )
            == []
        )


class TestValidateUniqueExpectedArtifacts:
    """#673: an artifact path may appear in only one task's expected_artifacts.

    fay-18's approved framing-2 plan (cyc_42c44ad3af91) carried the live shape:
    qa task 5 declared dev task 4's ``backend/tests/test_runs.py`` with an
    explicit do-not-produce instruction. Benign that roll by luck — but a
    failing non-producing claimant aims its repair at another task's file, and
    dual producers hand the shipped suite to last-wins ordering (the #389
    class). A regression here means that exact plan would be admitted again.
    """

    _fay_plan = staticmethod(TestValidateModuleExistence._fay_plan)

    @staticmethod
    def _plan_with_artifacts(*artifact_lists: list[str]) -> ImplementationPlan:
        tasks = []
        for i, artifacts in enumerate(artifact_lists):
            entries = "".join(f'      - "{a}"\n' for a in artifacts)
            tasks.append(
                f"  - task_index: {i}\n"
                "    task_type: development.develop\n"
                "    role: dev\n"
                f'    focus: "Task {i}"\n'
                '    description: "build the thing"\n'
                + (
                    f"    expected_artifacts:\n{entries}"
                    if artifacts
                    else "    expected_artifacts: []\n"
                )
                + "    depends_on: []\n"
            )
        return ImplementationPlan.from_yaml(
            "version: 1\n"
            "project_id: group_run\n"
            "cycle_id: cyc_test\n"
            "prd_hash: abc123\n"
            "tasks:\n" + "".join(tasks) + "summary:\n"
            f"  total_dev_tasks: {len(artifact_lists)}\n"
            "  total_qa_tasks: 0\n"
            f"  total_tasks: {len(artifact_lists)}\n"
            "  estimated_layers: []\n"
        )

    def test_fay18_stored_plan_trips_on_the_dual_claim(self):
        """Stored-artifact replay: the real fay-18 framing-2 plan must reject,
        solely on tasks 4/5 both claiming the backend test suite."""
        errors = self._fay_plan(
            "fay18_framing2_implementation_plan.yaml"
        ).validate_unique_expected_artifacts()

        assert len(errors) == 1
        assert "Tasks 4 (Backend test suite) and 5" in errors[0]
        assert "'backend/tests/test_runs.py'" in errors[0]
        assert "criteria_refs" in errors[0]

    def test_fay19_clean_stored_plan_passes(self):
        """Stored-artifact replay: the window's cleanest accepted plan has
        disjoint artifact sets and must pass untouched."""
        assert (
            self._fay_plan(
                "fay19_framing2_implementation_plan.yaml"
            ).validate_unique_expected_artifacts()
            == []
        )

    def test_disjoint_artifacts_pass(self):
        assert (
            self._plan_with_artifacts(
                ["backend/routes.py"], ["backend/tests/test_api.py"], []
            ).validate_unique_expected_artifacts()
            == []
        )

    def test_three_way_claim_reports_one_error_naming_every_claimant(self):
        """One duplicated path is one defect — three claimants must not produce
        three rejection lines, and every claimant must be named so the re-roll
        knows which tasks to untangle."""
        errors = self._plan_with_artifacts(
            ["backend/tests/test_api.py"],
            ["backend/tests/test_api.py"],
            ["backend/tests/test_api.py"],
        ).validate_unique_expected_artifacts()

        assert len(errors) == 1
        assert "0 (Task 0) and 1 (Task 1) and 2 (Task 2)" in errors[0]

    def test_repeat_within_a_single_task_is_not_a_claim_conflict(self):
        """Scope pin: a path listed twice in ONE task's expected_artifacts is a
        benign echo (presence-checking is set-shaped), not a cross-task claim —
        flagging it would reject plans over a formatting slip."""
        assert (
            self._plan_with_artifacts(
                ["backend/routes.py", "backend/routes.py"]
            ).validate_unique_expected_artifacts()
            == []
        )


# ---------------------------------------------------------------------------
# #645: command-check executability + expected-artifact shape (FAY window)
# ---------------------------------------------------------------------------


def _qa_verification_plan(criteria_yaml: str, *, expected: str = '["backend/tests/test_x.py"]'):
    return ImplementationPlan.from_yaml(
        f"""\
version: 1
project_id: group_run
cycle_id: cyc_test
prd_hash: abc123
tasks:
  - task_index: 0
    task_type: qa.test
    role: qa
    focus: "Verification"
    description: "check things"
    expected_artifacts: {expected}
    acceptance_criteria:
{criteria_yaml}
    depends_on: []

summary:
  total_dev_tasks: 0
  total_qa_tasks: 1
  total_tasks: 1
"""
    )


class TestValidateCommandChecks:
    """#645: fay-2 was killed by a plan whose blocking checks could never run —
    `tsc` absent from the check environment, `node --check` on .jsx refused
    before parsing. Both are provable at authoring time; a validator rejection
    re-rolls framing for free where a human gate rejection ends the cycle."""

    def test_unknown_executable_rejected(self):
        plan = _qa_verification_plan(
            """\
      - check: command_exit_zero
        argv: [tsc, --noEmit]
"""
        )
        errors = plan.validate_command_checks()
        assert len(errors) == 1
        assert "'tsc'" in errors[0] and "never execute" in errors[0]

    def test_node_on_jsx_rejected_even_though_node_exists(self):
        plan = _qa_verification_plan(
            """\
      - check: command_exit_zero
        argv: [node, --check, frontend/src/views/RunsListView.jsx]
"""
        )
        errors = plan.validate_command_checks()
        assert len(errors) == 1
        assert "ERR_UNKNOWN_FILE_EXTENSION" in errors[0]

    def test_warning_severity_doomed_command_tolerated(self):
        # RC-9: a warning cannot block a build — fay-6/fay-8 carried exactly
        # this shape harmlessly and must keep passing validation.
        plan = _qa_verification_plan(
            """\
      - check: command_exit_zero
        argv: [node, --check, frontend/src/__tests__/runs.test.jsx]
        severity: warning
"""
        )
        assert plan.validate_command_checks() == []

    def test_legitimate_py_compile_command_passes(self):
        # fay-5/fay-7/fay-9 all used this exact shape correctly.
        plan = _qa_verification_plan(
            """\
      - check: command_exit_zero
        argv: [python, -m, py_compile, backend/tests/test_x.py]
"""
        )
        assert plan.validate_command_checks() == []

    def test_node_on_plain_js_passes(self):
        plan = _qa_verification_plan(
            """\
      - check: command_exit_zero
        argv: [node, --check, frontend/src/api.js]
"""
        )
        assert plan.validate_command_checks() == []


class TestValidateExpectedArtifactShapes:
    """fay-9: rejected 16/17 solely because a verification-only task declared
    expected_artifacts: ['backend/tests/'] and the presence check read the
    directory as a permanently missing file."""

    def test_directory_entry_rejected(self):
        plan = _qa_verification_plan(
            """\
      - check: count_at_least
        glob: backend/tests/test_*.py
        min_count: 2
""",
            expected='["backend/tests/"]',
        )
        errors = plan.validate_expected_artifact_shapes()
        assert len(errors) == 1
        assert "'backend/tests/'" in errors[0] and "expected_artifacts: []" in errors[0]

    def test_file_entries_and_empty_list_pass(self):
        plan = ImplementationPlan.from_yaml(VALID_MANIFEST_YAML)
        assert plan.validate_expected_artifact_shapes() == []
        empty = _qa_verification_plan(
            """\
      - check: count_at_least
        glob: backend/tests/test_*.py
        min_count: 2
""",
            expected="[]",
        )
        assert empty.validate_expected_artifact_shapes() == []
