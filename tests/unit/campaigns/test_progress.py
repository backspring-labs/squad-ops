"""A campaign hears its cycle end (SIP-0109 §10, §11, §12a; #1800, #1709).

Entered at ``CycleCompletion.end`` — the completion boundary every cycle passes — on the real
executor, over the memory campaign and cycle registries. The vault holds what a run stores; the
assessment is the real projection over crafted evidence, so the decision reads the verdict as the
live path hands it over.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from squadops.campaigns.campaign_branch import CampaignBranch
from squadops.campaigns.continuation import CycleEnding
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntentState,
)
from squadops.campaigns.progress import CampaignProgress, CycleRecord, cycle_ending, derive_counters
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord, assess
from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from squadops.cycles.models import ArtifactRef, Cycle, Gate, Run, TaskFlowPolicy
from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict
from tests.unit.campaigns.builders import campaign, move, policy

NOW = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)
CID = "cmp_prog00000001"
MANIFEST = "version: 1\nentities: []\nendpoints: []\n"


def _assessment(cycle_id: str, verdict: RunVerdict | None):
    run = RunRecord("run_impl", 2, "implementation", "completed" if verdict else "failed", NOW, NOW)
    evidence = CycleEvidence(
        cycle_id=cycle_id, runs=(run,), verification_summary_runs=("run_impl",) if verdict else ()
    )
    outcome = CycleOutcome(
        verdict=verdict or RunVerdict.REJECTED,
        verified=(),
        failed=("tests_pass",) if verdict is RunVerdict.REJECTED else (),
        unverified=(),
        run_count=1,
        criteria_verified=(),
        criteria_total=(),
    )
    return assess(outcome, evidence, assessor=AssessorIdentity("2.0.0", None))


def _ref(art_id, filename, kind, created, **meta):
    return ArtifactRef(
        artifact_id=art_id,
        project_id="group_run",
        artifact_type=kind,
        filename=filename,
        content_hash="h",
        size_bytes=1,
        media_type="text/plain",
        created_at=NOW + timedelta(seconds=created),
        cycle_id="cyc_cal",
        run_id="run_impl",
        metadata=meta,
    )


#: The calibration's implementation run: two delivered files, one rejected repair candidate
#: newer than the file it repairs, and the interface manifest (a document, not delivered).
_STORED = {
    "art_routes": (_ref("art_routes", "backend/routes.py", "source", 1), b"routes v1"),
    "art_cand": (
        _ref(
            "art_cand",
            "backend/routes.py",
            "source",
            9,
            producing_task_type="development.correction_repair",
        ),
        b"rejected repair",
    ),
    "art_app": (_ref("art_app", "frontend/src/App.jsx", "source", 2), b"app"),
    "art_manifest": (
        _ref("art_manifest", "interface_manifest.yaml", "document", 0),
        MANIFEST.encode(),
    ),
}


def _flow_policy(profile: str) -> TaskFlowPolicy:
    """The task-flow policy a cycle launched on ``profile`` carries, gates included."""
    raw = load_profile(profile).defaults["task_flow_policy"]
    return TaskFlowPolicy(
        mode=raw["mode"],
        gates=tuple(
            Gate(g["name"], g["description"], tuple(g["after_task_types"]))
            for g in raw.get("gates") or ()
        ),
    )


class _Vault:
    async def list_artifacts(self, *, cycle_id=None, run_id=None, **_):
        return [ref for ref, _ in _STORED.values()]

    async def retrieve(self, artifact_id):
        return _STORED[artifact_id]


class _World:
    def __init__(self, verdict: RunVerdict | None, evaluator=None, branch=None) -> None:
        from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor

        self.campaigns = MemoryCampaignRegistry()
        self.cycles = MemoryCycleRegistry()
        self.launches = AsyncMock()
        # SIP-0113 (#2414): the outcome evaluator, built on this world's registries when given.
        self.evaluations = evaluator(self).cycle_ended if evaluator else AsyncMock()
        self.verdict = verdict
        self.now = NOW + timedelta(hours=1)
        self.progress = CampaignProgress(
            campaigns=self.campaigns,
            cycles=self.cycles,
            vault=_Vault(),
            assess=self._assess,
            launch=self.launches,
            evaluate_outcome=self.evaluations,
            outcome_section=None,
            intervention_section=None,
            campaign_branch=branch,
            clock=lambda: self.now,
        )
        self.executor = DispatchedFlowExecutor(
            cycle_registry=self.cycles,
            artifact_vault=_Vault(),
            queue=AsyncMock(),
            squad_profile=AsyncMock(),
            task_timeout=5.0,
            campaign_registry=self.campaigns,
            campaign_progress=self.progress,
            project_registry=None,
            box_verdict=None,
            failure_recall=NoOpFailurePatternRecall(),
            proposal_evidence=NoOpProposalEvidence(),
        )
        self.executor._cycle_event_bus = MagicMock()

    async def _assess(self, cycle_id):
        return _assessment(cycle_id, self.verdict)

    async def launched_cycle(
        self,
        kind: str,
        cycle_id: str,
        workload: str,
        status: str,
        overrides: dict | None = None,
        intent_kind: str | None = None,
    ) -> Run:
        await self.cycles.create_cycle(
            Cycle(
                cycle_id=cycle_id,
                project_id="group_run",
                created_at=NOW,
                created_by="campaign-launcher",
                prd_ref=None,
                squad_profile_id="full-38",
                squad_profile_snapshot_ref="sha256:abc",
                # The calibration profile's policy, its plan gate included.
                task_flow_policy=_flow_policy("framing"),
                build_strategy="fresh",
                campaign_id=CID,
                kind=kind,
                execution_overrides=dict(overrides or {}),
            )
        )
        run = Run(
            run_id="run_impl",
            cycle_id=cycle_id,
            run_number=1,
            status=status,
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type=workload,
        )
        await self.cycles.create_run(run)
        [intent] = [
            i
            for i in await self.campaigns.pending_launch_intents()
            if i.cycle_kind.value == (intent_kind or kind)
        ]
        await self.campaigns.mark_launch_intent_launched(intent.launch_id, cycle_id, actor="l")
        return run

    async def end(self, cycle_id: str, run: Run, stopped: CycleStopReason):
        await self.executor._cycle_completion.end(cycle_id, run, stopped)


@pytest.fixture
async def calibrating() -> _World:
    async def make(
        verdict,
        objective=None,
        evaluator=None,
        overrides=None,
        workload="implementation",
        branch=None,
        **policy_overrides,
    ):
        w = _World(verdict, evaluator, branch)
        draft = campaign(
            CID,
            policy=policy(
                calibration_profile="framing",
                **{"proposal_profile": "campaign-increment", **policy_overrides},
            ),
            **({"objective": objective} if objective is not None else {}),
        )
        await w.campaigns.create_campaign(
            draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
        )
        await w.campaigns.transition(
            CID,
            start_transition(
                draft, actor="owner", actor_role="admin", reason="go", idempotency_key="start"
            ),
        )
        return w, await w.launched_cycle("calibration", "cyc_cal", workload, "completed", overrides)

    return make


async def test_an_accepted_calibration_is_promoted_then_proposes_against_its_tree(calibrating):
    """§11, §12a, §10 rows 5: promotion first, then the decision, keyed by the cycle, its
    intent written with it. Bugs caught: a tree identified with a rejected repair in it (the
    #1832 rule bypassed), a proposal launched against no tree or another manifest, or the
    campaign's revision budget not reaching the increment gate."""
    w, run = await calibrating(RunVerdict.ACCEPTED)

    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)

    stored = await w.campaigns.get_campaign(CID)
    log = await w.campaigns.control_log(CID)
    [_, increment] = await w.campaigns.launch_intents(CID)
    proposal = increment.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    expected = FileTree.of({"backend/routes.py": b"routes v1", "frontend/src/App.jsx": b"app"})
    assert stored.accepted.identity == expected.identity
    assert stored.state is CampaignState.AT_PROPOSAL
    assert [e.operation for e in log[-2:]] == [ControlOperation.PROMOTE, ControlOperation.DECIDE]
    assert (log[-1].binding["row"], log[-1].binding["action"]) == (5, "propose")
    assert (increment.cycle_kind, increment.state) == (
        CycleKind.INCREMENT,
        LaunchIntentState.PENDING,
    )
    assert proposal["baseline_tree"] == expected.identity
    assert proposal["baseline_manifest"] == MANIFEST
    assert proposal["max_revisions"] == 2
    w.launches.assert_awaited_once()


@pytest.mark.parametrize(
    ("tokens", "state", "paused_by"),
    [(1_500_000, CampaignState.AT_PROPOSAL, None), (2_100_000, CampaignState.PAUSED, "budget")],
    ids=["under-budget", "over-budget"],
)
async def test_a_cycles_stored_usage_reaches_the_budget_limit(
    calibrating, tokens, state, paused_by
):
    """§9.2, #1857, entered at the completion hook with the run's real loop summary stored, as
    every live run has. Bugs caught: the token counter crashing on the stored usage, so the hook
    decides nothing and the campaign is left where it was; or the usage never counted, so the
    budget limit never pauses."""
    from squadops.cycles.llm_usage import RunUsage, UsageTotals
    from squadops.cycles.run_loop_summary import RunLoopSummary

    w, run = await calibrating(RunVerdict.ACCEPTED)
    usage = UsageTotals(calls=2, prompt_tokens=tokens - 100_000, completion_tokens=100_000)
    await w.cycles.record_run_loop_summary(
        run.run_id,
        RunLoopSummary(
            run_id=run.run_id,
            usage=RunUsage(
                by_task_type={"development.develop": usage}, tasks_reported=2, tasks_unreported=()
            ),
        ),
    )

    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)

    decision = (await w.campaigns.control_log(CID))[-1]
    assert decision.operation is ControlOperation.DECIDE
    assert ((await w.campaigns.get_campaign(CID)).state, decision.binding["paused_by"]) == (
        state,
        paused_by,
    )


async def _resume(w: _World, cycle_ids: list[str]) -> None:
    """The runtime API's startup, as it resumes campaigns (``main._resume_campaigns``)."""
    from types import SimpleNamespace

    from squadops.api.runtime.main import _resume_campaigns

    launch = AsyncMock()
    launch.launched_cycles.return_value = cycle_ids
    await _resume_campaigns(SimpleNamespace(campaign_launch=launch, campaign_progress=w.progress))


async def test_a_cycle_its_hook_failed_to_decide_is_re_heard_once_at_startup(calibrating):
    """§12a, #1803 — the live shakeout's shape (#1857): the calibration ended accepted, the hook
    promoted and then crashed before deciding, and nothing heard the cycle again. Entered at the
    completion hook, which records the ending, and at the startup that re-hears it. Bugs caught:
    a campaign left where the failed hook left it; a re-entry that decides twice; or one that
    reconstructs the stop reason instead of reading the recorded one."""
    w, run = await calibrating(RunVerdict.ACCEPTED)
    crash = AsyncMock(side_effect=AttributeError("'RunUsage' object has no attribute 'totals'"))
    working = w.progress._launched_cycles
    w.progress._launched_cycles = crash
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    assert [e.operation for e in await w.campaigns.control_log(CID)][-1] is ControlOperation.PROMOTE

    w.progress._launched_cycles = working
    await _resume(w, ["cyc_cal"])
    await _resume(w, ["cyc_cal"])

    log = await w.campaigns.control_log(CID)
    decisions = [e for e in log if e.operation is ControlOperation.DECIDE]
    assert [(d.target, d.binding["row"], d.binding["action"]) for d in decisions] == [
        ("cyc_cal", 5, "propose")
    ]
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.AT_PROPOSAL
    w.launches.assert_awaited_once()


async def _sweep(w: _World, cycle_ids: list[str], passes: int) -> None:
    """The runtime's campaign sweep (``main._sweep_campaigns``), run for ``passes`` intervals."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch

    from squadops.api.runtime import main

    launch = AsyncMock()
    launch.launched_cycles.return_value = cycle_ids
    ticks = [None] * passes + [asyncio.CancelledError()]
    with (
        patch.object(main.asyncio, "sleep", AsyncMock(side_effect=ticks)),
        pytest.raises(asyncio.CancelledError),
    ):
        await main._sweep_campaigns(
            SimpleNamespace(campaign_launch=launch, campaign_progress=w.progress)
        )


async def test_a_cycle_its_hook_failed_to_decide_is_re_heard_by_the_sweep(calibrating):
    """§24v, #1972: the same lost hook as above, while the process stays up. Entered at the
    completion hook and at the runtime's sweep. Bugs caught: the campaign left where the hook
    left it until the next restart; or a sweep that decides again on every pass."""
    w, run = await calibrating(RunVerdict.ACCEPTED)
    working = w.progress._launched_cycles
    w.progress._launched_cycles = AsyncMock(side_effect=RuntimeError("the hook died"))
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    w.progress._launched_cycles = working

    await _sweep(w, ["cyc_cal"], passes=2)

    log = await w.campaigns.control_log(CID)
    decisions = [e for e in log if e.operation is ControlOperation.DECIDE]
    assert [(d.target, d.binding["action"]) for d in decisions] == [("cyc_cal", "propose")]
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.AT_PROPOSAL
    w.launches.assert_awaited_once()


async def test_a_cycle_heard_by_the_hook_and_the_sweep_at_once_is_decided_once(calibrating):
    """#1972: the sweep and a hook still deciding the same cycle. Bug caught: both deciding it,
    so the calibration is promoted twice and the second decision is refused as a conflict and
    recorded in the campaign's log."""
    import asyncio

    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.cycles.record_cycle_end(
        RecordedEnd("cyc_cal", run.run_id, CycleStopReason.SEQUENCE_COMPLETED)
    )
    real_assess = w._assess

    async def slow_assess(cycle_id):
        await asyncio.sleep(0)  # the other hearer runs here
        return await real_assess(cycle_id)

    w.progress._assess = slow_assess
    cycle = await w.cycles.get_cycle("cyc_cal")

    results = await asyncio.gather(
        w.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED),
        w.progress.rehear_ended(["cyc_cal"]),
    )

    log = await w.campaigns.control_log(CID)
    operations = [e.operation for e in log]
    assert operations.count(ControlOperation.PROMOTE) == 1
    assert operations.count(ControlOperation.DECIDE) == 1
    assert all(e.outcome is ControlOutcome.APPLIED for e in log)
    assert results[0] is not None and results[1] == []


