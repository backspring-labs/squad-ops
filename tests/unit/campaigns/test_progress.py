"""A campaign hears its cycle end (SIP-0109 §10, §11, §12a; #1800, #1709).

Entered at ``CycleCompletion.end`` — the completion boundary every cycle passes — on the real
executor, over the memory campaign and cycle registries. The vault holds what a run stores; the
assessment is the real projection over crafted evidence, so the decision reads the verdict as the
live path hands it over.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.continuation import CycleEnding
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import (
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    CycleKind,
    LaunchIntentState,
)
from squadops.campaigns.progress import CampaignProgress, CycleRecord, cycle_ending, derive_counters
from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord, assess
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.models import ArtifactRef, Cycle, Run, TaskFlowPolicy
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


class _Vault:
    async def list_artifacts(self, *, cycle_id=None, run_id=None, **_):
        return [ref for ref, _ in _STORED.values()]

    async def retrieve(self, artifact_id):
        return _STORED[artifact_id]


class _World:
    def __init__(self, verdict: RunVerdict | None) -> None:
        from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

        self.campaigns = MemoryCampaignRegistry()
        self.cycles = MemoryCycleRegistry()
        self.launches = AsyncMock()
        self.verdict = verdict
        self.now = NOW + timedelta(hours=1)
        self.progress = CampaignProgress(
            campaigns=self.campaigns,
            cycles=self.cycles,
            vault=_Vault(),
            assess=self._assess,
            launch=self.launches,
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
        )
        self.executor._cycle_event_bus = MagicMock()

    async def _assess(self, cycle_id):
        return _assessment(cycle_id, self.verdict)

    async def launched_cycle(self, kind: str, cycle_id: str, workload: str, status: str) -> Run:
        await self.cycles.create_cycle(
            Cycle(
                cycle_id=cycle_id,
                project_id="group_run",
                created_at=NOW,
                created_by="campaign-launcher",
                prd_ref=None,
                squad_profile_id="full-38",
                squad_profile_snapshot_ref="sha256:abc",
                task_flow_policy=TaskFlowPolicy(mode="sequential"),
                build_strategy="fresh",
                campaign_id=CID,
                kind=kind,
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
            i for i in await self.campaigns.pending_launch_intents() if i.cycle_kind.value == kind
        ]
        await self.campaigns.mark_launch_intent_launched(intent.launch_id, cycle_id, actor="l")
        return run

    async def end(self, cycle_id: str, run: Run, stopped: CycleStopReason):
        await self.executor._cycle_completion.end(cycle_id, run, stopped)


@pytest.fixture
async def calibrating() -> _World:
    async def make(verdict):
        w = _World(verdict)
        draft = campaign(
            CID, policy=policy(calibration_profile="framing", proposal_profile="campaign-increment")
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
        return w, await w.launched_cycle("calibration", "cyc_cal", "implementation", "completed")

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
    ("workload", "status", "stopped", "ending"),
    [
        ("proposal", "completed", CycleStopReason.GATE_REJECTED, CycleEnding.REJECTED_AT_GATE),
        # §9.5: a proposal whose revisions are spent counts as rejected.
        (
            "proposal",
            "completed",
            CycleStopReason.REVISION_UNAVAILABLE,
            CycleEnding.REJECTED_AT_GATE,
        ),
        ("proposal", "failed", CycleStopReason.RUN_FAILED, CycleEnding.PROPOSAL_FAILED),
        ("implementation", "failed", CycleStopReason.RUN_FAILED, CycleEnding.ASSESSED),
        ("framing", "completed", CycleStopReason.GATE_REJECTED, CycleEnding.ASSESSED),
    ],
)
def test_the_ending_is_read_from_where_the_cycle_stopped(workload, status, stopped, ending):
    run = Run("r", "c", 1, status, "system", "cfg", workload_type=workload)
    assert cycle_ending(stopped, run) is ending


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
