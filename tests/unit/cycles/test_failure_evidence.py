"""Tests for squadops/cycles/failure_evidence.py.

Moved verbatim from test_dispatched_flow_executor.py in SIP-0097 slice 1
(the functions hoisted from DispatchedFlowExecutor staticmethods to the
domain module); only the call syntax changed — assertions are unmodified.
"""

from __future__ import annotations

import pytest

from squadops.cycles.failure_evidence import (
    FailureLocus,
    build_failure_evidence,
    classify_failure_locus,
    compose_failure_trigger,
)
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_orchestration]


class TestBuildFailureEvidence:
    """Issue #84 follow-up: the executor must hand data.analyze_failure
    a structured payload that surfaces validation_result, the failed
    handler's preliminary classification, and per-artifact content
    snippets — without these, downstream correction-decision picks
    rewind on patchable content failures (cyc_4178f25a0dff delta_2 →
    cyc_d1c1a259c983 delta_0 had to guess the failure shape)."""

    def _envelope(self, task_type: str) -> TaskEnvelope:
        return TaskEnvelope(
            task_id="t-7",
            agent_id="bob",
            cycle_id="cyc_x",
            pulse_id="pulse",
            project_id="proj",
            task_type=task_type,
            correlation_id="corr",
            causation_id=None,
            trace_id="trace",
            span_id="span",
            inputs={},
            metadata={},
        )

    def _result(self, error: str | None, outputs: dict) -> TaskResult:
        return TaskResult(
            task_id="t-7",
            status="FAILED" if error else "SUCCEEDED",
            outputs=outputs,
            error=error,
        )

    def test_includes_validation_result_when_present(self):
        envelope = self._envelope("builder.assemble")
        result = self._result(
            "validation failed",
            {
                "outcome_class": "semantic_failure",
                "failure_classification": "work_product",
                "validation_result": {
                    "passed": False,
                    "summary": "1 typed check failed",
                    "missing_components": ["qa_handoff.md::## How to run backend"],
                    "checks": [{"name": "regex:how to run backend", "status": "failed"}],
                },
                "artifacts": [],
            },
        )

        evidence = build_failure_evidence(envelope, result, prior_plan_deltas_count=0)

        assert evidence["validation_result"]["passed"] is False
        assert evidence["validation_result"]["missing_components"] == [
            "qa_handoff.md::## How to run backend"
        ]
        assert evidence["validation_result"]["checks"][0]["status"] == "failed"
        assert evidence["preliminary_failure_classification"] == "work_product"

    def test_truncates_artifact_content_snippets_to_1500_chars(self):
        envelope = self._envelope("development.develop")
        big = "x" * 5000
        result = self._result(
            "validation failed",
            {
                "artifacts": [
                    {"name": "huge.py", "type": "source", "content": big},
                    {"name": "small.py", "type": "source", "content": "ok"},
                ]
            },
        )

        evidence = build_failure_evidence(envelope, result, prior_plan_deltas_count=2)

        rejected = evidence["rejected_artifacts"]
        assert rejected[0]["name"] == "huge.py"
        assert rejected[0]["size"] == 5000  # original size preserved
        assert len(rejected[0]["content_snippet"]) == 1500  # snippet truncated
        assert rejected[1]["content_snippet"] == "ok"
        assert evidence["prior_plan_deltas_count"] == 2

    def test_handles_empty_outputs_without_crashing(self):
        # Failed handler that returned no outputs at all (e.g. crashed
        # before assembling anything) — analyze_failure must still get a
        # well-formed envelope, not a KeyError downstream.
        envelope = self._envelope("development.develop")
        result = TaskResult(task_id="t-7", status="FAILED", outputs=None, error="connection reset")

        evidence = build_failure_evidence(envelope, result, prior_plan_deltas_count=0)

        assert evidence["error"] == "connection reset"
        assert evidence["outcome_class"] == ""
        assert evidence["preliminary_failure_classification"] == ""
        assert evidence["validation_result"] == {
            "passed": None,
            "summary": "",
            "missing_components": [],
            "checks": [],
        }
        assert evidence["rejected_artifacts"] == []


