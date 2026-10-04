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
            i for i in await self.campaigns.pending_launch_intents() if i.cycle_kind.value == kind
        ]
        await self.campaigns.mark_launch_intent_launched(intent.launch_id, cycle_id, actor="l")
        return run

    async def end(self, cycle_id: str, run: Run, stopped: CycleStopReason):
        await self.executor._cycle_completion.end(cycle_id, run, stopped)


@pytest.fixture
async def calibrating() -> _World:
    async def make(verdict, objective=None, **policy_overrides):
        w = _World(verdict)
        draft = campaign(
            CID,
            policy=policy(
                calibration_profile="framing",
                proposal_profile="campaign-increment",
                **policy_overrides,
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
    calibrating, stored, *, ruled="approved", moved=False, environment=True, reasons=(), **policy
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

    w, run = await calibrating(RunVerdict.ACCEPTED, **policy)
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
    assert overrides["campaign_proposal"]["prior_cycle"]["cycle_id"] == "cyc_inc"
    assert overrides["plan_artifact_refs"] == ["art_candidate", "art_cr", "art_plan"]
    assert [w["type"] for w in overrides["workload_sequence"]] == ["implementation"]


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


async def _answered_calibration(calibrating, monkeypatch, *, decided_by: str, notes: str | None):
    from squadops.cycles.models import GateDecision

    monkeypatch.setitem(
        _STORED,
        "art_manifest",
        (
            _ref("art_manifest", "interface_manifest.yaml", "interface_manifest", 0),
            _OPEN_MANIFEST.encode(),
        ),
    )
    w, run = await calibrating(RunVerdict.ACCEPTED)
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