async def test_startup_leaves_a_paused_or_unrecorded_ending_alone(calibrating):
    """§12a: a cycle that stopped resumable is not decided, and one that recorded no ending is in
    flight (or predates the record). Bug caught: a re-entry deciding a cycle that has not ended."""
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.cycles.record_cycle_end(RecordedEnd("cyc_cal", run.run_id, CycleStopReason.RUN_PAUSED))

    await _resume(w, ["cyc_cal", "cyc_unknown"])

    log = await w.campaigns.control_log(CID)
    assert ControlOperation.DECIDE not in [e.operation for e in log]
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.CALIBRATING


async def test_the_decision_is_made_once_per_cycle(calibrating):
    """§8.4: re-entering returns the recorded decision, never a recomputed one. Bug caught: a
    re-entry after the clock crossed the elapsed limit deciding again — a second, conflicting
    row for the cycle, and a campaign the first decision had sent on now recorded as held."""
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    rows = len(await w.campaigns.control_log(CID))

    w.now = NOW + timedelta(hours=13)  # past the policy's 12 h
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)

    assert len(await w.campaigns.control_log(CID)) == rows
    assert len(await w.campaigns.launch_intents(CID)) == 2  # the calibration and one increment
    w.launches.assert_awaited_once()


async def test_a_rejected_calibration_stops_the_campaign_and_promotes_nothing(calibrating):
    """§10 row 2, §19 criterion 2. Bug caught: a rejected calibration's tree becoming the
    baseline every increment is proposed against."""
    w, run = await calibrating(RunVerdict.REJECTED)

    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)

    stored = await w.campaigns.get_campaign(CID)
    assert (stored.state, stored.outcome, stored.accepted) == (
        CampaignState.COMPLETED,
        CampaignOutcome.FAILURE,
        None,
    )
    assert len(await w.campaigns.launch_intents(CID)) == 1
    w.launches.assert_not_awaited()


@pytest.mark.parametrize(
    "stopped",
    [CycleStopReason.PLAN_REJECTED, CycleStopReason.GATE_REJECTED, CycleStopReason.GATE_FAILED],
)
async def test_a_calibration_stopped_at_its_plan_gate_fails_the_campaign_and_promotes_nothing(
    calibrating, stopped
):
    """§10 row 2, §24cb (#2704, live: ``cmp_889af0a98b6d``). The calibration's plan was rejected
    three times, so it built nothing, and its framing run's summary reads ``accepted`` with nothing
    executed. Bugs caught: that summary read as the calibration's verdict, so the empty tree was
    promoted as the campaign's baseline and an increment launched on it; and the outcome
    evaluation, which only a build has, run on one that never happened."""
    w, run = await calibrating(RunVerdict.ACCEPTED, workload="framing")

    await w.end("cyc_cal", run, stopped)

    stored = await w.campaigns.get_campaign(CID)
    log = await w.campaigns.control_log(CID)
    assert (stored.state, stored.outcome, stored.accepted) == (
        CampaignState.COMPLETED,
        CampaignOutcome.FAILURE,
        None,
    )
    assert [e for e in log if e.operation is ControlOperation.PROMOTE] == []
    assert {k: log[-1].binding[k] for k in ("row", "ending", "verdict", "cause")} == {
        "row": 2,
        "ending": "stopped_at_plan_gate",
        "verdict": None,
        "cause": "calibration",
    }
    w.evaluations.assert_not_awaited()
    w.launches.assert_not_awaited()


@pytest.mark.parametrize(
    ("limit", "expected"),
    [
        (2, {"row": 18, "action": "abandon_and_propose", "guard": "proceed"}),
        (1, {"row": 4, "outcome": "failure", "cause": "unaccepted_increments"}),
    ],
    ids=["abandoned-for-a-new-proposal", "counted-to-the-no-progress-limit"],
)
async def test_an_increment_stopped_at_its_plan_gate_is_abandoned_and_counted_never_repaired(
    calibrating, limit, expected
):
    """§10 rows 18 and 4, §24cb (#2704), entered at the completion hook as the increment's framing
    run stops at its plan gate. Bugs caught: its framing summary's ``accepted`` with no increment
    evaluation read as ``blocked_unverified``, so row 8 launched a repair of a candidate that was
    never built and spent the increment's repair; and the abandonment not counted as unaccepted,
    so increments whose plans keep failing never reach the no-progress limit."""
    w, run = await calibrating(RunVerdict.ACCEPTED, max_unaccepted_increments=limit)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    framing = await w.launched_cycle("increment", "cyc_inc", "framing", "completed")

    await w.end("cyc_inc", framing, CycleStopReason.PLAN_REJECTED)

    log = await w.campaigns.control_log(CID)
    decision = log[-1].binding
    assert {k: decision.get(k) for k in expected} == expected
    assert (decision["ending"], decision["verdict"]) == ("stopped_at_plan_gate", None)
    assert [e.target for e in log if e.operation is ControlOperation.PROMOTE] == ["cyc_cal"]
    assert [i.cycle_kind for i in await w.campaigns.launch_intents(CID)] == [
        CycleKind.CALIBRATION,
        CycleKind.INCREMENT,
        *([CycleKind.INCREMENT] if limit == 2 else []),
    ]
    assert [c.args[0].cycle_id for c in w.evaluations.await_args_list] == ["cyc_cal"]


async def test_a_cycle_ending_after_an_abort_decides_and_launches_nothing(calibrating):
    """§12a: an abort is terminal — no continuation follows, whatever arrives after. Bug
    caught: the cancelled cycle's completion, arriving after the abort committed, writing a
    decision (here §10 row 2's stop, which the registry would refuse and record as a row) or a
    launch for a campaign that has ended."""
    w, run = await calibrating(RunVerdict.REJECTED)
    await w.campaigns.transition(
        CID,
        move(
            CampaignState.COMPLETED,
            "abort",
            operation=ControlOperation.ABORT,
            outcome=CampaignOutcome.ABORTED,
        ),
    )
    rows = len(await w.campaigns.control_log(CID))

    await w.end("cyc_cal", run, CycleStopReason.RUN_CANCELLED)

    stored = await w.campaigns.get_campaign(CID)
    assert stored.outcome is CampaignOutcome.ABORTED
    assert len(await w.campaigns.control_log(CID)) == rows
    w.launches.assert_not_awaited()


@pytest.mark.parametrize("stopped", [CycleStopReason.RUN_PAUSED, CycleStopReason.RUN_NOT_TERMINAL])
async def test_a_cycle_that_can_still_continue_is_not_decided(calibrating, stopped):
    """Bug caught: a deferred run (#1754) read as an ending, and the campaign moving on while
    its cycle resumes."""
    w, run = await calibrating(RunVerdict.ACCEPTED)

    await w.end("cyc_cal", run, stopped)

    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.CALIBRATING


@pytest.mark.parametrize(
    ("workload", "status", "stopped", "ending", "parked"),
    [
        (
            "proposal",
            "completed",
            CycleStopReason.GATE_REJECTED,
            CycleEnding.REJECTED_AT_GATE,
            False,
        ),
        # §9.5: a proposal whose revisions are spent counts as rejected.
        (
            "proposal",
            "completed",
            CycleStopReason.REVISION_UNAVAILABLE,
            CycleEnding.REJECTED_AT_GATE,
            False,
        ),
        ("proposal", "failed", CycleStopReason.RUN_FAILED, CycleEnding.PROPOSAL_FAILED, False),
        # #2213: the increment gate failed to submit the proposal; never read as reaching a build.
        ("proposal", "completed", CycleStopReason.GATE_FAILED, CycleEnding.PROPOSAL_FAILED, False),
        # #2704: a decision the increment gate doesn't know is never read as reaching a build.
        (
            "proposal",
            "completed",
            CycleStopReason.GATE_DECISION_UNRECOGNIZED,
            CycleEnding.PROPOSAL_FAILED,
            False,
        ),
        # §24cb (#2704): a framing run stopped at its plan gate ended the cycle unbuilt, however
        # the gate stopped it. Read as assessed, its framing summary's ``accepted`` promoted it.
        *[
            ("framing", "completed", stop, CycleEnding.STOPPED_AT_PLAN_GATE, False)
            for stop in (
                CycleStopReason.PLAN_REJECTED,
                CycleStopReason.GATE_REJECTED,
                CycleStopReason.REVISION_UNAVAILABLE,
                CycleStopReason.GATE_DECISION_UNRECOGNIZED,
                CycleStopReason.GATE_FAILED,
            )
        ],
        ("implementation", "failed", CycleStopReason.RUN_FAILED, CycleEnding.ASSESSED, False),
        # A framing run that failed stopped on its own run, not its gate: its summary judges it.
        ("framing", "failed", CycleStopReason.RUN_FAILED, CycleEnding.ASSESSED, False),
        # §24bj: the expired escalation's run, cancelled for it.
        ("framing", "cancelled", CycleStopReason.RUN_CANCELLED, CycleEnding.PARKED, True),
        # An expiry a person's decision beat: the run went on, so the cycle was not parked.
        (
            "implementation",
            "completed",
            CycleStopReason.SEQUENCE_COMPLETED,
            CycleEnding.ASSESSED,
            True,
        ),
        # An operator's cancel with no expiry naming the run is not a park.
        ("framing", "cancelled", CycleStopReason.RUN_CANCELLED, CycleEnding.ASSESSED, False),
    ],
)
def test_the_ending_is_read_from_where_the_cycle_stopped(workload, status, stopped, ending, parked):
    run = Run("r", "c", 1, status, "system", "cfg", workload_type=workload)
    assert cycle_ending(stopped, run, parked=parked) is ending


def test_the_counters_are_read_from_the_campaigns_own_records():
    """§9.5, §24b. Bugs caught: repair cycles counted across increments (a fresh increment
    inheriting the last one's spent repairs), or rejections in a row that an accepted
    proposal should have broken."""

    def decided(ending, action=None):
        entry = MagicMock()
        entry.operation, entry.outcome = ControlOperation.DECIDE, "applied"
        entry.binding = {"row": 6, "ending": ending, "action": action, "guard": "proceed"}
        return entry

    started = MagicMock()
    started.operation, started.committed_at = ControlOperation.START, NOW
    log = [
        started,
        decided("rejected_at_gate"),
        decided("assessed", action="abandon_and_propose"),
        decided("rejected_at_gate"),
    ]
    launched = [
        CycleRecord(CycleKind.CALIBRATION, 100),
        CycleRecord(CycleKind.INCREMENT, 50),
        CycleRecord(CycleKind.REPAIR, 20),
        CycleRecord(CycleKind.INCREMENT, 30),
        CycleRecord(CycleKind.REPAIR, 10),
    ]

    counters = derive_counters(
        campaign(CID),
        log,
        launched,
        ending=CycleEnding.REJECTED_AT_GATE,
        now=NOW + timedelta(hours=2),
        objective_met=False,
    )

    assert (counters.cycles, counters.tokens, counters.elapsed_s) == (5, 210, 7200)
    assert (counters.repair_cycles, counters.retry_cycles) == (1, 0)
    assert counters.rejected_proposals_in_row == 2
    assert counters.unaccepted_increments == 1