class TestComposeFailureTrigger:
    """Issue #114: plan_delta `trigger` must identify the specific typed-
    check failure when one tripped, so the SIP-0092 gate evaluator can
    attribute corrections to specific checks instead of inferring from
    prose. Non-typed-check failures (LLM crash, RabbitMQ timeout) keep the
    legacy `task_failure:<task_type>` shape so consumers handle both."""

    @staticmethod
    def _envelope(task_type: str = "builder.assemble") -> TaskEnvelope:
        return TaskEnvelope(
            task_id="t-9",
            agent_id="bob",
            cycle_id="cyc_x",
            pulse_id="pulse",
            project_id="proj",
            task_type=task_type,
            correlation_id="corr",
            causation_id=None,
            trace_id="trace",
            span_id="span",
            inputs={},
            metadata={},
        )

    def _evidence(self, checks: list[dict]) -> dict:
        return {
            "validation_result": {
                "passed": False,
                "checks": checks,
            }
        }

    def test_typed_check_failure_emits_extended_trigger(self):
        evidence = self._evidence(
            [
                {
                    "check": "acceptance:regex_match",
                    "severity": "error",
                    "status": "failed",
                    "passed": False,
                    "task_index": 5,
                    "check_index": 2,
                },
            ]
        )
        trigger = compose_failure_trigger(self._envelope("builder.assemble"), evidence)
        assert trigger == "typed_check_failed:builder.assemble:5:2"

    def test_no_failed_checks_falls_back_to_legacy_shape(self):
        # All typed checks passed but task still failed — e.g. tests_pass
        # synthetic check tripped, or the task crashed after validation.
        # Trigger must fall through to the legacy shape; no malformed
        # extended trigger.
        evidence = self._evidence(
            [
                {
                    "check": "acceptance:regex_match",
                    "severity": "error",
                    "status": "passed",
                    "passed": True,
                    "task_index": 5,
                    "check_index": 0,
                },
            ]
        )
        trigger = compose_failure_trigger(self._envelope("development.develop"), evidence)
        assert trigger == "task_failure:development.develop"

    def test_non_typed_check_failure_uses_legacy_shape(self):
        # Validation_result.checks contains only non-acceptance entries
        # (e.g. tests_pass, stack_coverage_heuristic). These never gate
        # the extended trigger — only acceptance:* rows do.
        evidence = self._evidence(
            [
                {"check": "tests_pass", "passed": False},
                {"check": "stack_coverage_heuristic", "passed": False},
            ]
        )
        trigger = compose_failure_trigger(self._envelope("qa.test"), evidence)
        assert trigger == "task_failure:qa.test"

    def test_warning_severity_failure_uses_legacy_shape(self):
        # severity=warning is informational; even a status=failed warning
        # must not promote to typed_check_failed: trigger, because the
        # gate's C2 measures *blocking* typed-check trips.
        evidence = self._evidence(
            [
                {
                    "check": "acceptance:regex_match",
                    "severity": "warning",
                    "status": "failed",
                    "passed": True,  # severity=warning never gates; passed flag stays True
                    "task_index": 0,
                    "check_index": 0,
                },
            ]
        )
        trigger = compose_failure_trigger(self._envelope("builder.assemble"), evidence)
        assert trigger == "task_failure:builder.assemble"

    def test_first_failing_check_wins_when_multiple(self):
        evidence = self._evidence(
            [
                {
                    "check": "acceptance:endpoint_defined",
                    "severity": "error",
                    "status": "passed",
                    "passed": True,
                    "task_index": 1,
                    "check_index": 0,
                },
                {
                    "check": "acceptance:regex_match",
                    "severity": "error",
                    "status": "failed",
                    "passed": False,
                    "task_index": 1,
                    "check_index": 1,
                },
                {
                    "check": "acceptance:regex_match",
                    "severity": "error",
                    "status": "failed",
                    "passed": False,
                    "task_index": 1,
                    "check_index": 2,
                },
            ]
        )
        trigger = compose_failure_trigger(self._envelope("builder.assemble"), evidence)
        assert trigger == "typed_check_failed:builder.assemble:1:1"

    def test_missing_task_index_falls_back_to_legacy(self):
        # Legacy data without identity fields (pre-#114 cycle reruns
        # mid-rollout) — fall through to legacy rather than emit a
        # `typed_check_failed:...:None:None` string downstream consumers
        # would have to special-case.
        evidence = self._evidence(
            [
                {
                    "check": "acceptance:regex_match",
                    "severity": "error",
                    "status": "failed",
                    "passed": False,
                    # task_index/check_index intentionally absent
                },
            ]
        )
        trigger = compose_failure_trigger(self._envelope("builder.assemble"), evidence)
        assert trigger == "task_failure:builder.assemble"

    def test_empty_evidence_falls_back_to_legacy(self):
        trigger = compose_failure_trigger(self._envelope("development.develop"), {})
        assert trigger == "task_failure:development.develop"

    def test_malformed_check_row_skipped_safely(self):
        # Defensive: a row that's not a dict (corrupt validation_result)
        # must not crash the trigger composer. Fall through to legacy.
        evidence = self._evidence(["not a dict", None, 42])  # type: ignore[list-item]
        trigger = compose_failure_trigger(self._envelope("qa.test"), evidence)
        assert trigger == "task_failure:qa.test"


