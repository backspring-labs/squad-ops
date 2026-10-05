"""Cross-Cycle Memory's 2.1 part (#1964): the recall port, inert, and its call site.

What bugs would these catch? An inert recall that raises as ``NoOpMemoryPort`` does, which would
crash every run's provisioning now that the call site is live; recalled patterns handed to a
task type the registry does not declare (the plan merger or the sign-off reading warnings meant
for the authors); the inert recall handing anything at all, when 2.1 must change no prompt; and
a call site off the path a run takes, so 2.2's adapter would be wired to nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.capabilities.context_assembly import CONTEXT_CONTRACTS
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.cycles.task_plan import generate_task_plan, recalled_patterns_for
from squadops.memory.recall import RecalledPattern, RecallQuery
from squadops.ports.memory.recall import FailurePatternRecallPort

pytestmark = [pytest.mark.domain_memory]

_NOW = datetime(2026, 10, 5, tzinfo=UTC)
_DECLARED = {str(t) for t, c in CONTEXT_CONTRACTS.items() if c.plan_rejection_context}
_PATTERN = RecalledPattern(
    rejection_class="artifact_claim_conflict",
    statement="verification-only tasks declare expected_artifacts: []",
)


class _Recording(FailurePatternRecallPort):
    """A recall that answers one pattern for every task type, and records what it was asked."""

    def __init__(self) -> None:
        self.asked: list[RecallQuery] = []

    async def recall(self, query: RecallQuery) -> tuple[RecalledPattern, ...]:
        self.asked.append(query)
        return (_PATTERN,)


def _framing_cycle() -> Cycle:
    return Cycle(
        cycle_id="cyc_recall",
        project_id="group_run",
        created_at=_NOW,
        created_by="s",
        prd_ref="PRD",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"plan_authoring_contributors": ["development", "qa", "strategy"]},
        execution_overrides={},
        expected_artifact_types=["source"],
    )


def _framing_run() -> Run:
    return Run(
        run_id="run_recall0001",
        cycle_id="cyc_recall",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="h",
        workload_type=WorkloadType.FRAMING,
    )


_PROFILE = SquadProfile(
    profile_id="full",
    name="F",
    description="d",
    version=1,
    agents=[
        AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
        for a, r in (("max", "lead"), ("neo", "dev"), ("nat", "strat"), ("eve", "qa"))
    ]
    + [
        AgentProfileEntry(
            agent_id="data", role="data", model="m", enabled=True, serves_roles=("data",)
        )
    ],
    created_at=_NOW,
)


async def test_the_inert_recall_answers_empty_and_hands_nothing():
    """2.1's recall: an answer of "none", never a raise, and no key on any envelope."""
    answers = await recalled_patterns_for(NoOpFailurePatternRecall(), "group_run")

    plan = generate_task_plan(_framing_cycle(), _framing_run(), _PROFILE, recalled_patterns=answers)

    assert answers == {}
    assert not [e for e in plan if "recalled_failure_patterns" in e.inputs]


async def test_recalled_patterns_reach_exactly_the_task_types_that_declare_them():
    recall = _Recording()

    answers = await recalled_patterns_for(recall, "group_run")
    plan = generate_task_plan(_framing_cycle(), _framing_run(), _PROFILE, recalled_patterns=answers)

    handed = {str(e.task_type) for e in plan if "recalled_failure_patterns" in e.inputs}
    assert {q.task_type for q in recall.asked} == _DECLARED
    assert {q.project_id for q in recall.asked} == {"group_run"}
    assert handed == _DECLARED & {str(e.task_type) for e in plan}
    assert handed  # a framing plan has declared authors
    assert all(
        e.inputs["recalled_failure_patterns"]
        == [{"rejection_class": "artifact_claim_conflict", "statement": _PATTERN.statement}]
        for e in plan
        if str(e.task_type) in handed
    )


async def test_provisioning_asks_the_executors_recall_before_it_builds_the_plan():
    """Entered at ``RunProvisioning.prepare``, the step ``execute_run`` takes before dispatch,
    with the real plan generation. Bug caught: the call site off the run's path, so a recall
    answering patterns would reach no envelope."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
    from adapters.cycles.run_provisioning import RunInProgress

    recall = _Recording()
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=recall,
        task_timeout=5.0,
    )
    cycle, run = _framing_cycle(), _framing_run()
    executor._prepare_cycle_for_run = AsyncMock(return_value=(cycle, None))
    executor._cycle_registry.get_run.return_value = run
    executor._cycle_registry.get_latest_checkpoint.return_value = None
    executor._squad_profile.resolve_snapshot.return_value = (_PROFILE, "sha")
    executor._load_plan_for_run = AsyncMock(return_value=None)
    executor._load_contract_for_run = AsyncMock(return_value=None)
    executor._cycle_event_bus = MagicMock()
    state = RunInProgress()

    await executor._run_provisioning.prepare(
        state, cycle.cycle_id, run.run_id, "full", forwarding_overrides=None
    )

    assert recall.asked
    assert any("recalled_failure_patterns" in e.inputs for e in state.plan)