@pytest.mark.parametrize(
    ("earlier", "ending", "failed", "rejected"),
    [
        (["proposal_failed", "proposal_failed"], CycleEnding.PROPOSAL_FAILED, 3, 0),
        (["proposal_failed", "rejected_at_gate"], CycleEnding.PROPOSAL_FAILED, 1, 0),
        (["proposal_failed"], CycleEnding.REJECTED_AT_GATE, 0, 1),
        (["proposal_failed"], CycleEnding.ASSESSED, 0, 0),
    ],
    ids=["a-run-of-failures", "a-rejection-breaks-it", "a-rejection-ends-it", "a-build-ends-it"],
)
def test_failed_proposals_in_a_row_are_read_back_until_another_ending(
    earlier, ending, failed, rejected
):
    """§24bn (#2231). Bugs caught: failures counted across a rejection or a built increment, so
    a campaign pauses on failures that were never consecutive; or failures and rejections
    counted as one run."""
    started = MagicMock()
    started.operation, started.committed_at = ControlOperation.START, NOW
    rows = []
    for e in earlier:
        entry = MagicMock()
        entry.operation, entry.outcome = ControlOperation.DECIDE, "applied"
        entry.binding = {"row": 6, "ending": e, "action": "propose", "guard": "proceed"}
        rows.append(entry)

    counters = derive_counters(
        campaign(CID),
        [started, *rows],
        [CycleRecord(CycleKind.CALIBRATION, 100), CycleRecord(CycleKind.INCREMENT, 10)],
        ending=ending,
        now=NOW,
        objective_met=False,
    )

    assert (counters.failed_proposals_in_row, counters.rejected_proposals_in_row) == (
        failed,
        rejected,
    )


async def test_the_failure_past_the_proposal_retries_pauses_the_campaign(calibrating):
    """§24bn (#2231), entered at the completion hook as each live proposal run ends. Bug caught:
    the 2.2.1 diagnostic's shape. ``max_proposal_run_retries`` was read nowhere, so a proposer
    that cannot produce a valid proposal launched proposal after proposal until ``max_cycles``.
    The first failure is retried by a new proposal cycle; the second pauses for the owner."""
    w, run = await calibrating(RunVerdict.ACCEPTED, max_proposal_run_retries=1)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    w.verdict = None

    first = await w.launched_cycle("increment", "cyc_inc1", "proposal", "failed")
    await w.end("cyc_inc1", first, CycleStopReason.RUN_FAILED)
    retried = (await w.campaigns.control_log(CID))[-1]
    second = await w.launched_cycle("increment", "cyc_inc2", "proposal", "failed")
    await w.end("cyc_inc2", second, CycleStopReason.RUN_FAILED)

    paused = (await w.campaigns.control_log(CID))[-1]
    assert (retried.binding["row"], retried.binding["guard"]) == (6, "proceed")
    assert (paused.binding["row"], paused.binding["ending"], paused.binding["paused_by"]) == (
        6,
        "proposal_failed",
        "failed_proposals_in_row",
    )
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.PAUSED


def test_the_increment_launch_reads_its_profile_from_the_policy():
    """The increment cycle is the policy's proposal profile, run by the policy's squad."""
    from squadops.campaigns.launch_requests import increment_launch
    from squadops.campaigns.models import AcceptedTree

    c = campaign(
        CID,
        policy=policy(proposal_profile="campaign-increment"),
        accepted=AcceptedTree("sha-1", "cyc_cal"),
    )

    body = increment_launch(c, MANIFEST).cycle_request["body"]

    assert (body["request_profile"], body["squad_profile_id"]) == ("campaign-increment", "full-38")
    # The increment builds on the accepted cycle's delivered files (§7.1, #1705 c1).
    assert body["execution_overrides"]["campaign_proposal"]["accepted_cycle_id"] == "cyc_cal"
    assert yaml.safe_load(MANIFEST) == yaml.safe_load(
        body["execution_overrides"]["campaign_proposal"]["baseline_manifest"]
    )


@pytest.mark.parametrize(
    ("stack", "built_on"),
    [("nextjs_ts", "nextjs_ts"), (None, None)],
    ids=["declared", "the-profiles-own"],
)
def test_every_launch_kind_carries_the_campaigns_stack(stack, built_on):
    """§24bs (#2443). Bug caught: a Next.js campaign whose calibration, increments or bound
    cycles build on FastAPI, because one launch kind dropped the stack the others carry; or a
    campaign that declares none overriding its profiles' own stack."""
    from squadops.campaigns.launch_requests import (
        bound_launch,
        calibration_launch,
        increment_launch,
    )
    from squadops.campaigns.models import AcceptedTree

    c = campaign(
        CID,
        policy=policy(proposal_profile="campaign-increment", stack=stack),
        accepted=AcceptedTree("sha-1", "cyc_cal"),
    )
    bodies = {
        "calibration": calibration_launch(c).cycle_request["body"],
        "increment": increment_launch(c, MANIFEST).cycle_request["body"],
        "repair": bound_launch(
            c, CycleKind.REPAIR, {"proposal_id": "p"}, ["art_1"], None
        ).cycle_request["body"],
    }

    for kind, body in bodies.items():
        overrides = body["execution_overrides"]
        carried = (overrides.get("build_profile"), overrides.get("development_profile"))
        assert carried == (built_on, built_on), kind


async def test_a_proposal_only_increment_escalates_to_the_owner(calibrating):
    """§24f: until delta framing exists, an increment cycle runs its proposal alone and ends
    with no verdict. Bug caught: that cycle read as accepted (a propose loop that never builds)
    or as rejected (an abandonment counted against a proposal nobody ruled on) — §10 row 14
    escalates it, and the owner holds the proposal."""
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    w.verdict = None
    increment_run = await w.launched_cycle("increment", "cyc_inc", "proposal", "completed")

    await w.end("cyc_inc", increment_run, CycleStopReason.SINGLE_WORKLOAD_ENDED)

    stored = await w.campaigns.get_campaign(CID)
    decision = (await w.campaigns.control_log(CID))[-1]
    assert stored.state is CampaignState.ESCALATED
    assert (decision.binding["row"], decision.binding["action"]) == (14, "escalate")
    assert len(await w.campaigns.launch_intents(CID)) == 2


# --------------------------------------------------------------------------------------------
# §8.4 / §12a: an increment's own acceptance, its promotion and the criteria it freezes
# --------------------------------------------------------------------------------------------

_C1 = "backend/tests/criteria/test_C1.py"


def _evaluation(verdict: str) -> bytes:
    return json.dumps(
        {
            "verdict": verdict,
            "new_bundles": {
                "C1": {
                    "address": "addr-c1",
                    "test_path": _C1,
                    "invocation": ["both"],
                    "files": {_C1: "def test_c1(): ..."},
                }
            },
        }
    ).encode()


def _capacity_request(prd_id: str = "capacity-limit") -> bytes:
    """The reference increment's change request (C1, ``POST /runs``), stored as the gate stores
    an approved one; its PRD section renamed when a second, different document is wanted."""
    from squadops.campaigns.change_request import (
        ProposalContext,
        stored_change_request,
        validate_proposal,
    )

    fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
    authored = yaml.safe_load((fixtures / "reference-capacity-change-request.yaml").read_text())
    authored["prd_delta"][0]["id"] = prd_id
    request = validate_proposal(
        authored,
        ProposalContext(
            "prop_cap",
            1,
            "sha-accepted",
            (fixtures / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text(),
            "fullstack_fastapi_react",
            ("backend/**", "frontend/**"),
            (),
        ),
    ).change_request
    return stored_change_request(request).encode()


@pytest.fixture(autouse=True)
def stored(monkeypatch):
    """A vault per test that can also store (the promotion writes bundles and its tree)."""
    contents = dict(_STORED)
    # This module's own globals: ``_Vault`` reads ``_STORED`` by name at call time.
    monkeypatch.setitem(globals(), "_STORED", contents)

    async def store(self, ref, content):
        contents[ref.artifact_id] = (ref, content)
        return ref

    monkeypatch.setattr(_Vault, "store", store, raising=False)
    return contents


async def _end_increment(calibrating, stored, evaluation: bytes | None):
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    if evaluation is not None:
        stored["art_eval"] = (
            _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 20),
            evaluation,
        )
    increment_run = await w.launched_cycle("increment", "cyc_inc", "implementation", "completed")
    await w.end("cyc_inc", increment_run, CycleStopReason.SEQUENCE_COMPLETED)
    return w


async def test_an_accepted_increment_is_promoted_and_its_criteria_frozen_for_the_next(
    calibrating, stored
):
    """§8.4, §8.1, §12a, entered at the completion hook. Bugs caught: an accepted increment never
    promoted (every later increment proposed against the calibration's tree), its new criterion's
    bundle never stored, or the next increment launched without it — its id reusable and its
    verifier never run again."""
    w = await _end_increment(calibrating, stored, _evaluation("accepted"))

    campaign_now = await w.campaigns.get_campaign(CID)
    log = await w.campaigns.control_log(CID)
    [promote] = [
        e for e in log if e.operation is ControlOperation.PROMOTE and e.target == "cyc_inc"
    ]
    [frozen] = promote.binding["frozen_criteria"]
    bundle_ref, bundle = stored[frozen["bundle_ref"]]
    # #1887: the promotion records the whole tree, and names the record on its row.
    tree_ref, tree = stored[promote.binding["tree_ref"]]
    assert tree_ref.artifact_type == "accepted_tree"
    assert {"backend/routes.py", "frontend/src/App.jsx"} <= set(json.loads(tree))
    assert campaign_now.accepted.cycle_id == "cyc_inc"
    assert (frozen["criterion_id"], frozen["test_path"]) == ("C1", _C1)
    assert (bundle_ref.artifact_type, json.loads(bundle)["files"]) == (
        "verifier_bundle",
        {_C1: "def test_c1(): ..."},
    )
    assert (log[-1].binding["row"], log[-1].binding["action"]) == (7, "propose")
    *_, next_increment = await w.campaigns.launch_intents(CID)
    proposal = next_increment.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert proposal["prior_criteria"] == ["C1"]
    assert proposal["frozen_criteria"][0]["bundle_ref"] == frozen["bundle_ref"]
    assert proposal["accepted_cycle_id"] == "cyc_inc"


class _NoClone:
    """A sample application has no managed clone and no source mappings: any read or move of one
    by its promotion is the bug."""

    def __getattr__(self, name):
        async def reached(*args, **kwargs):
            raise AssertionError(f"a sample application's promotion reached {name}")

        return reached


async def test_a_sample_applications_promotions_stay_the_vaults_with_a_branch_wired(
    calibrating, stored
):
    """§24bv's "What stays": the runtime always wires the campaign branch (§24bv point 2), so this
    world does too, over a clone and mappings that fail on any touch. Bugs caught: a sample
    application's calibration or increment routed onto the branch's path, where it is refused (or
    fails), so the campaign never accepts an increment; or its tree given a commit, which every
    reader then takes for a repository-backed Project's."""
    w, run = await calibrating(
        RunVerdict.ACCEPTED, branch=CampaignBranch(projects=_NoClone(), repository=_NoClone())
    )
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    stored["art_eval"] = (
        _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 20),
        _evaluation("accepted"),
    )
    increment_run = await w.launched_cycle("increment", "cyc_inc", "implementation", "completed")

    await w.end("cyc_inc", increment_run, CycleStopReason.SEQUENCE_COMPLETED)

    log = await w.campaigns.control_log(CID)
    promotions = [e for e in log if e.operation is ControlOperation.PROMOTE]
    stored_campaign = await w.campaigns.get_campaign(CID)
    assert [p.target for p in promotions] == ["cyc_cal", "cyc_inc"]
    assert [("tree_ref" in p.binding, "commit" in p.binding) for p in promotions] == [
        (True, False),
        (True, False),
    ]
    assert stored_campaign.accepted == AcceptedTree(promotions[-1].binding["identity"], "cyc_inc")
    assert (log[-1].binding["row"], log[-1].binding["action"]) == (7, "propose")
    assert "promotion_refused" not in log[-1].binding


async def test_a_frozen_criterion_carries_what_it_asserts_to_the_next_proposal(calibrating, stored):
    """#1938, entered at the completion hook, on the live shape. Bug caught: the next proposal
    told only the frozen criteria's ids. Shakeout 6's strategy role, told "do not break T3",
    re-proposed the feature T3 froze. The promotion freezes each criterion's statement and surface
    from the approved change request, and the next increment's launch carries them.

    The live shape matters: an increment cycle's row carries no plan refs, which ride each run's
    forwarding. The request is on the approved proposal run, promoted, where the seed finds it.
    The first build of this fix read the cycle's refs, passed a test that put them there, and
    on shakeout 6's real records would have frozen ids only."""
    from squadops.campaigns.change_request import (
        ProposalContext,
        stored_change_request,
        validate_proposal,
    )

    fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
    request = validate_proposal(
        yaml.safe_load((fixtures / "reference-capacity-change-request.yaml").read_text()),
        ProposalContext(
            "prop_cap",
            1,
            "sha-accepted",
            (fixtures / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text(),
            "fullstack_fastapi_react",
            ("backend/**", "frontend/**"),
            (),
        ),
    ).change_request
    stored["art_candidate"] = (
        _ref("art_candidate", "interface_manifest.yaml", "interface_manifest", -2),
        MANIFEST.encode(),
    )
    stored["art_cr"] = (
        _ref("art_cr", "change_request.yaml", "change_request", -1),
        stored_change_request(request).encode(),
    )
    stored["art_eval"] = (
        _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 20),
        _evaluation("accepted"),
    )
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    block = {
        "proposal_id": "prop_cap",
        "version": 1,
        "baseline_tree": (await w.campaigns.get_campaign(CID)).accepted.identity,
        "accepted_cycle_id": "cyc_cal",
        "baseline_manifest": MANIFEST,
    }
    increment_run = await w.launched_cycle(
        "increment",
        "cyc_inc",
        "implementation",
        "completed",
        overrides={"campaign_proposal": block},
    )
    await w.cycles.create_run(
        Run(
            run_id="run_prop",
            cycle_id="cyc_inc",
            run_number=0,
            status="completed",
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type="proposal",
        )
    )
    await w.end("cyc_inc", increment_run, CycleStopReason.SEQUENCE_COMPLETED)

    *_, next_increment = await w.campaigns.launch_intents(CID)
    proposal = next_increment.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    [frozen] = proposal["frozen_criteria"]
    assert (frozen["criterion_id"], frozen["statement"], frozen["surface"]) == (
        "C1",
        "A run created with capacity 2 is returned with capacity 2",
        "POST /runs",
    )