class TestClassifyFailureLocus:
    """#568: deterministic locus classification — the routing key that decides
    whether a failed task's own role re-authors its artifact or the default
    (dev) chain repairs the subject. Conservative: ambiguity → UNKNOWN."""

    def _evidence_with_check(self, row):
        return {"validation_result": {"passed": False, "checks": [row]}}

    def test_emission_failure_marker_is_own_artifact(self):
        evidence = {"emission_failure": {"reason": "no_fenced_blocks", "response_chars": 6203}}
        assert classify_failure_locus(evidence) == FailureLocus.OWN_ARTIFACT

    def test_missing_expected_artifacts_is_own_artifact(self):
        row = {
            "check": "expected_artifacts",
            "missing": ["backend/tests/test_runs.py"],
            "passed": False,
        }
        assert classify_failure_locus(self._evidence_with_check(row)) == FailureLocus.OWN_ARTIFACT

    @pytest.mark.parametrize("exit_code", [2, 5])
    def test_suite_defect_exit_codes_are_own_artifact(self, exit_code):
        """pytest 2=collection error in the test files, 5=no tests collected:
        the suite itself cannot run as a suite — the test artifact is the defect
        (pf-31's truncated-test collection crash lands here)."""
        row = {"check": "tests_pass", "executed": True, "exit_code": exit_code, "passed": False}
        assert classify_failure_locus(self._evidence_with_check(row)) == FailureLocus.OWN_ARTIFACT

    def test_exit_one_is_subject(self):
        """Tests ran and failed — the app is implicated, NEVER the qa re-author
        route (the test-gaming guard: rewriting tests to green a broken app)."""
        row = {"check": "tests_pass", "executed": True, "exit_code": 1, "passed": False}
        assert classify_failure_locus(self._evidence_with_check(row)) == FailureLocus.SUBJECT

    def test_pytest_internal_error_is_unknown(self):
        row = {"check": "tests_pass", "executed": True, "exit_code": 3, "passed": False}
        assert classify_failure_locus(self._evidence_with_check(row)) == FailureLocus.UNKNOWN

    def test_exit_four_is_unknown_dev_chain(self):
        """pf-35 corr-01/02 regression: exit 4 (usage error) is AMBIGUOUS — a
        conftest/app-import failure (accepted routes.py importing names the
        frozen models.py never defined) surfaces as exit 4, and own-artifact
        classification sent the qa role to re-author a suite that could never
        fix the app's import. Ambiguity falls to the dev chain."""
        row = {"check": "tests_pass", "executed": True, "exit_code": 4, "passed": False}
        assert classify_failure_locus(self._evidence_with_check(row)) == FailureLocus.UNKNOWN

    def test_not_executed_suite_is_unknown(self):
        """Runner/environment failures implicate neither artifact nor subject."""
        row = {"check": "tests_pass", "executed": False, "exit_code": None, "passed": False}
        assert classify_failure_locus(self._evidence_with_check(row)) == FailureLocus.UNKNOWN

    def test_passed_rows_and_junk_are_unknown(self):
        assert classify_failure_locus(None) == FailureLocus.UNKNOWN
        assert classify_failure_locus({}) == FailureLocus.UNKNOWN
        row = {"check": "tests_pass", "executed": True, "exit_code": 1, "passed": True}
        assert classify_failure_locus(self._evidence_with_check(row)) == FailureLocus.UNKNOWN


class TestEmissionFailurePassthrough:
    """#566/#568: the zero-extraction marker must travel into failure evidence
    so the analyzer and the locus classifier see a machine fact."""

    @staticmethod
    def _envelope() -> TaskEnvelope:
        return TaskEnvelope(
            task_id="t1",
            agent_id="eve",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="proj",
            task_type="qa.test",
            correlation_id="c",
            causation_id=None,
            trace_id="tr",
            span_id="sp",
            inputs={},
            metadata={"role": "qa"},
        )

    def test_marker_passes_through(self):
        result = TaskResult(
            task_id="t1",
            status="FAILED",
            error="No valid fenced code blocks found",
            outputs={"emission_failure": {"reason": "no_fenced_blocks", "response_chars": 42}},
        )
        evidence = build_failure_evidence(self._envelope(), result, prior_plan_deltas_count=0)
        assert evidence["emission_failure"] == {"reason": "no_fenced_blocks", "response_chars": 42}

    def test_absent_marker_stays_absent(self):
        result = TaskResult(task_id="t1", status="FAILED", error="x", outputs={})
        evidence = build_failure_evidence(self._envelope(), result, prior_plan_deltas_count=0)
        assert "emission_failure" not in evidence
