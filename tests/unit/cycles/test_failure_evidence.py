"""Tests for squadops/cycles/failure_evidence.py.

Moved verbatim from test_dispatched_flow_executor.py in SIP-0097 slice 1
(the functions hoisted from DispatchedFlowExecutor staticmethods to the
domain module); only the call syntax changed — assertions are unmodified.
"""

from __future__ import annotations

import pytest

from squadops.cycles.failure_evidence import build_failure_evidence, compose_failure_trigger
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
