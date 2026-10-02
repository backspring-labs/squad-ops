"""The increment gate as the cycle reaches it (SIP-0109 §9.2; #1801).

Entered at ``WorkloadGate.decide``, the seam ``execute_cycle`` calls between the proposal workload
and framing, on the real executor with a memory campaign registry. What reaches the campaign is
asserted, and what the gate does next.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.campaigns.gate import INCREMENT_RULING_GATE
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    ProposalBinding,
)
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    GateDecision,
    GateDecisionValue,
    Run,
    TaskFlowPolicy,
)
from tests.unit.campaigns.builders import campaign, move

NOW = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)
CID = "cmp_wire00000001"
_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
_BASELINE = (_FIXTURES / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text()


def _stored_change_request():
    """The reference capacity proposal, through the proposal's own rails, stored as the
    proposal run stores it (``StrategyProposeIncrementHandler._success``)."""
    from squadops.campaigns.change_request import (
        ProposalContext,
        stored_change_request,
        validate_proposal,
    )

    verdict = validate_proposal(
        yaml.safe_load((_FIXTURES / "reference-capacity-change-request.yaml").read_text()),
        ProposalContext(
            proposal_id="prop_cap",
            version=1,
            baseline_tree="sha-accepted",
            baseline_manifest=_BASELINE,
            expected_stack="fullstack_fastapi_react",
            allowed_scope=("backend/**", "frontend/**"),
            prior_criteria=(),
        ),
    )
    assert verdict.accepted, verdict.refusals
    request = verdict.change_request
    return request, stored_change_request(request)


_REQUEST, _CHANGE_REQUEST = _stored_change_request()
#: An interface manifest that declares no open question: #807 would pass its gate through.
_QUESTION_FREE_MANIFEST = "version: 1\nentities: []\nendpoints: []\nopen_questions: []\n"


def _ref(artifact_id: str, artifact_type: str, filename: str, content: str) -> tuple:
    return ArtifactRef(
        artifact_id=artifact_id,
        project_id="group_run",
        artifact_type=artifact_type,
        filename=filename,
        content_hash="h",
        size_bytes=len(content),
        media_type="text/yaml",
        created_at=NOW,
        cycle_id="cyc_inc",
        run_id="run_prop",
    ), content.encode()


def _cycle(campaign_id: str | None) -> Cycle:
    return Cycle(
        cycle_id="cyc_inc",
        project_id="group_run",
        created_at=NOW,
        created_by="launcher",
        prd_ref=None,
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        execution_overrides={
            "plan_artifact_refs": ["art_manifest"],
            "campaign_proposal": {
                "proposal_id": "prop_cap",
                "version": 1,
                "max_revisions": 1,
                "baseline_manifest": _BASELINE,
            },
        },
        campaign_id=campaign_id,
        kind="increment" if campaign_id else None,
    )


_PROPOSAL_RUN = Run(
    run_id="run_prop",
    cycle_id="cyc_inc",
    run_number=1,
    status="completed",
    initiated_by="system",
    resolved_config_hash="cfg",
    workload_type="proposal",
    artifact_refs=("art_cr",),
)


@pytest.fixture
async def campaigns() -> MemoryCampaignRegistry:
    reg = MemoryCampaignRegistry()
    await reg.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create"
    )
    await reg.transition(CID, move(CampaignState.CALIBRATING, "cal"))
    await reg.transition(
        CID,
        move(
            CampaignState.CALIBRATING,
            "promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree("sha-accepted", "cyc_cal"),
        ),
    )
    await reg.transition(CID, move(CampaignState.AT_PROPOSAL, "propose"))
    return reg


class _Vault:
    """What the gate reads and stores: the proposal run's artifacts, promotion included."""

    def __init__(self, *stored) -> None:
        self.stored = {ref.artifact_id: (ref, content) for ref, content in stored}

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def list_artifacts(self, *, run_id=None, promotion_status=None, **_):
        return [
            ref
            for ref, _ in self.stored.values()
            if (run_id is None or ref.run_id == run_id)
            and (promotion_status is None or ref.promotion_status == promotion_status)
        ]

    async def promote_artifact(self, artifact_id):
        ref, content = self.stored[artifact_id]
        self.stored[artifact_id] = (dataclasses.replace(ref, promotion_status="promoted"), content)