async def test_a_promotion_whose_lookup_fails_commits_nothing_and_its_retry_commits_once(
    calibrating, stored, monkeypatch
):
    """#1943, entered at the completion hook and then the startup re-hearing. Bug caught: a lookup
    that failed degraded the binding to ids only and committed. The replay after a restart then
    computed the binding with statements: one key, two bindings, refused (§12a), and the campaign
    never decided. A failing lookup now fails the attempt, which commits nothing, and the
    re-hearing promotes once, with the statements."""
    from squadops.campaigns.change_request import (
        ProposalContext,
        stored_change_request,
        validate_proposal,
    )

    fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
    request = validate_proposal(
        yaml.safe_load((fixtures / "reference-capacity-change-request.yaml").read_text()),
        ProposalContext(
            "prop_cap",
            1,
            "sha-accepted",
            (fixtures / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text(),
            "fullstack_fastapi_react",
            ("backend/**", "frontend/**"),
            (),
        ),
    ).change_request
    stored["art_candidate"] = (
        _ref("art_candidate", "interface_manifest.yaml", "interface_manifest", -2),
        MANIFEST.encode(),
    )
    stored["art_cr"] = (
        _ref("art_cr", "change_request.yaml", "change_request", -1),
        stored_change_request(request).encode(),
    )
    stored["art_eval"] = (
        _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 20),
        _evaluation("accepted"),
    )
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    block = {
        "proposal_id": "prop_cap",
        "version": 1,
        "baseline_tree": (await w.campaigns.get_campaign(CID)).accepted.identity,
        "accepted_cycle_id": "cyc_cal",
        "baseline_manifest": MANIFEST,
    }
    increment_run = await w.launched_cycle(
        "increment",
        "cyc_inc",
        "implementation",
        "completed",
        overrides={"campaign_proposal": block},
    )
    await w.cycles.create_run(
        Run(
            run_id="run_prop",
            cycle_id="cyc_inc",
            run_number=0,
            status="completed",
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type="proposal",
        )
    )
    reads = {"art_cr": 0}
    real_retrieve = _Vault.retrieve

    async def flaky(self, artifact_id):
        if artifact_id == "art_cr":
            reads["art_cr"] += 1
            if reads["art_cr"] == 1:
                raise OSError("the vault read failed once")
        return await real_retrieve(self, artifact_id)

    monkeypatch.setattr(_Vault, "retrieve", flaky)

    def promotions(log):
        return [e for e in log if e.operation is ControlOperation.PROMOTE and e.target == "cyc_inc"]

    await w.end("cyc_inc", increment_run, CycleStopReason.SEQUENCE_COMPLETED)
    after_failure = promotions(await w.campaigns.control_log(CID))
    await w.progress.rehear_ended(["cyc_inc"])

    [promote] = promotions(await w.campaigns.control_log(CID))
    assert after_failure == []
    assert [f["statement"] for f in promote.binding["frozen_criteria"]] == [
        "A run created with capacity 2 is returned with capacity 2"
    ]


@pytest.mark.parametrize(
    "evaluation",
    [_evaluation("blocked_unverified"), None],
    ids=["a-route-nobody-rendered", "never-evaluated"],
)
async def test_an_increment_not_proven_by_its_own_acceptance_is_not_promoted(
    calibrating, stored, evaluation
):
    """§8.4. Bug caught: an increment whose cycle passed its own checks promoted on that alone —
    its new criterion never shown to discriminate, or a declared page never rendered — and the
    next increment built on it. Row 8: repaired, not proposed past."""
    w = await _end_increment(calibrating, stored, evaluation)

    campaign_now = await w.campaigns.get_campaign(CID)
    log = await w.campaigns.control_log(CID)
    assert campaign_now.accepted.cycle_id == "cyc_cal"
    assert not [e for e in log if e.operation is ControlOperation.PROMOTE and e.target == "cyc_inc"]
    assert (log[-1].binding["row"], log[-1].binding["verdict"]) == (8, "blocked_unverified")
    assert not any(r.artifact_type == "verifier_bundle" for r, _ in stored.values())


def _promoted(seq, frozen, retired=()):
    """A PROMOTE row freezing ``frozen`` (criterion id → its bundle ref) and retiring ``retired``."""
    from squadops.campaigns.models import ControlLogEntry, ControlOutcome

    return ControlLogEntry(
        entry_id=f"ctl_{seq}",
        campaign_id=CID,
        seq=seq,
        operation=ControlOperation.PROMOTE,
        actor="squadops",
        actor_role="completion",
        reason="r",
        target=f"cyc_{seq}",
        idempotency_key=f"promote:{seq}",
        request_hash="h",
        binding={
            "frozen_criteria": [
                {"criterion_id": c, "bundle_ref": ref} for c, ref in frozen.items()
            ],
            "retired_criteria": list(retired),
        },
        outcome=ControlOutcome.APPLIED,
        refusal=None,
        prior_state=CampaignState.PROMOTING,
        next_state=CampaignState.AT_PROPOSAL,
        committed_at=NOW,
    )


def test_a_retired_criterion_leaves_the_frozen_set_and_a_later_one_takes_its_place():
    """§8.1. Bug caught: a criterion an increment retired still pinned for every later launch —
    run on every candidate and blocking the very change that ruled it out."""
    from squadops.campaigns.progress import frozen_criteria

    log = [
        _promoted(1, {"C1": "art_C1", "C2": "art_C2"}),
        _promoted(2, {"C3": "art_C3"}, retired=["C1"]),
    ]

    assert [f["criterion_id"] for f in frozen_criteria(log)] == ["C2", "C3"]


def test_a_replaced_verifier_is_frozen_again_under_its_new_bundle():
    """§8.1: "the old bundle is retired and the new one frozen", in one promotion. Bugs caught:
    the replaced criterion dropped altogether (retired and never frozen again), or kept under the
    bundle it was replaced from."""
    from squadops.campaigns.progress import frozen_criteria

    log = [
        _promoted(1, {"F1": "art_f1_old", "F2": "art_f2"}),
        _promoted(2, {"F1": "art_f1_new"}, retired=["F1"]),
    ]

    assert [(f["criterion_id"], f["bundle_ref"]) for f in frozen_criteria(log)] == [
        ("F2", "art_f2"),
        ("F1", "art_f1_new"),
    ]


# --------------------------------------------------------------------------------------------
# §10a: a retry reuses the increment's bound change request, ruling, baseline and footprint
# --------------------------------------------------------------------------------------------


def _environment_failure(cycle_id):
    """A rejected cycle whose primary cause is the environment: §10 rows 10/11."""
    import dataclasses as _dc

    from squadops.cycles.cycle_assessment import AttributionReading, IndicatorState
    from squadops.cycles.failure_attribution import Attribution, AttributionClass

    return _dc.replace(
        _assessment(cycle_id, RunVerdict.REJECTED),
        attribution=AttributionReading(
            IndicatorState.OBSERVED,
            Attribution(
                primary=AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE, contributing=()
            ),
        ),
    )


async def _increment_failed_by_the_environment(
    calibrating,
    stored,
    *,
    ruled="approved",
    moved=False,
    environment=True,
    reasons=(),
    loop_summary=None,
    assessed=RunVerdict.REJECTED,
    frozen=(),
    evaluation=None,
    repair_of=None,
    extra_block=None,
    **policy,
):
    """An accepted calibration, an increment proposed against its tree and ruled on, built, and
    rejected for a cause outside the work. Its approved seeds are stored, as the gate stores
    them; created before the calibration's manifest, so the calibration's stays the latest.

    ``assessed`` is the cycle's own verdict when the cause is the work, ``frozen`` the criteria
    earlier promotions froze (carried on its bound proposal), and ``evaluation`` the increment
    evaluation its run stored, if any (#2318). With ``repair_of``, the failed cycle is a repair
    of that cycle, bound as a repair's launch binds it: it continues that cycle, and carries its
    brief."""
    stored["art_candidate"] = (
        _ref("art_candidate", "interface_manifest.yaml", "interface_manifest", -2),
        MANIFEST.encode(),
    )
    stored["art_cr"] = (
        _ref("art_cr", "change_request.yaml", "change_request", -1),
        _capacity_request(),
    )
    from squadops.campaigns.gate import RETURNING_DECISIONS, ruling_transition, submission
    from squadops.campaigns.models import ProposalBinding, SubmittedProposal
    from squadops.cycles.models import GateDecisionValue

    w, run = await calibrating(RunVerdict.ACCEPTED, **policy)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    accepted = (await w.campaigns.get_campaign(CID)).accepted.identity
    block = {
        "proposal_id": "prop_cap",
        "version": 1,
        "baseline_tree": "an-older-tree" if moved else accepted,
        "accepted_cycle_id": "cyc_cal",
        "baseline_manifest": MANIFEST,
        **({"frozen_criteria": list(frozen)} if frozen else {}),
        **(
            {
                "repair_of": repair_of,
                "continues": repair_of,
                "prior_cycle": {"cycle_id": repair_of, "verdict": "rejected"},
            }
            if repair_of
            else {}
        ),
        **(extra_block or {}),
    }
    if evaluation is not None:
        stored["art_eval"] = (
            _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 20),
            evaluation,
        )
    increment_run = await w.launched_cycle(
        "repair" if repair_of else "increment",
        "cyc_inc",
        "implementation",
        "completed",
        overrides={
            "campaign_proposal": block,
            "plan_artifact_refs": ["art_candidate", "art_cr"],
            "contract_ref": "art_contract",
        },
        intent_kind="increment",
    )
    if reasons:
        from squadops.cycles.verification_integrity import RunVerificationSummary

        await w.cycles.record_run_verification_summary(
            increment_run.run_id,
            RunVerificationSummary(
                verdict=RunVerdict.REJECTED,
                verified=(),
                failed=tuple(r.check_id for r in reasons),
                unverified=(),
                required_unmet=(),
                executed_count=len(reasons),
                passed_count=0,
                failed_detail=tuple(reasons),
            ),
        )
    if loop_summary is not None:
        await w.cycles.record_run_loop_summary(increment_run.run_id, loop_summary)
    binding = ProposalBinding("prop_cap", 1, "hash-1", accepted)
    state = (await w.campaigns.get_campaign(CID)).state
    await w.campaigns.transition(
        CID, submission(state, SubmittedProposal(binding, "cyc_inc", "run_prop"))
    )
    await w.campaigns.transition(
        CID,
        ruling_transition(
            GateDecisionValue(ruled),
            binding,
            run_id="run_prop",
            actor="supervisor",
            actor_role="campaign_supervisor",
            reason="r",
            idempotency_key="rule-1",
            classification=(
                "scope_too_large" if GateDecisionValue(ruled) in RETURNING_DECISIONS else None
            ),
        ),
    )
    w._assess = lambda cycle_id: _async(
        _environment_failure(cycle_id) if environment else _assessment(cycle_id, assessed)
    )
    w.progress._assess = w._assess
    await w.end("cyc_inc", increment_run, CycleStopReason.SEQUENCE_COMPLETED)
    return w


async def _async(value):
    return value


async def test_an_environment_failure_is_retried_with_the_bound_request_and_no_new_ruling(
    calibrating, stored
):
    """§10 row 10, §10a. Bugs caught: a retry that re-proposes (a new ruling for the same change),
    one built from a stale baseline, or one that runs the proposal workload again — or one told
    which check failed and not why (#1692)."""
    from squadops.cycles.verification_integrity import FailedCheck

    w = await _increment_failed_by_the_environment(
        calibrating,
        stored,
        reasons=(FailedCheck("tests_pass", "POST /runs returned 422, expected 201", True),),
    )

    stored = await w.campaigns.get_campaign(CID)
    decision = (await w.campaigns.control_log(CID))[-1]
    *_, retry = await w.campaigns.launch_intents(CID)
    body = retry.cycle_request["body"]
    overrides = body["execution_overrides"]
    assert (decision.binding["row"], decision.binding["action"]) == (10, "retry")
    assert stored.state is CampaignState.RETRYING
    assert retry.cycle_kind is CycleKind.RETRY
    assert overrides["campaign_proposal"]["proposal_id"] == "prop_cap"
    assert (overrides["plan_artifact_refs"], overrides["contract_ref"]) == (
        ["art_candidate", "art_cr"],
        "art_contract",
    )
    assert [w["type"] for w in overrides["workload_sequence"]] == ["framing", "implementation"]
    # #1692: the retry is told what the cycle it recovers from recorded.
    prior = overrides["campaign_proposal"]["prior_cycle"]
    assert (prior["cycle_id"], prior["verdict"], prior["primary_cause"]) == (
        "cyc_inc",
        "rejected",
        "environment_or_infrastructure_failure",
    )
    assert prior["why_failed"] == [
        {
            "check_id": "tests_pass",
            "reason": "POST /runs returned 422, expected 201",
            "contested": False,
        }
    ]


