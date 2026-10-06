"""#1824: a campaign retries a cycle that failed outside the work.

SIP-0109 §10's retry rows read ``rejected`` with an environment attribution, and no cycle produced
that reading: a run that fails on infrastructure reaches no verdict, and nothing declared its
ending, so it read ``unattributed`` and every such failure escalated to the owner (0 of 156 stored
failed cycles read the environment class).

What bugs would these catch?
- An ending outside the work recorded as ``other`` again: the box refusing a run past its bound,
  or the queue refusing a dispatch.
- A task timeout read as infrastructure. The model may still have been working (#995), and a retry
  would hide a defect in the work.
- The retry rows keyed on the verdict again, so a failed run with no verdict escalates.
- An environment attribution outranking ``blocked_unverified``, whose own rows come first.

Each test enters where the live run does: the admission wait and the terminal mapping the
executor's single ``except`` calls, then the real assessment over the run's stored summary, then
the decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.execution_errors import _ExecutionError
from adapters.cycles.run_admission import RunAdmission
from adapters.cycles.run_completion import resolve_terminal_outcome
from squadops.campaigns.continuation import (
    CycleEnding,
    EndedCycle,
    PendingAction,
    campaign_continuation_decision,
)
from squadops.campaigns.models import CampaignState, CycleKind
from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord, assess
from squadops.cycles.failure_attribution import AttributionClass, TerminalKind
from squadops.cycles.llm_usage import RunUsage
from squadops.cycles.run_loop_summary import RunLoopSummary, RunTerminalDecision
from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict
from squadops.ports.comms.queue import QueueError
from tests.unit.campaigns.builders import campaign
from tests.unit.campaigns.test_continuation import assessment as continuation_assessment
from tests.unit.campaigns.test_continuation import counters

CYCLE = "cyc_000000000001"
T0 = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
CAMPAIGN = campaign(state=CampaignState.EVALUATING)


async def _refused_by_the_box() -> _ExecutionError:
    """A run outside every campaign on a box a foreign model holds: refused at once."""
    held = SimpleNamespace(
        allowed=False, refusal="foreign_model", reasons=("llama3.1:8b holds the box",)
    )
    executor = SimpleNamespace(
        _box_verdict=AsyncMock(return_value=held),
        _campaign_registry=None,
        _cycle_registry=SimpleNamespace(
            get_cycle=AsyncMock(return_value=SimpleNamespace(campaign_id=None))
        ),
    )
    with pytest.raises(_ExecutionError) as refused:
        await RunAdmission(executor=lambda: executor).await_box("run_1", CYCLE)
    return refused.value


def _assessed(terminal: RunTerminalDecision, verdict: RunVerdict | None = None):
    """The real assessment of a one-run cycle whose stored summary records ``terminal``.
    ``verdict=None`` is a run that failed before any verification summary."""
    run = RunRecord(
        run_id="run_1",
        run_number=1,
        workload_type="implementation",
        status="failed" if verdict is None else "completed",
        started_at=T0,
        finished_at=T0,
    )
    summary = RunLoopSummary(
        run_id="run_1",
        usage=RunUsage(by_task_type={}, tasks_reported=0, tasks_unreported=()),
        terminal=terminal,
    )
    evidence = CycleEvidence(
        cycle_id=CYCLE,
        runs=(run,),
        verification_summary_runs=() if verdict is None else ("run_1",),
        loop_summaries={"run_1": summary},
    )
    outcome = CycleOutcome(
        verdict=verdict or RunVerdict.REJECTED,
        verified=(),
        failed=(),
        unverified=(),
        run_count=1,
        criteria_verified=(),
        criteria_total=(),
    )
    return assess(outcome, evidence, assessor=AssessorIdentity("2.1.0", None))


def _decided(latest, **count_overrides):
    return campaign_continuation_decision(
        CAMPAIGN,
        counters(**count_overrides),
        EndedCycle(CYCLE, CycleKind.INCREMENT, CycleEnding.ASSESSED),
        latest,
    )


async def test_a_run_the_box_refuses_is_retried_by_its_campaign():
    """The whole path: the admission wait's refusal, the executor's terminal mapping, the run's
    stored summary, the real assessment, and the decision."""
    outcome = resolve_terminal_outcome(await _refused_by_the_box(), "run_1")
    latest = _assessed(outcome.terminal)

    assert outcome.terminal.kind is TerminalKind.INFRASTRUCTURE_FAILED
    assert latest.attribution.attribution.primary is (
        AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE
    )
    decision = _decided(latest)
    assert (decision.row, decision.action) == (10, PendingAction.RETRY)
    spent = _decided(latest, retry_cycles=1)
    assert (spent.row, spent.action) == (11, PendingAction.ESCALATE)


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (QueueError("Failed to publish message: connection refused"), "infrastructure_failed"),
        (RuntimeError("an unexpected defect"), "other"),
        (
            _ExecutionError(
                "Task t-1 failed: Timed out waiting for agent neo after 1800.0s",
            ),
            "other",
        ),
    ],
    ids=["the-queue-refuses-a-dispatch", "an-unexpected-error", "a-task-timeout"],
)
def test_only_an_unambiguous_fault_outside_the_work_ends_as_infrastructure(exc, kind):
    outcome = resolve_terminal_outcome(exc, "run_1")

    assert outcome.terminal.kind == kind


@pytest.mark.parametrize(
    ("terminal", "expected"),
    [
        # Before #1824, a failed run's ending read `other`: unattributed, row 14.
        (TerminalKind.OTHER, (14, PendingAction.ESCALATE)),
        (TerminalKind.INFRASTRUCTURE_FAILED, (10, PendingAction.RETRY)),
    ],
    ids=["an-ending-nothing-declared", "an-infrastructure-ending"],
)
def test_a_failed_run_with_no_verdict_is_retried_only_on_an_infrastructure_ending(
    terminal, expected
):
    latest = _assessed(RunTerminalDecision(kind=terminal))

    decision = _decided(latest)

    assert (decision.row, decision.action) == expected


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (RunVerdict.BLOCKED_UNVERIFIED, (8, PendingAction.REPAIR)),
        (RunVerdict.REJECTED, (10, PendingAction.RETRY)),
    ],
    ids=["blocked-keeps-its-own-rows", "rejected-is-retried"],
)
def test_an_environment_attribution_ranks_below_blocked_and_above_rejected(verdict, expected):
    """Precedence alone: the attribution is set directly, as the continuation suite sets it."""
    decision = _decided(continuation_assessment(verdict, environment=True))

    assert (decision.row, decision.action) == expected
