"""Every control-log row, projected (SIP-0109 §13; step 6).

Entered at ``CampaignProgress.cycle_ended`` and the launcher's mark — the non-route writers — over
a ``ProjectingCampaignRegistry`` wrapping the memory registry, with recording audit and event
ports. Before step 6, only the routes' rows reached either projection.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import CampaignState, ControlOperationRefused
from squadops.campaigns.progress import CampaignProgress
from squadops.campaigns.projection import ProjectingCampaignRegistry
from squadops.cycles.cycle_assessment import AssessorIdentity, CycleEvidence, RunRecord, assess
from squadops.cycles.cycle_end import CycleStopReason
from squadops.cycles.models import Cycle, Run, TaskFlowPolicy
from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict
from tests.unit.campaigns.builders import campaign, move, policy

NOW = datetime(2026, 10, 2, 18, 0, tzinfo=UTC)
CID = "cmp_proj00000001"


class _Audit:
    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


class _Bus:
    def __init__(self) -> None:
        self.emitted = []

    def emit(self, event_type, **kwargs):
        self.emitted.append((event_type, kwargs["payload"]["operation"]))


def _rejected(cycle_id):
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


@pytest.fixture
def world():
    inner = MemoryCampaignRegistry()
    audit, bus = _Audit(), _Bus()
    return inner, ProjectingCampaignRegistry(inner, audit=audit, events=bus), audit, bus


async def test_every_row_a_non_route_writer_commits_is_projected_once(world):
    """§13. Bug caught: the launcher's mark and the completion boundary's decision invisible to
    the audit and the event bus — a campaign's run of the night unrecorded in both."""
    inner, projected, audit, bus = world
    draft = campaign(CID, policy=policy(calibration_profile="framing"))
    await inner.create_campaign(
        draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
    )
    await inner.transition(
        CID,
        start_transition(
            draft, actor="owner", actor_role="admin", reason="go", idempotency_key="start"
        ),
    )
    [intent] = await inner.pending_launch_intents()
    cycles = MemoryCycleRegistry()
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

    await projected.mark_launch_intent_launched(intent.launch_id, "cyc_cal", actor="launcher")
    await projected.mark_launch_intent_launched(intent.launch_id, "cyc_cal", actor="launcher")
    await CampaignProgress(
        campaigns=projected,
        cycles=cycles,
        vault=AsyncMock(list_artifacts=AsyncMock(return_value=[])),
        assess=AsyncMock(side_effect=_rejected),
        launch=AsyncMock(),
        clock=lambda: NOW + timedelta(hours=1),
    ).cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)

    assert [(e.action, e.actor_type, e.result) for e in audit.events] == [
        ("campaign.mark_launched", "service", "success"),
        ("campaign.decide", "service", "success"),
    ]
    assert bus.emitted == [
        ("campaign.transitioned", "mark_launched"),
        ("campaign.transitioned", "decide"),
    ]


async def test_a_refused_row_is_audited_as_denied_and_emits_nothing(world):
    inner, projected, audit, bus = world
    await inner.create_campaign(
        campaign(CID), actor="o", actor_role="admin", reason="r", idempotency_key="create"
    )

    with pytest.raises(ControlOperationRefused):
        await projected.transition(CID, move(CampaignState.BUILDING, "k"))

    assert [(e.action, e.result, e.denial_reason) for e in audit.events] == [
        ("campaign.decide", "denied", "illegal_transition")
    ]
    assert bus.emitted == []


async def test_a_failing_projection_fails_no_operation(world):
    """§13: the projections are fail-open; the control record is the authority."""
    inner, _projected, _audit, _bus = world
    broken = MagicMock()
    broken.record.side_effect = RuntimeError("audit down")
    bus = MagicMock()
    bus.emit.side_effect = RuntimeError("bus down")
    projected = ProjectingCampaignRegistry(inner, audit=broken, events=bus)
    await inner.create_campaign(
        campaign(CID), actor="o", actor_role="admin", reason="r", idempotency_key="create"
    )

    result = await projected.transition(CID, move(CampaignState.CALIBRATING, "k"))

    assert result.campaign.state is CampaignState.CALIBRATING
    assert len(await inner.control_log(CID)) == 2