@pytest.mark.parametrize(
    "records", ["read", "unreadable", "malformed"], ids=lambda r: f"records-{r}"
)
async def test_an_owners_retry_carries_the_brief_and_is_never_blocked_by_it(
    calibrating, stored, records
):
    """#1692, entered at the owner's word (``owner_action``), which has no assessment in hand.
    Bugs caught: an owner's retry launched without the brief a decided one carries; or a
    resume refused because the failed cycle's records could not be read for an aid."""
    from squadops.campaigns.continuation import PendingAction

    w = await _increment_failed_by_the_environment(calibrating, stored)
    if records == "unreadable":
        w.progress._assess = AsyncMock(side_effect=RuntimeError("the assessment store is down"))
    if records == "malformed":
        w.progress._assess = AsyncMock(return_value=object())  # read, and nothing to derive from

    transition = await w.progress.owner_action(
        await w.campaigns.get_campaign(CID),
        PendingAction.RETRY,
        held=False,
        actor="owner",
        actor_role="admin",
        reason="r",
        idempotency_key="owner-retry",
    )

    block = transition.launch.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert transition.launch.cycle_kind is CycleKind.RETRY
    # SIP-0110 §3.7 (#2178): the owner's word's row names no cycle, so the request does, read
    # or not, for the carried task instructions.
    assert block["continues"] == "cyc_inc"
    expected = "cyc_inc" if records == "read" else None
    assert (block.get("prior_cycle") or {}).get("cycle_id") == expected


async def test_an_abandoned_increments_record_reaches_the_next_proposal_and_no_other_task(
    calibrating, stored
):
    """§10 row 13, §7 (#1692), entered at the completion hook: a rejected increment with no
    repair left is abandoned, and the fresh proposal is told why. Bugs caught: the next proposal
    as blind as the last; or the record carried as ``prior_cycle``, which would tell every author
    of the new, different increment that it was attempted before."""
    from squadops.cycles.verification_integrity import FailedCheck

    w = await _increment_failed_by_the_environment(
        calibrating,
        stored,
        environment=False,
        reasons=(FailedCheck("tests_pass", "POST /runs returned 422, expected 201", True),),
        max_repair_cycles_per_increment=0,
    )

    decision = (await w.campaigns.control_log(CID))[-1]
    *_, proposal = await w.campaigns.launch_intents(CID)
    block = proposal.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert (decision.binding["row"], decision.binding["action"]) == (13, "abandon_and_propose")
    assert proposal.cycle_kind is CycleKind.INCREMENT
    assert block["abandoned_increment"]["cycle_id"] == "cyc_inc"
    assert block["abandoned_increment"]["why_failed"][0]["check_id"] == "tests_pass"
    assert "prior_cycle" not in block


_PRIORITY = "Priority order: an Expansion Tier 2 change while Tier 1 is incomplete."


async def _rejected_at_the_gate(calibrating, stored):
    """An accepted calibration, then an increment whose proposal run (``run_prop``, its own
    change request among its artifacts) is rejected at the gate. A newer change request stored
    under the cycle's other run is the decoy a lookup by cycle, or by type alone, would read.
    Returns the world and the proposal run, before the cycle ends."""
    import dataclasses as _dc

    from squadops.campaigns.gate import ruling_transition, submission
    from squadops.campaigns.models import ProposalBinding, SubmittedProposal
    from squadops.cycles.models import GateDecisionValue

    stored["art_cr"] = (
        _dc.replace(
            _ref("art_cr", "change_request.yaml", "change_request", 30),
            cycle_id="cyc_inc",
            run_id="run_prop",
        ),
        _capacity_request(),
    )
    stored["art_decoy"] = (
        _dc.replace(
            _ref("art_decoy", "change_request.yaml", "change_request", 40), cycle_id="cyc_inc"
        ),
        _capacity_request("not-the-ruled-request"),
    )
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    accepted = (await w.campaigns.get_campaign(CID)).accepted.identity
    await w.launched_cycle("increment", "cyc_inc", "proposal", "completed")
    proposal_run = Run(
        run_id="run_prop",
        cycle_id="cyc_inc",
        run_number=2,
        status="completed",
        initiated_by="system",
        resolved_config_hash="cfg",
        workload_type="proposal",
        artifact_refs=("art_cr",),
    )
    await w.cycles.create_run(proposal_run)
    binding = ProposalBinding("prop_cap", 1, "hash-1", accepted)
    state = (await w.campaigns.get_campaign(CID)).state
    await w.campaigns.transition(
        CID, submission(state, SubmittedProposal(binding, "cyc_inc", "run_prop"))
    )
    await w.campaigns.transition(
        CID,
        ruling_transition(
            GateDecisionValue.REJECTED,
            binding,
            run_id="run_prop",
            actor="supervisor",
            actor_role="campaign_supervisor",
            reason=_PRIORITY,
            idempotency_key="rule-1",
            classification="unclassified",
            classification_rationale="Priority order is none of the classes.",
        ),
    )
    return w, proposal_run


async def test_a_rejected_proposals_reason_reaches_the_fresh_proposal_after_it(calibrating, stored):
    """#2593, the 2.4 window's campaign 4, entered at the completion hook as the rejected
    proposal's cycle ends; row 6 launches a fresh proposal. Bugs caught: the fresh proposal told
    nothing of the rejection (campaign 4 proposed one rejected change in four of its five
    proposals); told the ruling without what was rejected; or shown another run's request (the
    decoy), not the document the ruling bound to."""
    w, proposal_run = await _rejected_at_the_gate(calibrating, stored)

    await w.end("cyc_inc", proposal_run, CycleStopReason.GATE_REJECTED)

    decision = (await w.campaigns.control_log(CID))[-1]
    *_, fresh = await w.campaigns.launch_intents(CID)
    block = fresh.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert (decision.binding["row"], decision.binding["action"]) == (6, "propose")
    [shown] = block["unapproved_proposals"]
    assert {k: v for k, v in shown.items() if k not in ("prd_delta", "criteria")} == {
        "proposal_id": "prop_cap",
        "version": 1,
        "decision": "rejected",
        "reason": _PRIORITY,
        "ruled_on_current_application": True,
        "classification": "unclassified",
        "classification_rationale": "Priority order is none of the classes.",
    }
    assert [(s["id"], s["op"]) for s in shown["prd_delta"]] == [("capacity-limit", "add")]
    assert [c["id"] for c in shown["criteria"]] == ["C1", "C2", "C3"]


async def test_a_ruled_request_whose_read_fails_launches_nothing_and_the_rehearing_shows_it(
    calibrating, stored, monkeypatch
):
    """#2593, the launch's rule for its inputs (the 2.1 plan, ``_propose_launch``): a vault read
    that fails raises, and the re-hearing retries. Bug caught: a proposal launched without what
    the ruling rejected because one read failed, which no later launch would ever restore."""
    w, proposal_run = await _rejected_at_the_gate(calibrating, stored)
    reads = {"art_cr": 0}
    real_retrieve = _Vault.retrieve

    async def flaky(self, artifact_id):
        if artifact_id == "art_cr":
            reads["art_cr"] += 1
            if reads["art_cr"] == 1:
                raise OSError("the vault read failed once")
        return await real_retrieve(self, artifact_id)

    monkeypatch.setattr(_Vault, "retrieve", flaky)
    launched_before = len(await w.campaigns.launch_intents(CID))

    await w.end("cyc_inc", proposal_run, CycleStopReason.GATE_REJECTED)
    after_failure = len(await w.campaigns.launch_intents(CID))
    await w.progress.rehear_ended(["cyc_inc"])

    *_, fresh = await w.campaigns.launch_intents(CID)
    block = fresh.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert after_failure == launched_before
    assert [s["id"] for s in block["unapproved_proposals"][0]["prd_delta"]] == ["capacity-limit"]


async def test_a_retry_of_a_repair_starts_from_the_accepted_tree(calibrating, stored, monkeypatch):
    """§10a, #2558, entered at the continuation decision. Bug caught: a retry of a repair that
    failed for a cause outside the work keeping the repair's ``repair_of``, so it starts from the
    original increment's failed candidate rather than a fresh one on the accepted tree."""
    from types import SimpleNamespace

    from squadops.campaigns import increment_tree

    w = await _increment_failed_by_the_environment(calibrating, stored, repair_of="cyc_first")

    decision = (await w.campaigns.control_log(CID))[-1]
    *_, retry = await w.campaigns.launch_intents(CID)
    overrides = retry.cycle_request["body"]["execution_overrides"]
    assert (decision.binding["row"], decision.binding["action"]) == (10, "retry")
    assert retry.cycle_kind is CycleKind.RETRY
    assert "repair_of" not in overrides["campaign_proposal"]
    assert overrides["campaign_proposal"]["continues"] == "cyc_inc"
    assert overrides["campaign_proposal"]["prior_cycle"]["cycle_id"] == "cyc_inc"

    async def accepted(_vault, _cycle, _frozen):
        return ["art_accepted_routes"]

    async def delivered(_vault, cycle_id):
        return {"backend/routes.py": f"art_{cycle_id}_routes"}

    monkeypatch.setattr(increment_tree, "accepted_tree_refs", accepted)
    monkeypatch.setattr(increment_tree, "_delivered", delivered)
    retry_cycle = SimpleNamespace(resolved_config=lambda: overrides)
    assert await increment_tree.starting_tree_refs(None, retry_cycle) == ["art_accepted_routes"]


@pytest.mark.parametrize("repair_of", [None, "cyc_first"], ids=["of-an-increment", "of-a-repair"])
async def test_a_continuation_carries_the_increments_keys_and_its_own_lineage_and_nothing_else(
    calibrating, stored, repair_of
):
    """#2578, entered at the continuation decision. Bug caught: a continuation built by copying the
    failed cycle's block and deleting from it, so a key only a proposal reads, or a lineage key
    added later, rides into every repair and retry by default (the class of #2558 and #2576)."""
    w = await _increment_failed_by_the_environment(
        calibrating,
        stored,
        repair_of=repair_of,
        extra_block={
            "abandoned_increment": {"cycle_id": "cyc_old"},
            "qa_proposed_behaviours": [{"behaviour": "a sorted list"}],
            "unapproved_proposals": [{"proposal_id": "prop_old"}],
            "supervisor_note": "narrow it",
            "a_lineage_key_added_later": "cyc_first",
        },
    )

    *_, retry = await w.campaigns.launch_intents(CID)
    block = retry.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert retry.cycle_kind is CycleKind.RETRY
    assert sorted(block) == sorted(
        ["proposal_id", "version", "baseline_tree", "accepted_cycle_id", "baseline_manifest"]
        + ["continues", "prior_cycle"]
    )
    assert (block["continues"], block["prior_cycle"]["cycle_id"]) == ("cyc_inc", "cyc_inc")


async def test_a_retry_whose_failed_cycle_cant_be_read_carries_no_brief_not_an_older_one(
    calibrating, stored, monkeypatch
):
    """§24u, #2576. Bug caught: a retry of a repair whose records can't be read keeping the
    repair's own brief, of the increment it repaired, so the retry's authors are shown that
    cycle's failures as the one they recover from."""
    from squadops.campaigns import progress

    async def unreadable(*args, **kwargs):
        raise TimeoutError("the cycle registry did not answer")

    original = progress.CampaignProgress._prior_cycle_brief

    async def brief_unreadable(self, cycle, latest):
        self._cycles.list_run_verification_summaries = unreadable
        return await original(self, cycle, latest)

    monkeypatch.setattr(progress.CampaignProgress, "_prior_cycle_brief", brief_unreadable)
    w = await _increment_failed_by_the_environment(calibrating, stored, repair_of="cyc_first")

    *_, retry = await w.campaigns.launch_intents(CID)
    block = retry.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert retry.cycle_kind is CycleKind.RETRY
    assert "prior_cycle" not in block


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        (dict(moved=True), "the bound ruling no longer matches"),
        (dict(ruled="returned_for_revision"), "no approving ruling is on record"),
    ],
    ids=["the-baseline-moved", "never-approved"],
)
async def test_a_retry_whose_binding_no_longer_holds_escalates_instead(
    calibrating, stored, kwargs, reason
):
    """§10a: a mismatch refuses the cycle. Bug caught: a retry built on a baseline that moved, or
    on a version nobody approved — scope changed without a ruling."""
    w = await _increment_failed_by_the_environment(calibrating, stored, **kwargs)

    stored = await w.campaigns.get_campaign(CID)
    decision = (await w.campaigns.control_log(CID))[-1]
    assert stored.state is CampaignState.ESCALATED
    assert reason in decision.binding["unbuilt"]


