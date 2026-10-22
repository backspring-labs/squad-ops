"""A run held on a task's binding sections, and its release (SIP-0110 Appendix A §3.6; #2178).

Entered where the live run holds: ``execute_run`` over the memory registry, with the snapshot
recall over the typed records' store; and ``BindingHolds.supplied``, the one seam every supply
site of the run goes through (provisioning, the re-dispatch, the correction and pulse repairs),
for its endings.
"""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from squadops.campaigns.models import CampaignState
from squadops.cycles.models import BindingHold, RunStatus
from squadops.events.types import EventType
from squadops.execution.binding_holds import BindingHolds
from squadops.execution.execution_errors import _CancellationError
from squadops.memory.exposures import Exposure, exposure_id_for
from squadops.memory.lessons import Snapshot
from squadops.memory.rebinding import runs_handed
from squadops.memory.recall import RecallQuery, UnitKind
from squadops.memory.records import InstructionApplicability, PinnedInstruction, withdrawn
from squadops.memory.task_instructions import (
    TASK_INSTRUCTIONS_INPUT,
    TaskInstructionsUnavailable,
    dispatched,
)
from tests.unit.cycles.test_failure_recall import _PROFILE, _framing_cycle, _framing_run, _pinned
from tests.unit.memory.test_task_instructions import DESIGN, _instruction

pytestmark = [pytest.mark.domain_cycles]

T0 = datetime(2026, 10, 21, tzinfo=UTC)


class _Events:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, dict | None]] = []

    def emit(self, event_type, *, entity_type, entity_id, context, payload=None):
        self.emitted.append((event_type, payload))

    def of(self, event_type) -> list[dict | None]:
        return [p for t, p in self.emitted if t == event_type]


async def test_a_run_held_at_provisioning_waits_then_starts_when_its_instruction_changes(
    reply_router,
):
    """Wiring, entered at ``execute_run``: a framing run whose design-plan instruction is too big
    for the prompt, withdrawn while the run is held. Bugs caught: the run failed instead of held;
    a task dispatched on a partial binding; the held task's exposure read as a dispatch, which
    refuses the very §5w change that releases it (and, recorded under the attempt's id, would
    stand in for the dispatch's own); the run never resuming once the change landed."""
    from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor
    from squadops.tasks.models import TaskResult

    store = InMemoryCrossCycleMemoryStore()
    await _pinned(store, UnitKind.CYCLE, "cyc_recall", disabled=True)
    records = InMemoryMemoryRecords()
    record = _instruction("cyc_recall", DESIGN, text="x" * 2_000_000)
    await records.create(record)
    cycle, run = _framing_cycle(), _framing_run()
    registry = MemoryCycleRegistry()
    await registry.create_cycle(cycle)
    await registry.create_run(run)
    profiles = AsyncMock()
    profiles.resolve_snapshot.return_value = (_PROFILE, "sha")
    events = _Events()
    executor = DispatchedFlowExecutor(
        cycle_registry=registry, artifact_vault=AsyncMock(), queue=reply_router.bind(AsyncMock()),
        squad_profile=profiles, task_timeout=5.0, reply_router=reply_router, project_registry=None,
        campaign_registry=None, campaign_progress=None, box_verdict=None,
        failure_recall=SnapshotRecall(store, records=records), event_bus=events,
    )  # fmt: skip
    handed: list[tuple[str, bool]] = []

    def responder(env):
        handed.append((env["task_type"], TASK_INSTRUCTIONS_INPUT in (env.get("inputs") or {})))
        return TaskResult(task_id=env["task_id"], status="SUCCEEDED", outputs={"summary": "ok"})

    reply_router.responder = responder
    at_the_hold: dict = {}

    real_sleep = asyncio.sleep

    async def tick(*_args, **_kwargs):
        await real_sleep(0)  # yields, so a hold that never ends times out rather than spins
        held = await registry.get_run(run.run_id)
        if held.open_hold is None or at_the_hold:
            return
        exposures = await store.list_exposures(run.run_id)
        at_the_hold.update(
            status=held.status, hold=held.open_hold, dispatched=list(handed),
            exposures=[(x.exposure_id, x.held) for x in exposures],
            refused_by=dispatched((DESIGN,), exposures, cycle_id=cycle.cycle_id),
        )  # fmt: skip
        gone = withdrawn(record, by="ada", at=T0, why="too long for the prompt")
        await records.append_status(record.record_id, gone.status_changes[-1])

    with patch("squadops.execution.binding_holds.asyncio.sleep", side_effect=tick):
        await _bounded(executor.execute_run(cycle_id=cycle.cycle_id, run_id=run.run_id))

    hold = at_the_hold["hold"]
    assert (at_the_hold["status"], hold.task_type, hold.sections) == (
        "paused", DESIGN, ("task_instructions",)
    )  # fmt: skip
    assert [kind for _, _, kind in hold.unresolved] == ["input"]
    assert at_the_hold["dispatched"] == [] and at_the_hold["refused_by"] == []
    design_task = hold.task_id
    assert at_the_hold["exposures"] == [(exposure_id_for(run.run_id, design_task) + ":held", True)]

    ended = await registry.get_run(run.run_id)
    assert ended.status == RunStatus.COMPLETED.value
    assert [(h.hold_id, h.cause) for h in ended.binding_holds] == [
        ("hold_1", "instruction_changed")
    ]
    assert (DESIGN, False) in handed and all(not given for _, given in handed)
    after = {x.exposure_id: x for x in await store.list_exposures(run.run_id)}
    assert not after[exposure_id_for(run.run_id, design_task)].held
    [paused] = events.of(EventType.RUN_PAUSED)
    assert paused["binding_hold"]["task_type"] == DESIGN
    assert {"binding_hold": "hold_1", "cause": "instruction_changed"} in events.of(
        EventType.RUN_RESUMED
    )


