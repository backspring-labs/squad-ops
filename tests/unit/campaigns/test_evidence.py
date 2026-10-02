"""A campaign's evidence package and digest (SIP-0109 §14; #1710).

The wiring test enters at ``CampaignProgress.cycle_ended`` — the completion boundary's campaign
call — where a rejected calibration closes the campaign, and reads the vault after it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.continuation import ContinuationDecision, CycleEnding, PendingAction
from squadops.campaigns.evidence import CycleRecords, digest, package
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import CampaignState
from squadops.campaigns.progress import (
    EVIDENCE_ARTIFACT_TYPE,
    CampaignProgress,
    decision_transition,
)
from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord, assess
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.models import Cycle, Run, TaskFlowPolicy
from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict
from tests.unit.campaigns.builders import campaign, move, policy

NOW = datetime(2026, 10, 2, 17, 0, tzinfo=UTC)
CID = "cmp_evid00000001"


def _assessment(cycle_id: str):
    run = RunRecord("run_impl", 1, "implementation", "completed", NOW, NOW)
    outcome = CycleOutcome(
        verdict=RunVerdict.REJECTED,
        verified=(),
        failed=("tests_pass",),
        unverified=(),
        run_count=1,
        criteria_verified=(),
        criteria_total=(),
    )
    return assess(
        outcome,
        CycleEvidence(cycle_id=cycle_id, runs=(run,), verification_summary_runs=("run_impl",)),
        assessor=AssessorIdentity("2.0.0", None),
    )


class _Vault:
    def __init__(self) -> None:
        self.stored: dict[str, tuple] = {}

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def list_artifacts(self, *, project_id=None, artifact_type=None, **_):
        return [r for r, _ in self.stored.values() if r.artifact_type == artifact_type]


@pytest.fixture
async def closed():
    campaigns, cycles, vault = MemoryCampaignRegistry(), MemoryCycleRegistry(), _Vault()
    progress = CampaignProgress(
        campaigns=campaigns,
        cycles=cycles,
        vault=vault,
        assess=AsyncMock(side_effect=_assessment),
        launch=AsyncMock(),
        clock=lambda: NOW + timedelta(hours=1),
    )
    draft = campaign(CID, policy=policy(calibration_profile="framing"))
    await campaigns.create_campaign(
        draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
    )
    await campaigns.transition(
        CID,
        start_transition(
            draft, actor="owner", actor_role="admin", reason="go", idempotency_key="start"
        ),
    )
    cycle = Cycle(
        cycle_id="cyc_cal",
        project_id="group_run",
        created_at=NOW,
        created_by="launcher",
        prd_ref=None,
        squad_profile_id="full-38",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        campaign_id=CID,
        kind="calibration",
    )
    await cycles.create_cycle(cycle)
    run = Run(
        "run_impl", "cyc_cal", 1, "completed", "system", "cfg", workload_type="implementation"
    )
    await cycles.create_run(run)
    [intent] = await campaigns.pending_launch_intents()
    await campaigns.mark_launch_intent_launched(intent.launch_id, "cyc_cal", actor="l")
    await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)
    return progress, campaigns, vault


async def test_a_closed_campaign_leaves_its_package_and_digest_once(closed):
    """§14, #1710. Bugs caught: a campaign that closes leaving nothing a frontier reader can
    triage, or a re-materialization storing a second copy of the same records."""
    progress, campaigns, vault = closed

    again = await progress.materialize_package(CID)

    parts = {r.metadata["part"]: (r, c) for r, c in vault.stored.values()}
    doc = json.loads(parts["package"][1])
    assert (await campaigns.get_campaign(CID)).state is CampaignState.COMPLETED
    assert len(vault.stored) == 2
    assert again == (
        doc["identity"],
        parts["package"][0].artifact_id,
        parts["digest"][0].artifact_id,
    )
    assert [c["cycle_id"] for c in doc["cycles"]] == ["cyc_cal"]
    assert doc["cycles"][0]["decision"]["row"] == 2  # a rejected calibration stops the campaign
    assert all(r.artifact_type == EVIDENCE_ARTIFACT_TYPE for r, _ in vault.stored.values())


async def test_the_digest_says_how_the_campaign_ended_and_what_failed(closed):
    _progress, _campaigns, vault = closed

    [text] = [c.decode() for r, c in vault.stored.values() if r.metadata["part"] == "digest"]

    assert f"# Campaign {CID}: completed (failure)" in text
    assert "- nothing was accepted" in text
    assert (
        "| `cyc_cal` | calibration | assessed | rejected | row 2: failure | unattributed |" in text
    )


def test_the_identity_is_the_records_and_moves_with_them():
    """Bug caught: an identity that does not move when a record does — two different packages
    reading as one, and the second never stored."""
    c = campaign(CID)
    one = package(c, [], [], [CycleRecords("cyc_1", "calibration", {"verdict": "accepted"}, ())])
    same = package(c, [], [], [CycleRecords("cyc_1", "calibration", {"verdict": "accepted"}, ())])
    other = package(c, [], [], [CycleRecords("cyc_1", "calibration", {"verdict": "rejected"}, ())])

    assert one["identity"] == same["identity"] != other["identity"]


async def test_an_escalated_campaign_tells_the_owner_what_to_rule():
    registry = MemoryCampaignRegistry()
    await registry.create_campaign(
        campaign(CID), actor="o", actor_role="admin", reason="r", idempotency_key="k"
    )
    await registry.transition(CID, move(CampaignState.CALIBRATING, "cal"))
    stored = await registry.get_campaign(CID)
    await registry.transition(
        CID,
        decision_transition(
            stored,
            ContinuationDecision("cyc_1", 9, action=PendingAction.ESCALATE),
            ending=CycleEnding.ASSESSED,
            verdict=RunVerdict.BLOCKED_UNVERIFIED,
            launch=None,
        ),
    )

    text = digest(
        package(await registry.get_campaign(CID), await registry.control_log(CID), [], [])
    )

    assert "The campaign is escalated (§10 row 9). Resume it naming an action, or abort it." in text