@pytest.fixture
def executor(campaigns):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    vault = _Vault(
        _ref("art_cr", "change_request", "change_request.yaml", _CHANGE_REQUEST),
        _ref("art_manifest", "document", "interface_manifest.yaml", _QUESTION_FREE_MANIFEST),
    )
    exec_ = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        campaign_registry=campaigns,
    )
    exec_._cycle_event_bus = MagicMock()
    exec_._approve_gate_without_questions = AsyncMock()
    exec_._poll_inter_workload_gate = AsyncMock(
        return_value=GateDecision(
            gate_name=INCREMENT_RULING_GATE,
            decision=GateDecisionValue.APPROVED.value,
            decided_by="human:crew-supervisor",
            decided_at=NOW,
        )
    )
    return exec_


async def _reach_the_gate(executor, cycle: Cycle):
    return await executor._workload_gate.decide(
        cycle=cycle,
        cycle_id=cycle.cycle_id,
        run=_PROPOSAL_RUN,
        workload_entry={"type": "proposal", "gate": INCREMENT_RULING_GATE},
        gate_name=INCREMENT_RULING_GATE,
        current_run_id=_PROPOSAL_RUN.run_id,
        forwarding_overrides=None,
        framing_rerolls=0,
        framing_revisions=0,
        max_framing_rerolls=0,
        max_framing_revisions=0,
    )


async def test_the_gate_submits_the_proposal_and_waits_for_the_ruling(executor, campaigns):
    """§19 criterion 5's front half. Bugs caught: the increment gate passed through because its
    baseline manifest asks no question (#807) — an increment built with nobody ruling — or the
    proposal never reaching the campaign, so no ruling could ever bind."""
    await _reach_the_gate(executor, _cycle(CID))

    stored = await campaigns.get_campaign(CID)
    executor._approve_gate_without_questions.assert_not_awaited()
    executor._poll_inter_workload_gate.assert_awaited_once()
    assert executor._poll_inter_workload_gate.await_args.args[2] == INCREMENT_RULING_GATE
    assert stored.state is CampaignState.AWAITING_RULING
    assert stored.proposal.binding == ProposalBinding(
        "prop_cap", 1, _REQUEST.content_hash, "sha-accepted"
    )
    assert (stored.proposal.cycle_id, stored.proposal.run_id) == ("cyc_inc", "run_prop")


async def test_re_entering_the_gate_after_a_restart_replays_the_submission(executor, campaigns):
    await _reach_the_gate(executor, _cycle(CID))
    await _reach_the_gate(executor, _cycle(CID))

    submits = [e for e in await campaigns.control_log(CID) if e.operation == "submit"]
    assert len(submits) == 1


async def test_a_cycle_without_a_campaign_cannot_reach_the_increment_gate(executor):
    with pytest.raises(ValueError, match="without a campaign"):
        await _reach_the_gate(executor, _cycle(None))


async def test_a_proposal_run_without_its_change_request_fails_at_the_gate(executor):
    """Bug caught: a gate opened on nothing, which the supervisor could only rule on blind."""
    bare = dataclasses.replace(_PROPOSAL_RUN, artifact_refs=())
    with pytest.raises(ValueError, match="no change_request artifact"):
        await executor._workload_gate.decide(
            cycle=_cycle(CID),
            cycle_id="cyc_inc",
            run=bare,
            workload_entry={"type": "proposal", "gate": INCREMENT_RULING_GATE},
            gate_name=INCREMENT_RULING_GATE,
            current_run_id=bare.run_id,
            forwarding_overrides=None,
            framing_rerolls=0,
            framing_revisions=0,
            max_framing_rerolls=0,
            max_framing_revisions=0,
        )