def _held(kind: str = "store", sections: tuple[str, ...] = ("task_instructions",)):
    return TaskInstructionsUnavailable(
        "task t_design is held",
        task_id="t_design",
        task_type=DESIGN,
        unresolved=(("mrec_1@1", "the memory records could not be read", kind),),
        sections=sections,
    )


async def _registry_with_run(*, holds: tuple[BindingHold, ...] = ()) -> MemoryCycleRegistry:
    registry = MemoryCycleRegistry()
    run = dataclasses.replace(_framing_run(), status=RunStatus.RUNNING.value)
    await registry.create_run(run)
    for hold in holds:
        await registry.record_binding_hold(run.run_id, hold)
    return registry


async def _bounded(held):
    """A hold polls until something ends it: a test whose ending never comes fails, not hangs."""
    return await asyncio.wait_for(held, timeout=5)


def _holds(registry, *, events=None, campaigns=None, fill=None, await_box=None) -> BindingHolds:
    async def cancelled(run_id):
        return (await registry.get_run(run_id)).status == RunStatus.CANCELLED.value

    return BindingHolds(
        cycle_registry=registry,
        campaign_registry=campaigns,
        event_bus=events or _Events(),
        is_cancelled=cancelled,
        await_box=await_box or AsyncMock(),
        fill=fill,
        clock=lambda: T0,
        poll_s=0,
    )


@pytest.mark.parametrize(
    "ending", ["store-answers", "cancelled", "expiry-wins-the-race", "resumed-and-answered"]
)
async def test_a_hold_ends_exactly_once(ending):
    """Each way a hold ends, through the registry's compare-and-set. Bugs caught: a re-supply that
    lands after the Campaign's ruling bound released the hold resuming a run the sweep is
    cancelling, and overwriting ``expired``; a cancelled run's hold left open, so the Campaign
    reads it held; a store failure released as an instruction change; a run resumed while held
    carrying on with its hold still open, which the sweep then expires under it; the run resuming
    before the box is read."""
    run_id = _framing_run().run_id
    resumed_hold = BindingHold(
        "hold_1", "t_design", DESIGN, (("mrec_1@1", "unread", "store"),), T0,
        sections=("task_instructions",),
    )  # fmt: skip
    registry = await _registry_with_run(
        holds=(resumed_hold,) if ending == "resumed-and-answered" else ()
    )
    await_box = AsyncMock()
    holds = _holds(registry, await_box=await_box)
    calls = 0

    async def supply():
        nonlocal calls
        calls += 1
        if ending == "resumed-and-answered":
            return "composed"
        if calls == 1:
            raise _held()
        if ending == "cancelled":
            await registry.cancel_run(run_id)
            raise _held()
        if ending == "expiry-wins-the-race":
            # The sweep's expiry lands between the poll's read and the re-supply's release.
            await registry.release_binding_hold(run_id, "hold_1", released_at=T0, cause="expired")
            await registry.cancel_run(run_id)
        return "composed"

    if ending in ("cancelled", "expiry-wins-the-race"):
        with pytest.raises(_CancellationError):
            await _bounded(holds.supplied(run_id, _framing_cycle(), supply))
    else:
        assert await _bounded(holds.supplied(run_id, _framing_cycle(), supply)) == "composed"

    run = await registry.get_run(run_id)
    expected = {
        "store-answers": ("running", "store_answered", 1),
        "cancelled": ("cancelled", "cancelled", 0),
        "expiry-wins-the-race": ("cancelled", "expired", 0),
        "resumed-and-answered": ("running", "store_answered", 0),
    }[ending]
    assert (run.status, run.binding_holds[0].cause, await_box.await_count) == expected
    assert len(run.binding_holds) == 1 and run.open_hold is None


