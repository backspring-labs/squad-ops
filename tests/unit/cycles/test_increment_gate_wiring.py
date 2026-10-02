"""The increment gate as the cycle reaches it (SIP-0109 §9.2; #1801).

Entered at ``WorkloadGate.decide``, the seam ``execute_cycle`` calls between the proposal workload
and framing, on the real executor with a memory campaign registry. What reaches the campaign is
asserted, and what the gate does next.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
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
_CHANGE_REQUEST = yaml.safe_dump(
    {
        "proposal_id": "prop_cap",
        "version": 1,
        "baseline_tree": "sha-accepted",
        "kind": "feature",
        "content_hash": "hash-cap-v1",
    }
)
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
        execution_overrides={"plan_artifact_refs": ["art_manifest"]},
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


@pytest.fixture
def executor(campaigns):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    artifacts = {
        "art_cr": _ref("art_cr", "change_request", "change_request.yaml", _CHANGE_REQUEST),
        "art_manifest": _ref(
            "art_manifest", "document", "interface_manifest.yaml", _QUESTION_FREE_MANIFEST
        ),
    }
    vault = AsyncMock()
    vault.retrieve.side_effect = lambda artifact_id: artifacts[artifact_id]
    vault.list_artifacts.return_value = []
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
    assert stored.proposal.binding == ProposalBinding("prop_cap", 1, "hash-cap-v1", "sha-accepted")
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