async def test_a_rejected_increment_is_repaired_from_its_own_candidate_under_its_plan(
    calibrating, stored
):
    """§10 row 12, §10a. Bugs caught: a repair that frames afresh (a retry by another name), one
    built without the plan the failed cycle was approved under, or one that starts from the
    accepted tree and so throws the failed work away."""
    import dataclasses as _dc

    stored["art_plan"] = (
        _dc.replace(
            _ref("art_plan", "implementation_plan.yaml", "control_implementation_plan", 5),
            promotion_status="promoted",
        ),
        b"version: 1",
    )
    w = await _increment_failed_by_the_environment(calibrating, stored, environment=False)

    decision = (await w.campaigns.control_log(CID))[-1]
    *_, repair = await w.campaigns.launch_intents(CID)
    overrides = repair.cycle_request["body"]["execution_overrides"]
    assert (decision.binding["row"], decision.binding["action"]) == (12, "repair")
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.REPAIRING
    assert repair.cycle_kind is CycleKind.REPAIR
    assert overrides["campaign_proposal"]["repair_of"] == "cyc_inc"
    assert overrides["campaign_proposal"]["continues"] == "cyc_inc"  # SIP-0110 §3.7's carry
    assert overrides["campaign_proposal"]["prior_cycle"]["cycle_id"] == "cyc_inc"
    assert overrides["plan_artifact_refs"] == ["art_candidate", "art_cr", "art_plan"]
    assert [w["type"] for w in overrides["workload_sequence"]] == ["implementation"]


#: The frozen criterion the 2.3 cut's shakeout broke (``cmp_27dba15dea9a``, increment 2), as the
#: promotion froze it and the evaluation judged it.
_FROZEN_T2 = {
    "criterion_id": "T2",
    "statement": "A third join to a run with capacity 2 is refused",
    "surface": "POST /runs/{run_id}/join",
    "test_path": "backend/tests/criteria/test_T2.py",
    "bundle_address": "1bbf6dff",
}


def _t2_broken() -> bytes:
    return _rejection(
        frozen=[
            {
                "criterion_id": "T2",
                "bundle_address": "1bbf6dff",
                "held": "broken",
                "detail": "test_guard_ordering_capacity_before_duplicate",
            }
        ],
    )


@pytest.mark.parametrize("successor", ["repair", "next-proposal"])
async def test_an_increment_its_evaluation_rejected_tells_its_successor_why(
    calibrating, stored, successor
):
    """#2318, entered at the completion hook, on the 2.3 cut shakeout's case: a build that passed
    every check of its own, rejected by its increment's evaluation because it broke a frozen
    criterion. Bug caught: the successor told the cycle passed. There, a repair so briefed broke
    the same frozen test again, and the increment was abandoned."""
    import dataclasses as _dc

    from squadops.campaigns.prior_cycle import brief_lines

    stored["art_plan"] = (
        _dc.replace(
            _ref("art_plan", "implementation_plan.yaml", "control_implementation_plan", 5),
            promotion_status="promoted",
        ),
        b"version: 1",
    )
    w = await _increment_failed_by_the_environment(
        calibrating,
        stored,
        environment=False,
        assessed=RunVerdict.ACCEPTED,
        frozen=(_FROZEN_T2,),
        evaluation=_t2_broken(),
        **({} if successor == "repair" else {"max_repair_cycles_per_increment": 0}),
    )

    decision = (await w.campaigns.control_log(CID))[-1]
    *_, launched = await w.campaigns.launch_intents(CID)
    block = launched.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    if successor == "repair":
        assert (decision.binding["row"], decision.binding["action"]) == (12, "repair")
        brief = block["prior_cycle"]
    else:
        assert (decision.binding["row"], decision.binding["action"]) == (13, "abandon_and_propose")
        brief = block["abandoned_increment"]
    assert decision.binding["verdict"] == "rejected"
    assert brief["verdict"] == "accepted"  # the build's own checks, still shown as they read
    assert brief["evaluation"] == {
        "verdict": "rejected",
        "frozen_broken": [
            {
                "criterion_id": "T2",
                "statement": "A third join to a run with capacity 2 is refused",
                "surface": "POST /runs/{run_id}/join",
                "held": "broken",
                "detail": "test_guard_ordering_capacity_before_duplicate",
            }
        ],
    }
    assert (
        "- frozen `T2` on `POST /runs/{run_id}/join`: A third join to a run with capacity 2 is "
        "refused — `broken`; failing: test_guard_ordering_capacity_before_duplicate"
    ) in brief_lines(brief)


async def test_a_repair_with_no_approved_plan_escalates(calibrating, stored):
    w = await _increment_failed_by_the_environment(calibrating, stored, environment=False)

    decision = (await w.campaigns.control_log(CID))[-1]
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.ESCALATED
    assert "no approved implementation plan" in decision.binding["unbuilt"]


# --- §24ad (#1885): a question the accepted cycle's gate answered is not asked again ---------

_FIXTURES = __import__("pathlib").Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
#: Shakeout 4's calibration (``cyc_cc0909f2689a``): its manifest left ``run-list-ordering``
#: open, and its plan gate was answered at 05:41Z with these notes.
_OPEN_MANIFEST = (_FIXTURES / "manifest-cyc_cc0909f2689a-open-question.yaml").read_text()
_ANSWER = (
    "Campaign shakeout cmp_be852b0f08f0 calibration (uncounted). Approved under the 2.0 "
    "regression set's gate policy: system plan validation passed; no additional judgment "
    "applied. The open design question (run-list-ordering) is left to the implementation, as "
    "on every roll."
)


async def _answered_calibration(
    calibrating,
    monkeypatch,
    *,
    decided_by: str,
    notes: str | None,
    late_answer: tuple[str, str] | tuple[str, str, str] | None = None,
    **policy_overrides,
):
    """The calibration accepted on ``_OPEN_MANIFEST`` and its gate decided, then its cycle ended.
    ``late_answer`` (question, answer) first records an earlier campaign of the project whose
    escalation on ``run-list-ordering`` expired and was answered late (SIP-0109 §24bm)."""
    from squadops.cycles.models import GateDecision

    monkeypatch.setitem(
        _STORED,
        "art_manifest",
        (
            _ref("art_manifest", "interface_manifest.yaml", "interface_manifest", 0),
            _OPEN_MANIFEST.encode(),
        ),
    )
    w, run = await calibrating(RunVerdict.ACCEPTED, **policy_overrides)
    if late_answer is not None:
        await _a_late_answer_on_record(w.campaigns, *late_answer)
    await w.cycles.create_run(
        Run(
            run_id="run_frame",
            cycle_id="cyc_cal",
            run_number=0,
            status="completed",
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type="framing",
        )
    )
    await w.cycles.record_gate_decision(
        "run_frame",
        GateDecision(
            gate_name="progress_plan_review",
            decision="approved",
            decided_by=decided_by,
            decided_at=datetime(2026, 10, 3, 5, 41, 35, tzinfo=UTC),
            notes=notes,
        ),
    )
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    [_, increment] = await w.campaigns.launch_intents(CID)
    return increment.cycle_request["body"]["execution_overrides"]["campaign_proposal"]


async def _a_late_answer_on_record(
    campaigns, question: str, answer: str, decision_id: str = "run-list-ordering"
) -> str:
    """An earlier campaign of the project whose escalation on ``decision_id`` (asked as
    ``question``) expired, and which the owner answered late. Returns the escalation's id."""
    from squadops.campaigns.escalation import (
        EscalationIdentity,
        answer_transition,
        escalations,
        opening_transition,
    )
    from squadops.campaigns.models import CampaignTransition, ControlOperation, CycleKind, PlanGate
    from squadops.campaigns.plan_review_tier import plan_review_tier

    prior = "cmp_prior0000001"
    await campaigns.create_campaign(
        campaign(prior, policy=policy(plan_gate=PlanGate.TIER)),
        actor="owner",
        actor_role="owner",
        reason="r",
        idempotency_key="create-prior",
    )
    identity = EscalationIdentity(
        prior, "cyc_prior", "run_prior", "progress_plan_review", None, None, None, "p"
    )
    verdict = plan_review_tier(
        kind=CycleKind.CALIBRATION,
        open_questions=(question,),
        footprint=("backend/main.py",),
        allowed_scope=("backend/**",),
        stack="fullstack_fastapi_react",
        refused_framing_runs=(),
        answered_on_record={},
    )
    await campaigns.transition(
        prior, opening_transition(identity, verdict, ((decision_id, question),), NOW)
    )
    await campaigns.transition(
        prior,
        CampaignTransition(
            operation=ControlOperation.ESCALATION_CLOSED,
            actor="squadops",
            actor_role="sweep",
            reason="the bound passed",
            idempotency_key=f"escalation_closed:{identity.escalation_id}",
            next_state=None,
            target="run_prior",
            binding={"escalation_id": identity.escalation_id, "state": "expired"},
        ),
    )
    [expired] = escalations(await campaigns.control_log(prior), CampaignState.DRAFT)
    await campaigns.transition(
        prior,
        answer_transition(
            expired,
            {decision_id: answer},
            actor="human:owner",
            actor_role="owner",
            reason="late",
        ),
    )
    return identity.escalation_id


async def test_an_answered_question_reaches_the_increment_resolved(calibrating, monkeypatch):
    """#1885, read in shakeouts 3 and 4: the accepted manifest kept its answered question
    ``unresolved``, so every increment's candidate (the accepted manifest plus its delta) asked
    it again and its plan gate stopped for a human. Entered at ``CycleCompletion.end`` on the
    real records: shakeout 4's calibration manifest and its increment 1's approved delta. Bug
    caught: the proposal's baseline carrying the question, so the candidate does too."""
    from squadops.campaigns.change_request import (
        apply_manifest_delta,
        load_stored_change_request,
    )
    from squadops.cycles.manifest_authoring import open_questions

    proposal = await _answered_calibration(
        calibrating, monkeypatch, decided_by="agent:005159fd", notes=_ANSWER
    )

    baseline = proposal["baseline_manifest"]
    [decision] = [
        d for d in yaml.safe_load(baseline)["decisions"] if d["id"] == "run-list-ordering"
    ]
    assert decision["choice"] == _ANSWER
    assert decision["warrant"].startswith(
        "answered at cyc_cal's plan gate by agent:005159fd at 2026-10-03T05:41:35+00:00; "
        "the question was: PRD does not specify a guaranteed sort order"
    )
    assert "unresolved" not in decision and "question" not in decision
    delta = load_stored_change_request(
        (_FIXTURES / "change-request-prop_567c4915dbc0.yaml").read_text()
    ).manifest_delta
    assert open_questions(apply_manifest_delta(baseline, delta)) == ()


@pytest.mark.parametrize(
    ("decided_by", "notes"),
    [("system:no_open_questions", _ANSWER), ("agent:005159fd", None), ("agent:005159fd", " ")],
    ids=["a machine pass-through", "an approval with no notes", "blank notes"],
)
async def test_no_stated_answer_leaves_the_question_open(
    calibrating, monkeypatch, decided_by, notes
):
    """The edge: only a principal's approval that states something answers a question. Bug
    caught: a question resolved by a decision that answered nothing, so a human ruling is
    invented and the increment never asks."""
    proposal = await _answered_calibration(
        calibrating, monkeypatch, decided_by=decided_by, notes=notes
    )

    assert proposal["baseline_manifest"] == _OPEN_MANIFEST


def test_a_manifest_with_no_open_question_is_carried_byte_for_byte():
    """The other edge: an answer on record and nothing left to resolve, as on every increment
    after the first. Bug caught: a manifest re-dumped (key order, quoting) on every proposal,
    so the accepted manifest's text drifts with no change to the design."""
    from squadops.cycles.manifest_authoring import resolve_answered_questions

    resolved = resolve_answered_questions(
        _OPEN_MANIFEST, answer=_ANSWER, answered_by="agent:a", answered_at="t", where="cyc_cal"
    )
    again = resolve_answered_questions(
        resolved, answer="a later answer", answered_by="agent:b", answered_at="u", where="cyc_x"
    )

    assert again is resolved


