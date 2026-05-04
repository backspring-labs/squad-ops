"""SIP-0092 M1.3 — typed-acceptance integration into _validate_focused.

Covers RC-9 (severity × status blocking matrix), RC-9a (error-vs-failed
wording in missing_components), RC-9b (per-criterion error count with
2-strikes escalation), and RC-12a (skipped-not-error for unset stack).
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.cycle_tasks import DevelopmentDevelopHandler
from squadops.cycles.implementation_plan import TypedCheck

pytestmark = [pytest.mark.domain_capabilities]


def _art(name: str, content: str = "x" * 200) -> dict:
    return {"name": name, "content": content, "media_type": "text/plain", "type": "code"}


def _inputs(criteria, *, expected=("main.py",), focus="Test", config=None):
    return {
        "subtask_focus": focus,
        "expected_artifacts": list(expected),
        "acceptance_criteria": list(criteria),
        "resolved_config": dict(config or {}),
    }


# ---------------------------------------------------------------------------
# Severity × status blocking matrix (RC-9)
# ---------------------------------------------------------------------------


_FASTAPI_ALL = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def list_users():
    return []
"""

_FASTAPI_MISSING = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/users")
def list_users():
    return []
"""  # missing POST /users


_PROSE_CRITERION = "User CRUD endpoints are present"


class TestSeverityStatusMatrix:
    """RC-9: severity AND status are independent — only error+blocking gates."""

    async def test_severity_error_status_passed_does_not_block(self, tmp_path):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users"]},
            severity="error",
            description="users endpoint",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"stack": "fastapi"}),
            [_art("main.py", _FASTAPI_ALL)],
        )
        assert result.passed is True
        assert all("acceptance:" not in m for m in result.missing_components)

    async def test_severity_error_status_failed_blocks(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users", "POST /users"]},
            severity="error",
            description="users CRUD",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"stack": "fastapi"}),
            [_art("main.py", _FASTAPI_MISSING)],
        )
        assert result.passed is False
        # RC-9a: app-incompleteness wording, with the description.
        assert "acceptance:users CRUD" in result.missing_components

    async def test_severity_warning_status_failed_does_not_block(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users", "POST /users"]},
            severity="warning",
            description="ideal CRUD",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"stack": "fastapi"}),
            [_art("main.py", _FASTAPI_MISSING)],
        )
        assert result.passed is True
        assert all("acceptance:" not in m for m in result.missing_components)
        # But the failed evaluation appears in checks for evidence visibility.
        typed_checks = [c for c in result.checks if c.get("check") == "acceptance:endpoint_defined"]
        assert len(typed_checks) == 1
        assert typed_checks[0]["status"] == "failed"

    async def test_severity_info_status_failed_does_not_block(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "totally_absent", "count_min": 1},
            severity="info",
        )
        result = await h._validate_output(
            _inputs([criterion]),
            [_art("main.py", "no match here\n")],
        )
        assert result.passed is True

    async def test_severity_error_status_skipped_does_not_block(self):
        # endpoint_defined requires stack=fastapi; with stack unset the
        # evaluator returns skipped per RC-12a, never an error.
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /x"]},
            severity="error",
        )
        result = await h._validate_output(
            _inputs([criterion]),  # no stack
            [_art("main.py", _FASTAPI_ALL)],
        )
        assert result.passed is True
        typed_checks = [c for c in result.checks if c.get("check") == "acceptance:endpoint_defined"]
        assert typed_checks[0]["status"] == "skipped"
        assert typed_checks[0]["reason"] == "unsupported_stack_or_syntax"


# ---------------------------------------------------------------------------
# RC-9a — error vs failed wording in missing_components
# ---------------------------------------------------------------------------


class TestErrorVsFailedWording:
    async def test_failed_uses_acceptance_prefix(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "absent_marker", "count_min": 1},
            severity="error",
            description="marker present",
        )
        result = await h._validate_output(
            _inputs([criterion]),
            [_art("main.py", "no match\n")],
        )
        assert "acceptance:marker present" in result.missing_components
        # Sanity: not an evaluator-error.
        assert all(not m.startswith("evaluator-error:") for m in result.missing_components)

    async def test_evaluator_error_uses_evaluator_error_prefix(self):
        # command_exit_zero with argv outside the safelist → status=error.
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["python", "-c", "print(1)"]},
            severity="error",
        )
        result = await h._validate_output(
            _inputs([criterion]),
            [_art("main.py")],
        )
        assert any(
            m.startswith("evaluator-error:command_exit_zero:") for m in result.missing_components
        )
        # Not the app-incompleteness phrasing.
        assert all(not m.startswith("acceptance:") for m in result.missing_components)


# ---------------------------------------------------------------------------
# RC-9b — per-criterion error count + 2-strikes escalation
# ---------------------------------------------------------------------------


class TestPerCriterionErrorEscalation:
    async def test_first_two_errors_surface_third_drops_from_feedback(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["python", "-c", "print(1)"]},
            severity="error",
        )
        counts: dict[str, int] = {}
        artifacts = [_art("main.py")]

        # Pass 1 — first error → surfaced in missing_components.
        r1 = await h._validate_output(_inputs([criterion]), artifacts, typed_error_counts=counts)
        assert any(m.startswith("evaluator-error:") for m in r1.missing_components)

        # Pass 2 — second error → still surfaced.
        r2 = await h._validate_output(_inputs([criterion]), artifacts, typed_error_counts=counts)
        assert any(m.startswith("evaluator-error:") for m in r2.missing_components)

        # Pass 3 — third error → dropped from feedback (escalated separately).
        r3 = await h._validate_output(_inputs([criterion]), artifacts, typed_error_counts=counts)
        assert all(not m.startswith("evaluator-error:") for m in r3.missing_components)

        # Counter advanced once per pass.
        assert sum(counts.values()) == 3

    async def test_distinct_criteria_have_distinct_counters(self):
        h = DevelopmentDevelopHandler()
        c1 = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["python", "-c", "1"]},
            severity="error",
        )
        c2 = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["python", "-c", "2"]},
            severity="error",
        )
        counts: dict[str, int] = {}
        artifacts = [_art("main.py")]

        await h._validate_output(_inputs([c1]), artifacts, typed_error_counts=counts)
        await h._validate_output(_inputs([c2]), artifacts, typed_error_counts=counts)
        await h._validate_output(_inputs([c1]), artifacts, typed_error_counts=counts)

        # c1 saw 2 errors; c2 saw 1; total 3.
        assert len(counts) == 2
        assert sum(counts.values()) == 3


# ---------------------------------------------------------------------------
# Config gates
# ---------------------------------------------------------------------------


class TestConfigGates:
    async def test_typed_acceptance_disabled_skips_all_typed(self):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "absent", "count_min": 1},
            severity="error",
            description="x",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"typed_acceptance": False}),
            [_art("main.py", "no match")],
        )
        assert result.passed is True
        typed = [c for c in result.checks if c.get("check") == "acceptance:regex_match"]
        assert typed[0]["status"] == "skipped"
        assert typed[0]["reason"] == "typed_acceptance_disabled"

    async def test_command_acceptance_disabled_skips_only_commands(self):
        h = DevelopmentDevelopHandler()
        cmd = TypedCheck(
            check="command_exit_zero",
            params={"argv": ["pyflakes", "main.py"]},
            severity="error",
        )
        regex = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "absent", "count_min": 1},
            severity="error",
            description="r",
        )
        result = await h._validate_output(
            _inputs([cmd, regex], config={"command_acceptance_checks": False}),
            [_art("main.py", "no match")],
        )
        cmd_check = [c for c in result.checks if c["check"] == "acceptance:command_exit_zero"][0]
        regex_check = [c for c in result.checks if c["check"] == "acceptance:regex_match"][0]
        assert cmd_check["status"] == "skipped"
        assert cmd_check["reason"] == "command_acceptance_checks_disabled"
        # Regex still evaluates and fails.
        assert regex_check["status"] == "failed"
        assert "acceptance:r" in result.missing_components


# ---------------------------------------------------------------------------
# Prose criteria preserved as informational
# ---------------------------------------------------------------------------


class TestProseCriteriaInformational:
    async def test_prose_strings_never_block(self):
        h = DevelopmentDevelopHandler()
        result = await h._validate_output(
            _inputs([_PROSE_CRITERION]),
            [_art("main.py")],
        )
        assert result.passed is True
        prose_check = [c for c in result.checks if c["check"] == "acceptance_criteria_prose"][0]
        assert prose_check["criteria"] == [_PROSE_CRITERION]
        assert prose_check["evaluation"] == "included_in_evidence"

    async def test_mixed_prose_and_typed_only_typed_can_block(self):
        h = DevelopmentDevelopHandler()
        prose = _PROSE_CRITERION
        typed = TypedCheck(
            check="regex_match",
            params={"file": "main.py", "pattern": "absent", "count_min": 1},
            severity="error",
            description="x",
        )
        result = await h._validate_output(
            _inputs([prose, typed]),
            [_art("main.py", "no match")],
        )
        assert result.passed is False
        # Prose check still recorded as informational.
        prose_check = [c for c in result.checks if c["check"] == "acceptance_criteria_prose"][0]
        assert prose_check["passed"] is True


# ---------------------------------------------------------------------------
# TypedCheck.fingerprint() invariants
# ---------------------------------------------------------------------------


class TestFingerprint:
    def test_same_shape_same_fingerprint(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, severity="error")
        c2 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, severity="error")
        assert c1.fingerprint() == c2.fingerprint()

    def test_description_does_not_affect_fingerprint(self):
        c1 = TypedCheck(
            check="regex_match", params={"file": "a", "pattern": "x"}, description="one"
        )
        c2 = TypedCheck(
            check="regex_match", params={"file": "a", "pattern": "x"}, description="two"
        )
        assert c1.fingerprint() == c2.fingerprint()

    def test_param_change_changes_fingerprint(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"})
        c2 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "y"})
        assert c1.fingerprint() != c2.fingerprint()

    def test_severity_change_changes_fingerprint(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"}, severity="error")
        c2 = TypedCheck(
            check="regex_match", params={"file": "a", "pattern": "x"}, severity="warning"
        )
        assert c1.fingerprint() != c2.fingerprint()

    def test_param_key_order_does_not_matter(self):
        c1 = TypedCheck(check="regex_match", params={"file": "a", "pattern": "x"})
        c2 = TypedCheck(check="regex_match", params={"pattern": "x", "file": "a"})
        assert c1.fingerprint() == c2.fingerprint()


# ---------------------------------------------------------------------------
# Issue #83 — M1.3 observability: log per-check + per-validation summary
# ---------------------------------------------------------------------------


class TestM13Observability:
    """Verify _evaluate_typed_acceptance + _validate_focused emit log lines
    operators can grep for. Without these the M1.3 path is invisible.
    """

    async def test_per_check_log_emitted_on_pass(self, caplog):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users"]},
            severity="error",
            description="users endpoint",
        )
        with caplog.at_level("DEBUG", logger="squadops.capabilities.handlers.cycle_tasks"):
            await h._validate_output(
                _inputs([criterion], config={"stack": "fastapi"}),
                [_art("main.py", _FASTAPI_ALL)],
            )
        check_logs = [r for r in caplog.records if "typed_acceptance_check" in r.getMessage()]
        assert len(check_logs) == 1
        msg = check_logs[0].getMessage()
        assert "check=endpoint_defined" in msg
        assert "severity=error" in msg
        assert "status=passed" in msg
        assert "blocking=False" in msg

    async def test_per_check_log_marks_blocking_failure_at_info_level(self, caplog):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users", "POST /users"]},
            severity="error",
            description="users CRUD",
        )
        with caplog.at_level("INFO", logger="squadops.capabilities.handlers.cycle_tasks"):
            await h._validate_output(
                _inputs([criterion], config={"stack": "fastapi"}),
                [_art("main.py", _FASTAPI_MISSING)],
            )
        check_logs = [
            r
            for r in caplog.records
            if "typed_acceptance_check" in r.getMessage() and r.levelname == "INFO"
        ]
        assert len(check_logs) == 1
        msg = check_logs[0].getMessage()
        assert "status=failed" in msg
        assert "blocking=True" in msg

    async def test_summary_log_emitted_when_typed_checks_present(self, caplog):
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users"]},
            severity="error",
        )
        with caplog.at_level("INFO", logger="squadops.capabilities.handlers.cycle_tasks"):
            await h._validate_output(
                _inputs([criterion], focus="check focus", config={"stack": "fastapi"}),
                [_art("main.py", _FASTAPI_ALL)],
            )
        summary_logs = [r for r in caplog.records if "typed_acceptance_summary" in r.getMessage()]
        assert len(summary_logs) == 1
        msg = summary_logs[0].getMessage()
        assert "evaluated=1" in msg
        assert "passed=1" in msg
        assert "blocking_failures=0" in msg
        assert "overall_passed=True" in msg

    async def test_summary_log_skipped_when_no_typed_checks(self, caplog):
        # Prose-only criteria → summary log should NOT fire (it would be noise).
        h = DevelopmentDevelopHandler()
        with caplog.at_level("INFO", logger="squadops.capabilities.handlers.cycle_tasks"):
            await h._validate_output(
                _inputs([_PROSE_CRITERION], config={"stack": "fastapi"}),
                [_art("main.py", _FASTAPI_ALL)],
            )
        summary_logs = [r for r in caplog.records if "typed_acceptance_summary" in r.getMessage()]
        assert len(summary_logs) == 0


class TestEvaluationIdentityFields:
    """Issue #114: each typed-check evaluation row in validation.checks must
    carry task_index + check_index so downstream consumers (plan_delta
    trigger composer, gate evaluator) can pair outcome ↔ originating check
    without relying on positional inference from prose."""

    async def test_check_record_carries_task_index_and_check_index(self):
        h = DevelopmentDevelopHandler()
        criteria = [
            TypedCheck(
                check="endpoint_defined",
                params={"file": "main.py", "methods_paths": ["GET /users"]},
                severity="error",
                description="users get",
            ),
            TypedCheck(
                check="endpoint_defined",
                params={"file": "main.py", "methods_paths": ["POST /users"]},
                severity="error",
                description="users post",
            ),
        ]
        inputs = _inputs(criteria, config={"stack": "fastapi"})
        inputs["subtask_index"] = 4
        result = await h._validate_output(inputs, [_art("main.py", _FASTAPI_ALL)])

        typed = [c for c in result.checks if c.get("check", "").startswith("acceptance:")]
        assert len(typed) == 2
        # Both rows attribute to the same task; check_index distinguishes them.
        assert all(c["task_index"] == 4 for c in typed)
        assert [c["check_index"] for c in typed] == [0, 1]

    async def test_task_index_is_none_when_subtask_index_absent(self):
        # Legacy monolithic flow has no subtask_index on the inputs payload.
        # Identity must still be present (None task_index) so the trigger
        # composer can fall through to the legacy shape without crashing.
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users"]},
            severity="error",
        )
        result = await h._validate_output(
            _inputs([criterion], config={"stack": "fastapi"}),
            [_art("main.py", _FASTAPI_ALL)],
        )
        typed = [c for c in result.checks if c.get("check", "").startswith("acceptance:")]
        assert typed[0]["task_index"] is None
        assert typed[0]["check_index"] == 0


class TestTypedCheckEvaluationArtifactBuilder:
    """Issue #114: the static artifact builder is what surfaces evaluator
    outcomes to the per-cycle gate evaluator. Tested in isolation here;
    end-to-end emission is covered in handler integration tests."""

    def test_returns_none_when_no_typed_checks(self):
        # Monolithic-flow checks (e.g. stack_coverage_heuristic) must NOT
        # produce a typed_check_evaluation artifact — the artifact's purpose
        # is to surface acceptance:* evaluator outcomes, not legacy
        # heuristics. Emitting an empty/wrong-shape artifact would force
        # the gate evaluator to filter at read time.
        artifact = DevelopmentDevelopHandler._build_typed_check_evaluation_artifact(
            [
                {"check": "stack_coverage_heuristic", "passed": True},
                {"check": "artifact_count_heuristic", "passed": True},
            ],
            task_index=0,
            task_type="development.develop",
        )
        assert artifact is None

    def test_returns_none_for_empty_checks_list(self):
        artifact = DevelopmentDevelopHandler._build_typed_check_evaluation_artifact(
            [], task_index=0, task_type="development.develop"
        )
        assert artifact is None

    def test_emits_artifact_when_typed_checks_present(self):
        rows = [
            {
                "check": "acceptance:regex_match",
                "severity": "error",
                "params": {"file": "qa_handoff.md", "pattern": "## Expected Behavior"},
                "description": "Has Expected Behavior section",
                "status": "failed",
                "actual": {"count": 0, "expected_min": 1},
                "reason": "pattern not found",
                "passed": False,
                "task_index": 5,
                "check_index": 2,
            },
        ]
        artifact = DevelopmentDevelopHandler._build_typed_check_evaluation_artifact(
            rows, task_index=5, task_type="builder.assemble"
        )
        assert artifact is not None
        assert artifact["name"] == "typed_check_evaluation_task_5.json"
        assert artifact["type"] == "typed_check_evaluation"
        assert artifact["media_type"] == "application/json"

        import json as _json

        payload = _json.loads(artifact["content"])
        assert payload["version"] == 1
        assert payload["task_index"] == 5
        assert payload["task_type"] == "builder.assemble"
        assert "evaluated_at" in payload
        assert payload["evaluations"][0]["status"] == "failed"
        assert payload["evaluations"][0]["check"] == "acceptance:regex_match"

    def test_filename_omits_task_suffix_when_index_unknown(self):
        # Legacy flow without subtask_index — artifact still emits, just
        # without the per-task suffix (no second-task collision possible
        # in legacy flow because there's only one task).
        rows = [
            {
                "check": "acceptance:regex_match",
                "severity": "error",
                "passed": True,
                "status": "passed",
                "task_index": None,
                "check_index": 0,
            }
        ]
        artifact = DevelopmentDevelopHandler._build_typed_check_evaluation_artifact(
            rows, task_index=None, task_type="development.develop"
        )
        assert artifact is not None
        assert artifact["name"] == "typed_check_evaluation.json"

    def test_artifact_distinguishes_evaluator_error_from_app_failure(self):
        # RC-9a: status=error means evaluator broke; status=failed means
        # the app didn't meet the criterion. The gate's C1 measures the
        # former. The artifact must preserve the distinction.
        rows = [
            {
                "check": "acceptance:regex_match",
                "severity": "error",
                "status": "error",
                "reason": "regex compilation failed",
                "passed": False,
                "task_index": 0,
                "check_index": 0,
            },
            {
                "check": "acceptance:regex_match",
                "severity": "error",
                "status": "failed",
                "reason": "pattern not matched",
                "passed": False,
                "task_index": 0,
                "check_index": 1,
            },
        ]
        artifact = DevelopmentDevelopHandler._build_typed_check_evaluation_artifact(
            rows, task_index=0, task_type="development.develop"
        )
        import json as _json

        payload = _json.loads(artifact["content"])
        statuses = [e["status"] for e in payload["evaluations"]]
        assert statuses == ["error", "failed"]


class TestArtifactEmissionEndToEnd:
    """Issue #114: end-to-end — running _validate_output with typed checks
    surfaces the evaluation artifact. This is the regression guard against
    a refactor that detaches the builder from the validation flow."""

    async def test_validate_output_does_not_emit_artifact_directly(self):
        # _validate_output returns ValidationResult; artifact emission
        # happens at the handler.handle() level where artifacts are
        # appended to the outputs list. This test pins that contract:
        # _validate_output produces the data; the handler wires it.
        h = DevelopmentDevelopHandler()
        criterion = TypedCheck(
            check="endpoint_defined",
            params={"file": "main.py", "methods_paths": ["GET /users"]},
            severity="error",
        )
        inputs = _inputs([criterion], config={"stack": "fastapi"})
        inputs["subtask_index"] = 1
        result = await h._validate_output(inputs, [_art("main.py", _FASTAPI_ALL)])
        # The check rows are present and self-identifying.
        typed = [c for c in result.checks if c.get("check", "").startswith("acceptance:")]
        assert len(typed) == 1
        # And the helper builds an artifact from them.
        artifact = h._build_typed_check_evaluation_artifact(
            result.checks, inputs["subtask_index"], h._capability_id
        )
        assert artifact is not None
        assert artifact["name"] == "typed_check_evaluation_task_1.json"
