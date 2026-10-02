"""A campaign hears its cycle end (SIP-0109 §10, §11, §12a; #1800, #1709).

Entered at ``CycleCompletion.end`` — the completion boundary every cycle passes — on the real
executor, over the memory campaign and cycle registries. The vault holds what a run stores; the
assessment is the real projection over crafted evidence, so the decision reads the verdict as the
live path hands it over.
"""

from __future__ import annotations

import json
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

    async def launched_cycle(
        self, kind: str, cycle_id: str, workload: str, status: str, overrides: dict | None = None
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
                task_flow_policy=TaskFlowPolicy(mode="sequential"),
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


@pytest.fixture
def stored(monkeypatch):
    """A vault per test that can also store (the promotion writes bundles)."""
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


def test_a_retired_criterion_leaves_the_frozen_set_and_a_later_one_takes_its_place():
    """§8.1. Bug caught: a criterion an increment retired still pinned for every later launch —
    run on every candidate and blocking the very change that ruled it out."""
    from squadops.campaigns.models import ControlLogEntry, ControlOutcome
    from squadops.campaigns.progress import frozen_criteria

    def promote(seq, frozen, retired=()):
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
                "frozen_criteria": [{"criterion_id": c, "bundle_ref": f"art_{c}"} for c in frozen],
                "retired_criteria": list(retired),
            },
            outcome=ControlOutcome.APPLIED,
            refusal=None,
            prior_state=CampaignState.PROMOTING,
            next_state=CampaignState.AT_PROPOSAL,
            committed_at=NOW,
        )

    log = [promote(1, ["C1", "C2"]), promote(2, ["C3"], retired=["C1"])]

    assert [f["criterion_id"] for f in frozen_criteria(log)] == ["C2", "C3"]


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
    calibrating, stored, *, ruled="approved", moved=False, environment=True
):
    """An accepted calibration, an increment proposed against its tree and ruled on, built, and
    rejected for a cause outside the work. Its approved seeds are stored, as the gate stores
    them; created before the calibration's manifest, so the calibration's stays the latest."""
    stored["art_candidate"] = (
        _ref("art_candidate", "interface_manifest.yaml", "interface_manifest", -2),
        MANIFEST.encode(),
    )
    stored["art_cr"] = (_ref("art_cr", "change_request.yaml", "change_request", -1), b"cr")
    from squadops.campaigns.gate import ruling_transition, submission
    from squadops.campaigns.models import ProposalBinding, SubmittedProposal
    from squadops.cycles.models import GateDecisionValue

    w, run = await calibrating(RunVerdict.ACCEPTED)
    await w.end("cyc_cal", run, CycleStopReason.SEQUENCE_COMPLETED)
    accepted = (await w.campaigns.get_campaign(CID)).accepted.identity
    block = {
        "proposal_id": "prop_cap",
        "version": 1,
        "baseline_tree": "an-older-tree" if moved else accepted,
        "accepted_cycle_id": "cyc_cal",
        "baseline_manifest": MANIFEST,
    }
    increment_run = await w.launched_cycle(
        "increment",
        "cyc_inc",
        "implementation",
        "completed",
        overrides={
            "campaign_proposal": block,
            "plan_artifact_refs": ["art_candidate", "art_cr"],
            "contract_ref": "art_contract",
        },
    )
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
        ),
    )
    w._assess = lambda cycle_id: _async(
        _environment_failure(cycle_id)
        if environment
        else _assessment(cycle_id, RunVerdict.REJECTED)
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
    one built from a stale baseline, or one that runs the proposal workload again."""
    w = await _increment_failed_by_the_environment(calibrating, stored)

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
    assert overrides["plan_artifact_refs"] == ["art_candidate", "art_cr", "art_plan"]
    assert [w["type"] for w in overrides["workload_sequence"]] == ["implementation"]


async def test_a_repair_with_no_approved_plan_escalates(calibrating, stored):
    w = await _increment_failed_by_the_environment(calibrating, stored, environment=False)

    decision = (await w.campaigns.control_log(CID))[-1]
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.ESCALATED
    assert "no approved implementation plan" in decision.binding["unbuilt"]