def _returned(notes: str = "Keep it backend only.") -> GateDecision:
    return GateDecision(
        gate_name=INCREMENT_RULING_GATE,
        decision=GateDecisionValue.RETURNED_FOR_REVISION.value,
        decided_by="human:crew-supervisor",
        decided_at=NOW,
        notes=notes,
    )


@pytest.fixture
def revising(executor):
    """The supervisor returns the proposal; the registry holds the cycle's runs so far."""
    executor._poll_inter_workload_gate.return_value = _returned()
    executor._cycle_registry.list_runs.return_value = [_PROPOSAL_RUN]
    executor._create_next_workload_run = AsyncMock(
        return_value=dataclasses.replace(_PROPOSAL_RUN, run_id="run_prop2", run_number=2)
    )
    return executor


async def test_a_returned_proposal_is_revised_in_a_new_run_from_the_version_it_returned(revising):
    """§9.2: request revision → a new proposal run with the note; the supervisor never edits.
    Bugs caught: the sequence stopping (today's non-framing revision), the revision run given
    the original block (version 1 again, no note), or the returned run left occupying its place."""
    from adapters.cycles.workload_gate import GateOutcome

    step = await _reach_the_gate(revising, _cycle(CID))

    revised = step.forwarding_overrides["campaign_proposal"]
    assert step.outcome is GateOutcome.RE_EXECUTE
    assert step.current_run_id == "run_prop2"
    revising._cycle_registry.cancel_run.assert_awaited_once_with("run_prop")
    assert (revised["version"], revised["supervisor_note"]) == (2, "Keep it backend only.")
    assert revised["prior_change_request"] == _CHANGE_REQUEST
    assert revised["proposal_id"] == "prop_cap"


async def test_a_proposal_whose_revisions_are_spent_stops_and_counts_as_rejected(revising):
    """§9.5: the revisions of one proposal are bounded. The count is the cycle's superseded
    proposal runs, read from the registry, so a restart counts the same."""
    from adapters.cycles.workload_gate import GateOutcome
    from squadops.cycles.cycle_end import CycleStopReason

    superseded = dataclasses.replace(_PROPOSAL_RUN, run_id="run_prop0", status="cancelled")
    revising._cycle_registry.list_runs.return_value = [superseded, _PROPOSAL_RUN]

    step = await _reach_the_gate(revising, _cycle(CID))

    assert (step.outcome, step.stopped_because) == (
        GateOutcome.STOP,
        CycleStopReason.REVISION_UNAVAILABLE,
    )
    revising._cycle_registry.cancel_run.assert_not_awaited()
    revising._create_next_workload_run.assert_not_awaited()


async def test_a_revision_without_the_campaigns_budget_is_refused(revising):
    """Require, don't default: a block the launch did not give a budget is a defect."""
    cycle = _cycle(CID)
    cycle = dataclasses.replace(
        cycle, execution_overrides={**cycle.execution_overrides, "campaign_proposal": {}}
    )
    with pytest.raises(ValueError, match="no max_revisions"):
        await _reach_the_gate(revising, cycle)


async def test_an_approval_seeds_the_candidate_manifest_and_forwards_it_to_framing(executor):
    """SIP-0109 §7.3, #1705 step a. Bugs caught: the increment's framing authoring a fresh
    manifest from the PRD (greenfield) instead of binding to the accepted one with the approved
    delta applied, or the seed lost at the next advance because forwarding is rebuilt from
    durable state (#434)."""
    from squadops.campaigns.change_request import apply_manifest_delta
    from squadops.campaigns.gate import INCREMENT_SEED_PRODUCER

    await _reach_the_gate(executor, _cycle(CID))
    await _reach_the_gate(executor, _cycle(CID))  # a re-entry after a restart

    stored = executor._artifact_vault.stored
    seeds = [(r, c) for r, c in stored.values() if r.artifact_type == "interface_manifest"]
    contracts = [r for r, _ in stored.values() if r.artifact_type == "verification_contract"]
    [(seed, content)] = seeds
    [contract] = contracts
    assert content.decode() == apply_manifest_delta(_BASELINE, _REQUEST.manifest_delta)
    assert seed.metadata["producing_task_type"] == INCREMENT_SEED_PRODUCER
    assert (seed.promotion_status, contract.promotion_status) == ("promoted", "promoted")

    forwarded = await executor._build_forwarding_overrides(_cycle(CID), _PROPOSAL_RUN)

    assert seed.artifact_id in forwarded["plan_artifact_refs"]
    assert forwarded["contract_ref"] == contract.artifact_id