async def test_an_accepted_repair_proposes_from_the_manifest_it_ran_against(
    calibrating, stored, monkeypatch
):
    """#1902, shakeout 4 (control-log seq 14): the repair cycle was accepted and promoted, and
    the next proposal escalated, "the accepted cycle stored no interface manifest". A repair
    reuses its increment's approved seeds and stores none of its own, and the proposal read the
    accepted cycle's own artifacts only. Entered at ``CycleCompletion.end`` for the repair, over
    a vault that answers by cycle, as the live one does (this module's ``_Vault`` hands every
    artifact to every cycle, which is how the defect passed). Bugs caught: an accepted repair
    escalating instead of proposing; the increment's answered question asked again because the
    repair, which runs no framing, has no gate of its own to read the answer from."""
    import dataclasses as _dc

    from squadops.cycles.manifest_authoring import open_questions
    from squadops.cycles.models import GateDecision

    stored["art_plan"] = (
        _dc.replace(
            _ref("art_plan", "implementation_plan.yaml", "control_implementation_plan", 5),
            promotion_status="promoted",
        ),
        b"version: 1",
    )
    w = await _increment_failed_by_the_environment(calibrating, stored, environment=False)
    # The approved seed, as the gate stored it under the increment: shakeout 4's real manifest.
    stored["art_candidate"] = (
        _dc.replace(
            _ref("art_candidate", "interface_manifest.yaml", "interface_manifest", -2),
            cycle_id="cyc_inc",
        ),
        _OPEN_MANIFEST.encode(),
    )
    # The increment's framing gate answered the open question.
    await w.cycles.create_run(
        Run(
            run_id="run_inc_frame",
            cycle_id="cyc_inc",
            run_number=0,
            status="completed",
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type="framing",
        )
    )
    await w.cycles.record_gate_decision(
        "run_inc_frame",
        GateDecision(
            gate_name="progress_plan_review",
            decision="approved",
            decided_by="agent:005159fd",
            decided_at=datetime(2026, 10, 3, 6, 35, tzinfo=UTC),
            notes=_ANSWER,
        ),
    )
    *_, repair = await w.campaigns.launch_intents(CID)
    stored["art_eval"] = (
        _dc.replace(
            _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 30),
            cycle_id="cyc_rep",
        ),
        _evaluation("accepted"),
    )

    async def by_cycle(self, *, cycle_id=None, run_id=None, **_):
        return [
            ref
            for ref, _content in _STORED.values()
            if cycle_id in (None, ref.cycle_id) and run_id in (None, ref.run_id)
        ]

    monkeypatch.setattr(_Vault, "list_artifacts", by_cycle)
    repair_run = await w.launched_cycle(
        "repair",
        "cyc_rep",
        "implementation",
        "completed",
        overrides=repair.cycle_request["body"]["execution_overrides"],
    )
    w._assess = lambda cycle_id: _async(_assessment(cycle_id, RunVerdict.ACCEPTED))
    w.progress._assess = w._assess

    await w.end("cyc_rep", repair_run, CycleStopReason.SEQUENCE_COMPLETED)

    stored_campaign = await w.campaigns.get_campaign(CID)
    decision = (await w.campaigns.control_log(CID))[-1]
    assert stored_campaign.accepted.cycle_id == "cyc_rep"
    assert (decision.binding["row"], decision.binding["action"]) == (7, "propose")
    assert "unbuilt" not in decision.binding
    assert stored_campaign.state is CampaignState.AT_PROPOSAL
    *_, increment = await w.campaigns.launch_intents(CID)
    baseline = increment.cycle_request["body"]["execution_overrides"]["campaign_proposal"][
        "baseline_manifest"
    ]
    assert open_questions(baseline) == ()
    [decision] = [
        d for d in yaml.safe_load(baseline)["decisions"] if d["id"] == "run-list-ordering"
    ]
    assert decision["warrant"].startswith("answered at cyc_inc's plan gate by agent:005159fd")


@pytest.mark.parametrize("kind", ["repair", "retry"])
async def test_an_accepted_repair_or_retry_freezes_its_criteria_with_what_they_assert(
    calibrating, stored, monkeypatch, kind
):
    """#2595, the 2.4 window's campaign 3, entered at ``CycleCompletion.end`` for the successor
    over a vault that answers by cycle. A repair or a retry runs no proposal: its launch carries
    the increment's approved seeds, as the live repair row did (``plan_artifact_refs``: the
    manifest, the change request and, for a repair, the plan). Bug caught: the promotion read
    each criterion's statement through the proposal only, froze the successor's criterion with
    none, and the evidence digest's ``KeyError`` on it meant the campaign's package was never
    stored."""
    import dataclasses as _dc

    stored["art_plan"] = (
        _dc.replace(
            _ref("art_plan", "implementation_plan.yaml", "control_implementation_plan", 5),
            promotion_status="promoted",
        ),
        b"version: 1",
    )
    # The environment failing is a retry's cause (row 10); the work failing, a repair's (row 12).
    w = await _increment_failed_by_the_environment(calibrating, stored, environment=kind == "retry")
    *_, successor = await w.campaigns.launch_intents(CID)
    assert successor.cycle_kind is CycleKind(kind)
    stored["art_eval"] = (
        _dc.replace(
            _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 30),
            cycle_id="cyc_next",
        ),
        _evaluation("accepted"),
    )

    async def by_cycle(self, *, cycle_id=None, run_id=None, **_):
        return [
            ref
            for ref, _content in _STORED.values()
            if cycle_id in (None, ref.cycle_id) and run_id in (None, ref.run_id)
        ]

    monkeypatch.setattr(_Vault, "list_artifacts", by_cycle)
    run = await w.launched_cycle(
        kind,
        "cyc_next",
        "implementation",
        "completed",
        overrides=successor.cycle_request["body"]["execution_overrides"],
    )
    w._assess = lambda cycle_id: _async(_assessment(cycle_id, RunVerdict.ACCEPTED))
    w.progress._assess = w._assess

    await w.end("cyc_next", run, CycleStopReason.SEQUENCE_COMPLETED)

    [promote] = [
        e
        for e in await w.campaigns.control_log(CID)
        if e.operation is ControlOperation.PROMOTE and e.target == "cyc_next"
    ]
    [frozen] = promote.binding["frozen_criteria"]
    assert (frozen["criterion_id"], frozen.get("statement"), frozen.get("surface")) == (
        "C1",
        "A run created with capacity 2 is returned with capacity 2",
        "POST /runs",
    )


@pytest.mark.parametrize(
    ("target", "row", "state"),
    [(1, 3, CampaignState.COMPLETED), (2, 7, CampaignState.AT_PROPOSAL)],
    ids=["the-target-reached", "one-short-of-it"],
)
async def test_an_accepted_increment_that_meets_the_target_ends_the_campaign_in_success(
    calibrating, stored, target, row, state
):
    """§10 row 3, §24ah: shakeout 4 accepted its second increment and ended ``exhausted`` on
    row 4, because the measurement had no reader; a campaign set with a target of three would
    propose a fourth, fifth and sixth increment until its cycles ran out. Entered at
    ``CycleCompletion.end``. Bugs caught: the target never read; or the calibration's
    promotion counted as an increment, stopping the campaign one increment early."""
    from squadops.campaigns.models import CampaignObjective

    objective = CampaignObjective(
        statement="evolve group_run",
        allowed_scope=("backend", "frontend"),
        measurement=f"{target} accepted increment(s)",
        target_accepted_increments=target,
        work_class=None,
    )
    w, run = await calibrating(RunVerdict.ACCEPTED, objective=objective)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    stored["art_eval"] = (
        _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 20),
        _evaluation("accepted"),
    )
    increment_run = await w.launched_cycle("increment", "cyc_inc", "implementation", "completed")

    await w.end("cyc_inc", increment_run, CycleStopReason.SEQUENCE_COMPLETED)

    final = await w.campaigns.get_campaign(CID)
    decision = (await w.campaigns.control_log(CID))[-1]
    assert (decision.binding["row"], final.state) == (row, state)
    if row == 3:
        assert (final.outcome, decision.binding["cause"]) == (
            CampaignOutcome.SUCCESS,
            "objective_met",
        )


def test_the_accepted_increments_count_each_increment_family_cycle_once():
    """The edges: a replayed promotion row counted twice, a refused one counted, or the
    calibration's counted as an increment."""
    from types import SimpleNamespace

    from squadops.campaigns.models import ControlOutcome
    from squadops.campaigns.progress import accepted_increments

    def promote(cycle_id, outcome=ControlOutcome.APPLIED):
        return SimpleNamespace(
            operation=ControlOperation.PROMOTE, outcome=outcome, binding={"cycle_id": cycle_id}
        )

    intents = [
        SimpleNamespace(cycle_id="cyc_cal", cycle_kind=CycleKind.CALIBRATION),
        SimpleNamespace(cycle_id="cyc_inc", cycle_kind=CycleKind.INCREMENT),
        SimpleNamespace(cycle_id="cyc_rep", cycle_kind=CycleKind.REPAIR),
        SimpleNamespace(cycle_id=None, cycle_kind=CycleKind.INCREMENT),
    ]
    log = [
        promote("cyc_cal"),
        promote("cyc_rep"),
        promote("cyc_rep"),
        promote("cyc_inc", ControlOutcome.REFUSED),
        promote("cyc_unknown"),
    ]

    assert accepted_increments(log, intents) == 1


_PROPOSED = {
    "behaviour": "Two runs with the same date keep the order they were created in",
    "why": "The list reorders between refreshes when dates tie",
    "surface_kind": "endpoint",
    "surface": "GET /runs",
}


@pytest.mark.parametrize("proposed", [True, False])
async def test_the_next_proposal_is_shown_what_the_qa_author_proposed_instead_of_testing(
    calibrating, stored, proposed
):
    """#1884, entered at the completion hook that launches the next proposal. Bugs caught: the
    outlet's entries stored and never read, so "returned as a proposal" reaches no proposer; or
    a key launched with nothing in it."""
    import yaml

    from squadops.campaigns.proposed_behaviours import parse_proposed_behaviours, stored_form

    if proposed:
        content = stored_form(
            parse_proposed_behaviours(yaml.safe_dump({"proposed_behaviours": [_PROPOSED]}))
        )
        stored["art_pb"] = (
            _ref("art_pb", "proposed_behaviours.yaml", "qa_proposed_behaviours", 5),
            content.encode(),
        )
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)

    *_, proposal = await w.campaigns.launch_intents(CID)
    block = proposal.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert block.get("qa_proposed_behaviours") == ([_PROPOSED] if proposed else None)


async def test_a_proposal_launch_whose_outlet_read_fails_launches_nothing(
    calibrating, stored, monkeypatch, caplog
):
    """#1943's rule, for the launch the outlet feeds: a vault read that fails raises, the
    completion hook records the attempt as failed (``campaign_progress_failed``), and no launch is
    written, so the re-hearing retries it. Bug caught: a degraded launch without the entries,
    whose replay after a restart would launch a different request."""
    stored["art_pb"] = (
        _ref("art_pb", "proposed_behaviours.yaml", "qa_proposed_behaviours", 5),
        b"proposed_behaviours: []",
    )
    real = _Vault.retrieve

    async def failing(self, artifact_id):
        if artifact_id == "art_pb":
            raise OSError("vault unreadable")
        return await real(self, artifact_id)

    monkeypatch.setattr(_Vault, "retrieve", failing)
    w, run = await calibrating(RunVerdict.ACCEPTED)

    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)

    assert "campaign_progress_failed" in caplog.text
    assert [
        i for i in await w.campaigns.launch_intents(CID) if i.cycle_kind is CycleKind.INCREMENT
    ] == []


async def test_a_retry_is_told_what_each_correction_round_of_the_failed_cycle_tried(
    calibrating, stored
):
    """#1692's remainder, entered where the campaign launches the retry: the failed cycle's
    correction chain reaches the retry's brief round by round, from its run's stored loop
    summary. Bug caught: the successor told the round counts and not their content, so it
    repeats a repair that was already refused."""
    from squadops.cycles.failure_attribution import TerminalKind
    from squadops.cycles.llm_usage import RunUsage
    from squadops.cycles.run_loop_summary import (
        MovementRecord,
        RoundFailure,
        RunLoopSummary,
        RunTerminalDecision,
    )

    loop = RunLoopSummary(
        run_id="run_inc",
        usage=RunUsage(by_task_type={}, tasks_reported=0, tasks_unreported=()),
        round_failures=(
            RoundFailure(
                "task-run_0123456789ab-m007-qa.test",
                0,
                "executed_and_failed",
                "subject",
                failed_checks=("tests_pass",),
            ),
        ),
        movements=(MovementRecord("task-run_0123456789ab-m007-qa.test", 0, "repeat"),),
        revision_forms=(
            {
                "task_id": "repair-run_0123456789ab-00-s00-development.correction_repair",
                "task_type": "development.correction_repair",
                "accepted": False,
                "edited": ["backend/routes.py"],
                "failure_reason": "the patch's retest added a failure",
            },
        ),
        terminal=RunTerminalDecision(
            kind=TerminalKind.CORRECTION_TERMINATED, termination_reason="exhausted"
        ),
    )

    w = await _increment_failed_by_the_environment(calibrating, stored, loop_summary=loop)

    *_, retry = await w.campaigns.launch_intents(CID)
    prior = retry.cycle_request["body"]["execution_overrides"]["campaign_proposal"]["prior_cycle"]
    assert prior["correction_rounds"] == [
        {
            "round": 0,
            "task_type": "qa.test",
            "failed_checks": ["tests_pass"],
            "category": "executed_and_failed",
            "repairs": [
                {
                    "task_type": "development.correction_repair",
                    "kept": False,
                    "edited": ["backend/routes.py"],
                    "refused_because": "the patch's retest added a failure",
                }
            ],
            "movement": "repeat",
        }
    ]
    assert prior["correction_ended"] == "exhausted"


