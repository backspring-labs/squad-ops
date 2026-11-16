"""SIP-0108 §4.1 — the structured terminal decision on the run summary row.

Each test names what it catches: a decision field lost between the row and its reader, a stored
kind this reader does not know read as something it is not, or a run-ending exception mapped to a
kind nobody declared.
"""

from __future__ import annotations

import pytest

from squadops.cycles.failure_attribution import TerminalKind
from squadops.cycles.llm_usage import RunUsage
from squadops.cycles.run_loop_summary import RunLoopSummary, RunTerminalDecision
from squadops.cycles.task_outcome import CorrectionTerminationReason, FailureClassification
from squadops.execution.execution_errors import (
    _CancellationError,
    _ExecutionError,
    _PausedError,
    _RecruitmentRejectedError,
)
from squadops.execution.run_completion import resolve_terminal_outcome

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

    def test_a_skill_stop_survives_the_row_and_no_other_decision_gains_a_key(self):
        """SIP-0116 §17o. Bugs caught: the stop's line dropped between the run and whoever
        continues from it; and the new key entering every stored decision, which would change
        the stored form of runs that have no stop."""
        stop = {
            "skillset": "roblox-increment-design",
            "skill": "play-scenario-authoring",
            "opening": "no scenario:",
            "line": "no scenario: the chime shows itself as a sound",
        }
        decision = RunTerminalDecision(
            kind=TerminalKind.SKILL_STOPPED, task_id="task-strat-1", skill_stop=stop
        )

        assert RunTerminalDecision.from_dict(decision.to_dict()) == decision
        assert RunTerminalDecision(kind=TerminalKind.INPUT_REFUSED, task_id="t").to_dict() == {
            "kind": "input_refused",
            "termination_reason": None,
            "failure_classification": None,
            "task_id": "t",
            "refused_validators": [],
            "contested_checks": [],
        }

    @pytest.mark.parametrize(
        "stored",
        ["a sound", {"skillset": "s", "skill": "k", "opening": "no scenario:"}],
        ids=["not a mapping", "no line"],
    )
    def test_a_stored_stop_missing_a_part_is_refused(self, stored):
        """Bug caught: a ``skill_stopped`` decision read back with no line, so the next
        proposal is shown that a skill stopped the work and not what it said."""
        with pytest.raises(ValueError, match="skill_stop"):
            RunTerminalDecision.from_dict({"kind": "skill_stopped", "skill_stop": stored})

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