async def test_a_held_exposure_is_neither_a_dispatch_nor_a_handing():
    """§5w's check and §5v's read exposures. Bugs caught: the held task's exposure, whose project
    section was complete beside an incomplete task section, read as the revision being handed, so
    the re-binding that releases the hold is sent down the restart path; or as a dispatch, so the
    instruction change that releases it is refused."""
    pinned = PinnedInstruction(
        record_id="mrec_proj", revision=2, text="Use the repository's lint config.",
        applicability=InstructionApplicability((DESIGN,), ("*",), ("*",)),
    )  # fmt: skip
    snapshot = Snapshot(
        snapshot_id="snp_1", unit_kind=UnitKind.CYCLE, unit_id="cyc_recall", pinned_at=T0,
        disabled=True, instructions=(pinned,),
    )  # fmt: skip

    def exposure(task_disposition: str) -> Exposure:
        return Exposure(
            run_id="run_recall0001", task_id="t_design", cycle_id="cyc_recall", agent_id="neo",
            seam="plan_writing",
            query=RecallQuery(project_id="group_run", task_type=DESIGN, role="dev", stack="s",
                              model_family="f", unit_kind=UnitKind.CYCLE, unit_id="cyc_recall"),
            recalled={"disposition": "disabled"}, recorded_at=T0,
            task_instructions={"disposition": task_disposition, "supplied": [], "unresolved": []},
            project_instructions={"disposition": "supplied",
                                  "supplied": [{"record_id": "mrec_proj", "revision": "2"}],
                                  "unresolved": []},
        )  # fmt: skip

    held, ran = exposure("incomplete"), exposure("supplied")

    assert held.exposure_id.endswith(":held") and not ran.exposure_id.endswith(":held")
    assert dispatched((DESIGN,), [held], cycle_id="cyc_recall") == []
    assert runs_handed(snapshot, "mrec_proj", [held]) == []
    assert dispatched((DESIGN,), [ran], cycle_id="cyc_recall") == [("run_recall0001", "t_design")]
    assert runs_handed(snapshot, "mrec_proj", [ran]) == [("cyc_recall", "run_recall0001")]


async def test_a_campaign_cycles_hold_is_escalated_and_filled_by_the_launchers_binder():
    """§24bw's half, entered at the hold: a Campaign cycle held on a project instruction's
    required reference. Bugs caught: no ``escalation_opened`` row, so the owner never sees it and
    the ruling bound never ends it; the re-supply binding on its own instead of through the
    launcher's fill, so it waits on the next sweep; a re-binding's release recorded as an
    instruction change."""
    run_id = _framing_run().run_id
    registry = await _registry_with_run()
    written = []
    campaigns = SimpleNamespace(
        get_campaign=AsyncMock(return_value=SimpleNamespace(state=CampaignState.BUILDING)),
        control_log=AsyncMock(return_value=[]),
        transition=AsyncMock(side_effect=lambda campaign_id, t: written.append((campaign_id, t))),
    )
    filled: list[str] = []
    cycle = _framing_cycle(campaign_id="cmp_1")

    async def fill(cycle_id):
        filled.append(cycle_id)

    async def supply():
        if not filled:
            raise _held(kind="input", sections=("project_instructions",))
        return "composed"

    holds = _holds(registry, campaigns=campaigns, fill=fill)
    assert await _bounded(holds.supplied(run_id, cycle, supply)) == "composed"

    [(campaign_id, opened)] = written
    assert (campaign_id, opened.operation.value) == ("cmp_1", "escalation_opened")
    assert (opened.binding["kind"], opened.binding["hold_class"]) == ("binding_hold", "input")
    assert opened.binding["identity"]["run_id"] == run_id
    assert filled == ["cyc_recall"]
    assert [h.cause for h in (await registry.get_run(run_id)).binding_holds] == ["rebound"]