async def test_the_approved_change_request_reaches_the_increments_framing(executor):
    """§7.3, #1705 d: the approved change request is the framed objective. Entered at the gate,
    through the forwarding a restart rebuilds, to the loader the framing run's provisioning
    calls. Bug caught: the framing reaching provisioning without the document it frames, and
    framing the accepted application again from its PRD."""
    from squadops.campaigns.increment_tree import approved_change_request

    await _reach_the_gate(executor, _cycle(CID))
    forwarded = await executor._build_forwarding_overrides(_cycle(CID), _PROPOSAL_RUN)
    framing = _cycle(CID)
    framing = dataclasses.replace(
        framing, execution_overrides={**framing.execution_overrides, **forwarded}
    )

    assert await approved_change_request(executor._artifact_vault, framing) == _CHANGE_REQUEST


async def test_the_approved_seed_binds_every_workload_after_the_proposal(executor):
    """§7.3: the candidate manifest and its contract bind the increment's implementation as they
    bind its framing, as a creation-time seed binds every workload. Entered at the forwarding the
    workload loop builds after framing completes, and at a restart's rebuild of it (#434). Bug
    caught: forwarding rebuilt from the cycle and the framing run alone drops the proposal run's
    seed, so the implementation runs unscaffolded, in author mode, without the accepted tree."""
    await _reach_the_gate(executor, _cycle(CID))
    stored = executor._artifact_vault.stored
    [seed] = [r for r, _ in stored.values() if r.artifact_type == "interface_manifest"]
    [contract] = [r for r, _ in stored.values() if r.artifact_type == "verification_contract"]
    framing = Run(
        run_id="run_frame",
        cycle_id="cyc_inc",
        run_number=2,
        status="completed",
        initiated_by="system",
        resolved_config_hash="cfg",
        workload_type="framing",
    )
    executor._cycle_registry.list_runs.return_value = [_PROPOSAL_RUN, framing]

    forwarded = await executor._build_forwarding_overrides(_cycle(CID), framing)

    assert seed.artifact_id in forwarded["plan_artifact_refs"]
    assert forwarded["contract_ref"] == contract.artifact_id


async def test_an_increments_framing_without_its_change_request_is_refused(executor):
    """Bug caught: an increment framed as a new application because nothing was forwarded."""
    from squadops.campaigns.increment_tree import approved_change_request

    with pytest.raises(ValueError, match="no approved change_request"):
        await approved_change_request(executor._artifact_vault, _cycle(CID))
    ordinary = dataclasses.replace(_cycle(None), execution_overrides={})
    assert await approved_change_request(executor._artifact_vault, ordinary) is None


async def test_a_change_request_altered_after_its_ruling_is_refused_at_the_seed(executor):
    """Bug caught: a stored change request edited after the supervisor approved its hash
    seeding a manifest nobody ruled on."""
    from squadops.campaigns.change_request import ChangeRequestError

    ref, content = executor._artifact_vault.stored["art_cr"]
    tampered = content.decode().replace("capacity", "capacitee", 1).encode()
    executor._artifact_vault.stored["art_cr"] = (ref, tampered)

    with pytest.raises(ChangeRequestError, match="does not match its hash"):
        await executor._workload_gate._seed_increment(_cycle(CID), _PROPOSAL_RUN)