@pytest.mark.parametrize(
    ("plan_gate", "same_question", "carried"),
    [
        ("tier", True, True),
        ("tier", False, False),
        ("supervised", True, False),
    ],
    ids=["a tier campaign, the same question", "another question, one id", "a supervised campaign"],
)
async def test_a_late_answer_reaches_a_tier_increment_only_for_the_same_question(
    calibrating, monkeypatch, plan_gate, same_question, carried
):
    """SIP-0109 §24bm, entered at ``CycleCompletion.end`` on shakeout 4's calibration manifest.
    Bugs caught: a late answer that never reaches the plan the gate reads, so the tier can only
    clear it by id; one carried into a different question that shares the id; one carried into a
    supervised campaign, which keeps today's behaviour."""
    from squadops.campaigns.models import PlanGate
    from squadops.cycles.manifest_authoring import (
        LATE_ANSWER_WARRANT,
        cited_late_answers,
        open_decisions,
    )

    [(_, question)] = open_decisions(_OPEN_MANIFEST)
    asked = question if same_question else "Does the runs list page?"

    proposal = await _answered_calibration(
        calibrating,
        monkeypatch,
        decided_by="agent:005159fd",
        notes=None,
        late_answer=(asked, "newest first"),
        plan_gate=PlanGate(plan_gate),
    )

    baseline = proposal["baseline_manifest"]
    if carried:
        [(choice, escalation_id)] = cited_late_answers(baseline).values()
        assert choice == "newest first" and escalation_id.startswith("esc_")
        assert open_decisions(baseline) == ()
        assert LATE_ANSWER_WARRANT in baseline
    else:
        assert baseline == _OPEN_MANIFEST


@pytest.mark.parametrize(
    ("profile", "answered", "expected"),
    [
        ("campaign-increment-asks", False, "asks"),
        ("campaign-increment-asks", True, "carried"),
        ("campaign-increment", True, "unchanged"),
    ],
    ids=["a diagnostic, no answer yet", "a diagnostic, answered late", "an ordinary campaign"],
)
async def test_a_diagnostic_increment_launches_on_a_baseline_that_asks_and_carries_a_late_answer(
    calibrating, monkeypatch, profile, answered, expected
):
    """#2279, #2290: the timeout half's late answer, readable live. Entered at
    ``CycleCompletion.end``, which launches the increment, on shakeout 4's calibration manifest
    with its own question answered at its gate (§24ad). A tier campaign whose proposal profile
    declares ``increment_design_asks`` launches on a baseline that asks the injected question, and
    a late answer recorded against it is carried in (§24bm), so the plan the gate reads cites it.
    Bugs caught: the fault applied after the carry, or overwriting the answer, so increment 2 asks
    again and parks; an ordinary campaign's baseline changed."""
    from squadops.campaigns.models import PlanGate
    from squadops.capabilities.handlers.fault_injection import (
        INJECTED_QUESTION,
        INJECTED_QUESTION_ID,
    )
    from squadops.cycles.manifest_authoring import cited_late_answers, open_decisions

    proposal = await _answered_calibration(
        calibrating,
        monkeypatch,
        decided_by="agent:005159fd",
        notes=_ANSWER,
        late_answer=(INJECTED_QUESTION, "no; one page", INJECTED_QUESTION_ID) if answered else None,
        plan_gate=PlanGate.TIER,
        proposal_profile=profile,
    )
    baseline = proposal["baseline_manifest"]

    seen = {
        "asks": open_decisions(baseline) == ((INJECTED_QUESTION_ID, INJECTED_QUESTION),),
        "carried": open_decisions(baseline) == ()
        and [c for c, _esc in cited_late_answers(baseline).values()] == ["no; one page"],
        "unchanged": INJECTED_QUESTION_ID not in baseline and open_decisions(baseline) == (),
    }
    assert [k for k, held in seen.items() if held] == [expected]


def _rejection(*discriminations: tuple[str, str], **parts) -> bytes:
    """An increment evaluation that rejected, each new criterion ``(id, reason)``."""
    return json.dumps(
        {
            "verdict": "rejected",
            "unmet": [f"criterion {c}: {reason}" for c, reason in discriminations],
            "blocked": [],
            "discriminations": [
                {"criterion_id": c, "met": False, "reason": reason, "discriminating": []}
                for c, reason in discriminations
            ],
            "frozen": [],
            "routes": [{"path": "/", "held": "held", "missing": [], "not_shown": []}],
            "new_bundles": {},
            **parts,
        }
    ).encode()


@pytest.mark.parametrize(
    ("evaluation", "expected"),
    [
        (_rejection(("C1", "no_baseline_failure")), (16, "abandon_and_propose")),
        (
            _rejection(("C1", "no_baseline_failure"), ("C2", "fails_on_candidate")),
            (12, "repair"),
        ),
    ],
    ids=["only-already-met", "one-fails-on-the-candidate"],
)
async def test_an_increment_rejected_only_for_criteria_already_met_goes_to_a_new_proposal_told_which(
    calibrating, stored, evaluation, expected
):
    """#2315 (§24bq, row 16), entered at the completion hook on the live shape (the request on the
    approved proposal run, as #1938's test stores it). Bugs caught: a repair spent on criteria the
    accepted application already meets, which no rebuild can make fail on the baseline; or the new
    proposal not told which, so it proposes them again. A criterion that fails on the candidate is
    the build's to fix, and a repair still follows."""
    from squadops.campaigns.change_request import (
        ProposalContext,
        stored_change_request,
        validate_proposal,
    )

    fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
    request = validate_proposal(
        yaml.safe_load((fixtures / "reference-capacity-change-request.yaml").read_text()),
        ProposalContext(
            "prop_cap",
            1,
            "sha-accepted",
            (fixtures / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text(),
            "fullstack_fastapi_react",
            ("backend/**", "frontend/**"),
            (),
        ),
    ).change_request
    stored["art_candidate"] = (
        _ref("art_candidate", "interface_manifest.yaml", "interface_manifest", -2),
        MANIFEST.encode(),
    )
    stored["art_cr"] = (
        _ref("art_cr", "change_request.yaml", "change_request", -1),
        stored_change_request(request).encode(),
    )
    stored["art_eval"] = (
        _ref("art_eval", "increment_evaluation.json", "increment_evaluation", 20),
        evaluation,
    )
    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    block = {
        "proposal_id": "prop_cap",
        "version": 1,
        "baseline_tree": (await w.campaigns.get_campaign(CID)).accepted.identity,
        "accepted_cycle_id": "cyc_cal",
        "baseline_manifest": MANIFEST,
    }
    increment_run = await w.launched_cycle(
        "increment",
        "cyc_inc",
        "implementation",
        "completed",
        overrides={"campaign_proposal": block},
    )
    await w.cycles.create_run(
        Run(
            run_id="run_prop",
            cycle_id="cyc_inc",
            run_number=0,
            status="completed",
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type="proposal",
        )
    )
    await w.end("cyc_inc", increment_run, CycleStopReason.SEQUENCE_COMPLETED)

    decision = (await w.campaigns.control_log(CID))[-1]
    assert (decision.binding["row"], decision.binding["action"]) == expected
    if expected[0] == 16:
        *_, launched = await w.campaigns.launch_intents(CID)
        block = launched.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
        assert launched.cycle_kind is CycleKind.INCREMENT
        assert block["abandoned_increment"]["already_met"] == [
            {
                "criterion_id": "C1",
                "statement": "A run created with capacity 2 is returned with capacity 2",
                "surface": "POST /runs",
            }
        ]


@pytest.mark.parametrize(
    ("evaluation", "only"),
    [
        (None, False),
        (json.loads(_rejection(("C1", "no_baseline_failure"))), True),
        (
            json.loads(
                _rejection(("C1", "no_baseline_failure"), blocked=["route /: not rendered"])
            ),
            False,
        ),
        (
            json.loads(
                _rejection(
                    ("C1", "no_baseline_failure"),
                    frozen=[{"criterion_id": "T1", "held": "broken", "detail": "it failed"}],
                )
            ),
            False,
        ),
        (
            json.loads(
                _rejection(
                    ("C1", "no_baseline_failure"),
                    routes=[{"path": "/", "held": "broken", "missing": ["x"], "not_shown": []}],
                )
            ),
            False,
        ),
        (json.loads(_rejection(("C1", "no_baseline_failure"), verdict="accepted")), False),
    ],
    ids=["none", "only-already-met", "blocked", "frozen-broken", "route-missing", "accepted"],
)
def test_a_rejection_is_already_met_only_when_nothing_else_stands_in_it(evaluation, only):
    """#2315: row 16 skips the repair, so it must hold only when no repair could help. Bug caught:
    an increment whose frozen criterion broke, or whose route is missing, abandoned unrepaired
    because one of its new criteria was also met already."""
    from squadops.campaigns.progress import rejected_only_as_already_met

    assert rejected_only_as_already_met(evaluation) is only


# --------------------------------------------------------------------------------------------
# SIP-0113 §4.1 (#2414): each ending that reached its build evaluated against the pinned suite
# --------------------------------------------------------------------------------------------


class _ScenarioRunner:
    """Runs every scenario to ``passed``, noting the tree and which cycles were decided then."""

    def __init__(self, world_of):
        self._world_of = world_of
        self.calls: list[tuple[str, list]] = []

    async def evaluate_tree(self, **kw):
        from squadops.scenarios.runner import TreeEvaluation
        from squadops.scenarios.steps import ScenarioRun

        log = await self._world_of().campaigns.control_log(CID)
        decided = [e.target for e in log if e.operation is ControlOperation.DECIDE]
        self.calls.append((kw["tree_identity"], decided))
        runs = tuple(
            ScenarioRun(s["scenario_id"], "passed", steps_taken=1) for s in kw["scenarios"]
        )
        return TreeEvaluation(kw["tree_identity"], started=True, runs=runs)


async def _pinned_store():
    from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
    from squadops.scenarios.models import CampaignSuitePin, parse_suite
    from squadops.scenarios.suites import approve_suite, draft_suite

    suite = parse_suite(
        {
            "name": "group_run",
            "scenarios": [
                {
                    "scenario_id": "runs-list",
                    "goal": "The runs are listed.",
                    "surfaces": [{"kind": "http_endpoint", "method": "GET", "path": "/runs"}],
                    "steps": [{"action": "http", "method": "GET", "path": "/runs"}],
                    "checks": [{"check": "status", "step": 1, "equals": 200}],
                }
            ],
        }
    )
    store = MemoryScenarioStore()
    await draft_suite(store, suite, actor="supervisor", at=NOW)
    await approve_suite(store, suite.digest, actor="owner", at=NOW)
    await store.save_pin(CampaignSuitePin(CID, suite.digest, pinned_by="owner", pinned_at=NOW))
    return store


async def test_each_built_ending_is_evaluated_before_its_decision_against_the_tree_it_built_on(
    calibrating, stored
):
    """#2414's wiring, entered at the completion hook with the real evaluator and a pinned suite.
    Bugs caught: no evaluation at a cycle's end, so the window has no records; one run after the
    decision, beside the next cycle on the box; an increment's record naming no previous tree, so
    its contribution can't be read; or a re-heard cycle evaluated twice."""
    from squadops.scenarios.campaign_cycles import CampaignCycleEvaluator

    store, worlds = await _pinned_store(), []
    runner = _ScenarioRunner(lambda: worlds[0])

    def evaluator(world):
        worlds.append(world)
        return CampaignCycleEvaluator(
            store=store, runner=runner, vault=_Vault(), campaigns=world.campaigns,
            clock=lambda: NOW, projects=None, repository=None,
        )  # fmt: skip

    stack = {"build_profile": "fullstack_fastapi_react"}
    w, run = await calibrating(RunVerdict.ACCEPTED, evaluator=evaluator, overrides=stack)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    increment_run = await w.launched_cycle(
        "increment",
        "cyc_inc",
        "implementation",
        "completed",
        {**stack, "campaign_proposal": {"accepted_cycle_id": "cyc_cal"}},
    )
    await w.end("cyc_inc", increment_run, CycleStopReason.SEQUENCE_COMPLETED)
    await _resume(w, ["cyc_cal", "cyc_inc"])

    log = await w.campaigns.control_log(CID)
    promoted = {
        e.target: e.binding["identity"] for e in log if e.operation is ControlOperation.PROMOTE
    }
    [cal] = await store.evaluations_for_cycle("cyc_cal")
    [inc] = await store.evaluations_for_cycle("cyc_inc")
    assert (cal.campaign_id, cal.previous_accepted_tree_identity) == (CID, None)
    assert cal.evaluated_tree_identity == promoted["cyc_cal"]
    assert inc.previous_accepted_tree_identity == promoted["cyc_cal"]
    assert [decided for _, decided in runner.calls] == [[], ["cyc_cal"]]
