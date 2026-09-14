"""SIP-0108 §4.1 — the structured terminal decision on the run summary row.

Each test names what it catches: a decision field lost between the row and its reader, a stored
kind this reader does not know read as something it is not, or a run-ending exception mapped to a
kind nobody declared.
"""

from __future__ import annotations

import pytest

from adapters.cycles.execution_errors import (
    _CancellationError,
    _ExecutionError,
    _PausedError,
    _RecruitmentRejectedError,
)
from adapters.cycles.run_completion import resolve_terminal_outcome
from squadops.cycles.failure_attribution import TerminalKind
from squadops.cycles.llm_usage import RunUsage
from squadops.cycles.run_loop_summary import RunLoopSummary, RunTerminalDecision
from squadops.cycles.task_outcome import CorrectionTerminationReason, FailureClassification

pytestmark = [pytest.mark.domain_orchestration]

_USAGE = RunUsage(by_task_type={}, tasks_reported=0, tasks_unreported=())


class TestTheStoredShape:
    def test_every_field_of_the_decision_survives_the_row(self):
        """Bug caught: a field written but not read back — the validators of a plan-gate
        refusal or the classification of a plan-defect termination silently dropped."""
        decision = RunTerminalDecision(
            kind=TerminalKind.CORRECTION_TERMINATED,
            termination_reason=CorrectionTerminationReason.PLAN_DEFECT,
            failure_classification=FailureClassification.WORK_PRODUCT,
            task_id="task-qa-4",
            refused_validators=("validate_build_config", "validate_builder_floor"),
        )
        summary = RunLoopSummary(run_id="run_1", usage=_USAGE, terminal=decision)

        read = RunLoopSummary.from_dict(summary.to_dict())

        assert read == summary
        assert read.terminal.kind is TerminalKind.CORRECTION_TERMINATED

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [
            ({"kind": "gate_exploded"}, RunTerminalDecision(kind=TerminalKind.OTHER)),
            ({}, RunTerminalDecision(kind=TerminalKind.OTHER)),
            (None, None),
        ],
        ids=["a kind this reader does not know", "a decision with no kind", "no decision"],
    )
    def test_an_unreadable_decision_reads_other_and_an_absent_one_reads_none(
        self, stored, expected
    ):
        """Bug caught: a newer writer's kind raising on read, or a row without a decision read
        as a decided ending."""
        row = RunLoopSummary(run_id="run_1", usage=_USAGE).to_dict()
        row["terminal"] = stored

        assert RunLoopSummary.from_dict(row).terminal == expected


class TestTheMapping:
    _DECLARED = RunTerminalDecision(
        kind=TerminalKind.COMPLIANCE_BUDGET_EXCEEDED,
        failure_classification=FailureClassification.CONTRACT_COMPLIANCE,
        task_id="task-1",
    )

    @pytest.mark.parametrize(
        ("exc", "expected"),
        [
            (_ExecutionError("budget", terminal=_DECLARED), _DECLARED),
            (
                _ExecutionError("Task t-1 failed: boom"),
                RunTerminalDecision(kind=TerminalKind.OTHER),
            ),
            (ValueError("boom"), RunTerminalDecision(kind=TerminalKind.OTHER)),
            (_CancellationError("run_1"), RunTerminalDecision(kind=TerminalKind.OTHER)),
            (_PausedError("blocked"), RunTerminalDecision(kind=TerminalKind.OTHER)),
            (_RecruitmentRejectedError("a", "r"), RunTerminalDecision(kind=TerminalKind.OTHER)),
        ],
        ids=["declared", "undeclared", "unexpected", "cancelled", "paused", "deferred"],
    )
    def test_a_declared_decision_passes_through_and_everything_else_is_other(self, exc, expected):
        """Bug caught: the declaration dropped at the mapping, or an undeclared ending guessed
        into a kind (a cancellation read as completed would score as an accepted cycle)."""
        assert resolve_terminal_outcome(exc, "run_1").terminal == expected
