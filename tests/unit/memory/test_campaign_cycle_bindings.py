"""A campaign's repository references, bound per cycle against its snapshot (SIP-0110 §5ad, the owner's
ruling of 2026-10-20; #2179 T16).

Entered where the runtime enters:
- a campaign's launch builds the cycle (``CampaignLaunchService._build_cycle``);
- each dispatch is composed by the live composer (``supply_lessons`` through ``SnapshotRecall``);
- a re-binding goes through its route.

The stand-in resolver is the repository family's shape: it binds nothing for the campaign, which pins no
source commit, and binds each cycle at a revision of that cycle's own.

What bugs would these catch?
- a campaign's cycles all reading the campaign's unbound pin, so a required repository reference holds
  every task of a source-backed campaign;
- one cycle reading another's binding;
- a reference bound at dispatch;
- a binding that can't be read, read as no binding;
- a re-binding during a running cycle reaching that cycle unbound;
- a binding recorded, or read, where no instruction names ``@current``.
"""

from __future__ import annotations

import dataclasses

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.cycle_bindings import instructions_bound_for
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import cycle_binding, pin_unit
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.records import Reference
from squadops.memory.task_instructions import TaskInstructionsUnavailable
from squadops.ports.memory.references import (
    BoundReference,
    ReferenceResolverPort,
    ReferenceUnresolved,
)
from tests.unit.api.test_campaign_start import CID, _sandbox_provider, world  # noqa: F401
from tests.unit.api.test_launch_instructions import _service
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan
from tests.unit.memory.test_project_instructions import DESIGN, T0, _instruction

pytestmark = [pytest.mark.domain_memory]

REF = "fake:doc:spec@current"


class _PerCycle(ReferenceResolverPort):
    """Binds a cycle at a revision of its own, as the repository family binds at each cycle's
    pinned commit, and refuses the campaign, which pins none."""

    family = "fake"

    async def bind(self, ref: str, ctx) -> BoundReference:
        if ctx.unit_kind != UnitKind.CYCLE.value:
            raise ReferenceUnresolved(f"{ctx.unit_kind} {ctx.unit_id} pins no source commit")
        base = ref.rsplit("@", 1)[0]
        return BoundReference(f"{base}@{ctx.unit_id}", ctx.unit_id, f"sha256:{ctx.unit_id}")

    async def read(self, bound: BoundReference, ctx) -> str:
        return bound.revision


async def _pinned_campaign(store, records, *, ref: str = REF):
    await records.create(_instruction("mrec_ref", DESIGN, references=(Reference(ref, True),)))
    return await pin_unit(
        store, unit_kind=UnitKind.CAMPAIGN, unit_id=CID, project_id="group_run", pinned_at=T0,
        disabled=False, records=records, resolvers={"fake": _PerCycle()},
    )  # fmt: skip


def _launcher(w, records, store):
    service = _service(w, records)
    service._creation = dataclasses.replace(
        service._creation, memory_store=store, reference_resolvers={"fake": _PerCycle()}
    )
    return service


async def _handed(store, records, cycle_id: str):
    """What a campaign cycle's design task is handed, as the live composer hands it."""
    cycle = dataclasses.replace(_framing_cycle(), cycle_id=cycle_id, campaign_id=CID)
    envelopes = await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(store, records=records, resolvers={"fake": _PerCycle()}),
        unit=unit_of(cycle),
        stack="fullstack_fastapi_react", run_id=f"run_{cycle_id[-10:]}", now=T0,
    )  # fmt: skip
    [design] = [e for e in envelopes if str(e.task_type) == DESIGN]
    [instruction] = design.inputs[PROJECT_INSTRUCTIONS_INPUT]["instructions"]
    # §3.6: an instruction the cycle bound carries no unbound entry, the campaign's included.
    assert "unbound" not in instruction, instruction
    return instruction["references"]


async def test_each_cycle_reads_the_references_it_bound_at_its_launch(world):  # noqa: F811
    """§5ad. Bugs caught: the cycle reading the campaign's unbound pin; one cycle reading another's
    binding; the binding made at dispatch rather than at the launch."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    snapshot = await _pinned_campaign(store, records)
    world.start()
    [intent] = await world.campaigns.launch_intents(CID)
    launcher = _launcher(world, records, store)

    first = await launcher._build_cycle(intent)
    second = await launcher._build_cycle(intent)

    assert snapshot.instructions[0].unbound  # the campaign's own pin binds nothing
    for cycle in (first, second):
        assert await _handed(store, records, cycle.cycle_id) == [
            {"ref": f"fake:doc:spec@{cycle.cycle_id}", "required": True,
             "digest": f"sha256:{cycle.cycle_id}", "content": cycle.cycle_id},
        ]  # fmt: skip


async def test_a_cycle_with_no_binding_holds_a_required_reference():
    """§3.6, as before §5ad. Bug caught: a campaign cycle launched before its binding existed,
    or by a launch that couldn't bind, handed its required reference unbound."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _pinned_campaign(store, records)

    with pytest.raises(TaskInstructionsUnavailable, match=f"required reference {REF}"):
        await _handed(store, records, "cyc_unbound00")


class _BindingUnread(InMemoryCrossCycleMemoryStore):
    async def get_cycle_binding(self, cycle_id):
        raise TimeoutError("the store did not answer")


async def test_a_binding_that_cant_be_read_holds_the_task():
    """Bug caught: a cycle's binding that can't be read, read as no binding, so the dispatch goes
    ahead on the campaign's pin, or, for an optional reference, omits what the cycle had bound."""
    store, records = _BindingUnread(), InMemoryMemoryRecords()
    await _pinned_campaign(store, records)

    with pytest.raises(TaskInstructionsUnavailable, match="the store did not answer"):
        await _handed(store, records, "cyc_unread000")


class _Counting(InMemoryCrossCycleMemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self.reads = self.writes = 0

    async def get_cycle_binding(self, cycle_id):
        self.reads += 1
        return await super().get_cycle_binding(cycle_id)

    async def record_cycle_bindings(self, cycle_id, unit_kind, unit_id, entries, bound_at):
        self.writes += 1
        await super().record_cycle_bindings(cycle_id, unit_kind, unit_id, entries, bound_at)


async def test_a_campaign_naming_no_current_reference_records_and_reads_no_binding(world):  # noqa: F811
    """Bug caught: a binding written at every launch, and read at every dispatch, of every
    campaign, the window's included, where no instruction names ``@current``, so the store sits
    on every campaign's path for nothing."""
    store, records = _Counting(), InMemoryMemoryRecords()
    await _pinned_campaign(store, records, ref="fake:doc:spec@r9")
    world.start()
    [intent] = await world.campaigns.launch_intents(CID)

    cycle = await _launcher(world, records, store)._build_cycle(intent)
    handed = await _handed(store, records, cycle.cycle_id)

    # Written with its revision, so it carries no digest; it is still read for its content (#2179).
    assert handed == [{"ref": "fake:doc:spec@r9", "required": True, "content": "r9"}]
    assert (store.reads, store.writes) == (0, 0)


async def _campaign_world(*records_refs: str):
    """The re-binding route's world, with this campaign pinned over one instruction per reference,
    and its three launched cycles: one running, one paused (which can resume), one cancelled."""
    from types import SimpleNamespace

    from squadops.campaigns.models import LaunchIntentState
    from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
    from squadops.cycles.models import RunStatus
    from squadops.memory.pinning import pin_campaign
    from tests.unit.api.test_rebinding import RECORDS, WHERE, _World
    from tests.unit.campaigns.builders import campaign

    api = _World()
    api.client.app.state.reference_resolvers = {"fake": _PerCycle()}
    ids = []
    for ref in records_refs:
        body = {"kind": "instruction", "scope": "project", "project_id": "group_run",
                "body": f"Read {ref}.", "applicability": WHERE,
                "references": [{"ref": ref, "required": True}]}  # fmt: skip
        ids.append(api.client.post(RECORDS, json=body).json()["record_id"])
    cmp = campaign(CID)
    await api.campaigns.create_campaign(
        cmp, actor="ada", actor_role="admin", reason="t", idempotency_key="create"
    )
    await pin_campaign(api.store, cmp, now=T0, records=api.records,
                       resolvers={"fake": _PerCycle()})  # fmt: skip
    running, paused, ended = (
        dataclasses.replace(_framing_cycle(), cycle_id=c, campaign_id=CID)
        for c in ("cyc_running00", "cyc_paused000", "cyc_ended0000")
    )
    for c in (running, paused, ended):
        await api.cycles.create_cycle(c)
    await api.cycles.cancel_cycle(ended.cycle_id)
    await api.run(paused, "run_paused00", RunStatus.PAUSED)
    # Its run paused, and the ending is recorded; ``runs resume`` re-enters it (cycle_end.py).
    await api.cycles.record_cycle_end(
        RecordedEnd(paused.cycle_id, "run_paused00", CycleStopReason.RUN_PAUSED)
    )
    launched = [SimpleNamespace(state=LaunchIntentState.LAUNCHED, cycle_id=c.cycle_id)
                for c in (running, paused, ended)]  # fmt: skip

    async def launch_intents(_campaign_id):
        return launched

    api.campaigns.launch_intents = launch_intents
    return api, ids, (running, paused, ended)


def _revise(api, record_id: str, ref: str, text: str):
    from tests.unit.api.test_rebinding import RECORDS, WHERE

    response = api.client.post(
        f"{RECORDS}/{record_id}/revisions",
        json={"body": text, "applicability": WHERE, "references": [{"ref": ref, "required": True}]},
    )
    assert response.status_code == 201, response.text


async def test_a_rebinding_reaches_running_and_paused_cycles_as_each_binds_it():
    """§5ad with §5v. Bugs caught: a campaign's re-bound revision reaching its running cycle with
    its ``@current`` reference unbound, holding the very tasks the re-binding was for; a paused
    cycle, which can resume, skipped as ended; a cancelled cycle's binding rewritten."""
    api, [record_id], (running, paused, ended) = await _campaign_world(REF)
    _revise(api, record_id, REF, "Read the spec, then its notes.")

    applied = api.rebind(record_id, kind="campaign", unit_id=CID, why="the spec moved")

    assert applied.status_code == 201, applied.text
    for live in (running, paused):
        [instruction] = (await api.store.get_cycle_binding(live.cycle_id)).instructions
        assert (instruction.revision, [r.ref for r in instruction.references]) == (
            2, [f"fake:doc:spec@{live.cycle_id}"],
        )  # fmt: skip
    assert await api.store.get_cycle_binding(ended.cycle_id) is None


async def test_rebinding_one_record_keeps_the_cycles_binding_of_another():
    """The second read of #2570. Bug caught: a re-binding that rebuilds the cycle's binding from
    nothing, so re-binding one instruction erases another's, and its required reference holds."""
    other = "fake:doc:notes@current"
    api, [spec_id, notes_id], (running, _paused, _ended) = await _campaign_world(REF, other)
    for record_id, ref in ((spec_id, REF), (notes_id, other)):
        _revise(api, record_id, ref, f"Read {ref}, revised.")
    api.rebind(notes_id, kind="campaign", unit_id=CID, why="the notes moved")

    applied = api.rebind(spec_id, kind="campaign", unit_id=CID, why="the spec moved")

    assert applied.status_code == 201, applied.text
    held = (await api.store.get_cycle_binding(running.cycle_id)).instructions
    assert sorted((p.record_id, p.revision) for p in held) == sorted([(spec_id, 2), (notes_id, 2)])


@pytest.mark.parametrize("fault", ["cycles-unread", "resolver-fault"])
async def test_a_rebinding_its_running_cycles_cant_bind_is_refused_with_nothing_written(fault):
    """The second and third reads of #2570. Bugs caught: the snapshot re-bound and then the cycles'
    bindings failed, answered 500 with no control-log row, invisible to the ledger and refused on
    retry as already bound; or a running cycle left holding the reference the re-binding was for."""
    from squadops.campaigns.models import ControlOperation

    api, [record_id], (running, _paused, _ended) = await _campaign_world(REF)
    _revise(api, record_id, REF, "Read the spec, then its notes.")
    if fault == "cycles-unread":

        async def unreadable(_campaign_id):
            raise TimeoutError("the campaign registry did not answer")

        api.campaigns.launch_intents = unreadable
    else:
        api.client.app.state.reference_resolvers = {"fake": _Faulting()}

    refused = api.rebind(record_id, kind="campaign", unit_id=CID, why="the spec moved")

    assert refused.status_code == 503, refused.text
    assert refused.json()["detail"]["error"]["code"] == "CYCLES_UNBOUND"
    snapshot = await api.store.get_snapshot(UnitKind.CAMPAIGN, CID)
    assert (len(snapshot.rebindings), snapshot.instructions[0].revision) == (0, 1)
    assert [e for e in await api.campaigns.control_log(CID)
            if e.operation is ControlOperation.REBIND] == []  # fmt: skip
    assert await api.store.get_cycle_binding(running.cycle_id) is None


async def test_a_binding_of_an_earlier_revision_is_never_handed_for_the_pinned_one():
    """§5ad with §5v. Bug caught: a cycle's binding matched by record alone. After a re-binding
    that couldn't reach this cycle, the cycle would be handed the replaced revision's text, bound,
    under the pin that replaced it, rather than holding."""
    from squadops.memory.records import PinnedInstruction, Revision, Source, revised

    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    original = _instruction("mrec_ref", DESIGN, references=(Reference(REF, True),))
    await records.create(original)
    second = revised(
        original,
        Revision(number=2, body="Read the revised spec.", author="ada", created_at=T0,
                 source=Source("api_call"), confirmed_by="ada",
                 applicability=original.current.applicability,
                 references=(Reference(REF, True),)),
    )  # fmt: skip
    await records.append_revision("mrec_ref", second.current)
    await _pinned_campaign_as_is(store, records)
    stale = PinnedInstruction(
        "mrec_ref", 1, original.current.body, original.current.applicability,
        (Reference("fake:doc:spec@cyc_stale0000", True, digest="sha256:old"),),
    )  # fmt: skip
    await store.record_cycle_bindings("cyc_stale0000", UnitKind.CAMPAIGN.value, CID, (stale,), T0)

    with pytest.raises(TaskInstructionsUnavailable, match=f"required reference {REF}"):
        await _handed(store, records, "cyc_stale0000")


async def _pinned_campaign_as_is(store, records):
    return await pin_unit(
        store, unit_kind=UnitKind.CAMPAIGN, unit_id=CID, project_id="group_run", pinned_at=T0,
        disabled=False, records=records, resolvers={"fake": _PerCycle()},
    )  # fmt: skip


async def test_the_sweep_fills_a_cycle_a_rebinding_could_not_reach(world):  # noqa: F811
    """The second and third reads of #2570, entered at the runtime's own sweep
    (``main._sweep_campaigns``). Bugs caught: a cycle whose re-binding couldn't be stored, or raced
    its launch, left holding its required reference for the rest of its life, since re-binding the
    same revision again is refused; a fill that waits for a drain, which the cycle's run may never
    see before it ends."""
    from squadops.memory.rebinding import rebound
    from squadops.memory.records import Revision, Source, pinned_of, revised

    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _pinned_campaign(store, records)
    world.start()
    launcher = _launcher(world, records, store)
    await launcher.drain()
    [cycle_id] = [i.cycle_id for i in await world.campaigns.launch_intents(CID) if i.cycle_id]
    record = await records.get("mrec_ref")
    second = revised(
        record,
        Revision(number=2, body="Read the revised spec.", author="ada", created_at=T0,
                 source=Source("api_call"), confirmed_by="ada",
                 applicability=record.current.applicability, references=(Reference(REF, True),)),
    )  # fmt: skip
    await records.append_revision("mrec_ref", second.current)
    snapshot = await store.get_snapshot(UnitKind.CAMPAIGN, CID)
    replacement = dataclasses.replace(pinned_of(second), unbound=((REF, "pins no source commit"),))
    await store.rebind_snapshot(
        rebound(snapshot, second, by="ada", at=T0, why="the spec moved", replacement=replacement)
    )  # the campaign is re-bound, and this cycle's binding isn't reached

    with pytest.raises(TaskInstructionsUnavailable, match=f"required reference {REF}"):
        await _handed(store, records, cycle_id)
    await _one_sweep(launcher)

    assert await _handed(store, records, cycle_id) == [
        {
            "ref": f"fake:doc:spec@{cycle_id}",
            "required": True,
            "digest": f"sha256:{cycle_id}",
            "content": cycle_id,
        }
    ]


class _Faulting(_PerCycle):
    async def bind(self, ref, ctx):
        if ctx.unit_kind == UnitKind.CYCLE.value:
            raise TimeoutError("the repository did not answer")
        return await super().bind(ref, ctx)


async def test_a_resolver_fault_at_launch_is_repeated_never_bound_as_nothing(world):  # noqa: F811
    """The second read of #2570. Bug caught: a timeout in the family's resolver at a cycle's
    launch kept as "unbound", so the cycle holds its required reference for life, where the next
    drain could have bound it."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _pinned_campaign(store, records)
    world.start()
    [intent] = await world.campaigns.launch_intents(CID)
    launcher = _launcher(world, records, store)
    launcher._creation = dataclasses.replace(
        launcher._creation, reference_resolvers={"fake": _Faulting()}
    )

    with pytest.raises(TimeoutError):
        await launcher._build_cycle(intent)


class _SnapshotUnreadable(InMemoryCrossCycleMemoryStore):
    async def get_snapshot(self, unit_kind, unit_id):
        from squadops.ports.memory.cross_cycle import RecordIncompatible

        raise RecordIncompatible("a body this code can't read")


async def test_an_unreadable_snapshot_refuses_the_launch_not_every_launch_behind_it(world):  # noqa: F811
    """The second read of #2570. Bug caught: a snapshot this code can't read raised as a fault,
    which every drain repeats, holding every intent queued behind it. It is refused, so the
    campaign escalates."""
    from squadops.campaigns.launcher import LaunchRefused

    world.start()
    [intent] = await world.campaigns.launch_intents(CID)
    launcher = _launcher(world, InMemoryMemoryRecords(), _SnapshotUnreadable())

    with pytest.raises(LaunchRefused, match="snapshot can't be read"):
        await launcher._build_cycle(intent)


async def _one_sweep(launcher) -> None:
    """One pass of the runtime's campaign sweep, with this launcher (``main._sweep_campaigns``)."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    from squadops.api.runtime import main

    launcher.retry_blocked = AsyncMock(return_value=[])
    progress = SimpleNamespace(
        sweep_ruling_bounds=AsyncMock(), rehear_ended=AsyncMock(return_value=[])
    )
    with (
        patch.object(
            main.asyncio, "sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()])
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await main._sweep_campaigns(
            SimpleNamespace(campaign_launch=launcher, campaign_progress=progress)
        )


async def test_the_sweep_fills_each_campaign_and_cycle_apart_and_never_an_ended_one(world):  # noqa: F811
    """The third read of #2570. Bugs caught: one snapshot or one cycle that can't be read stopping
    the fill for every campaign or cycle after it; a cancelled cycle filled."""
    from types import SimpleNamespace

    from squadops.campaigns.models import LaunchIntentState

    store, records = _UnreadableFor({"cmp_broken0000"}), InMemoryMemoryRecords()
    await _pinned_campaign(store, records)
    world.start()
    launcher = _launcher(world, records, store)
    cycles = []
    for cycle_id in ("cyc_unreadabl", "cyc_fillable0", "cyc_cancelld0"):
        cycle = dataclasses.replace(_framing_cycle(), cycle_id=cycle_id, campaign_id=CID)
        await world.cycles.create_cycle(cycle)
        cycles.append(cycle_id)
    await world.cycles.cancel_cycle("cyc_cancelld0")
    store.unreadable_cycles = {"cyc_unreadabl"}
    broken = SimpleNamespace(campaign_id="cmp_broken0000", state=None)
    listed = [broken, *await world.campaigns.list_campaigns("group_run")]

    async def list_campaigns(_project_id):
        return listed

    async def launch_intents(_campaign_id):
        return [SimpleNamespace(state=LaunchIntentState.LAUNCHED, cycle_id=c) for c in cycles]

    world.campaigns.list_campaigns, world.campaigns.launch_intents = list_campaigns, launch_intents

    filled = await launcher.reconcile_bindings()

    assert filled == ["cyc_fillable0"]
    assert await store.get_cycle_binding("cyc_cancelld0") is None


class _UnreadableFor(InMemoryCrossCycleMemoryStore):
    """A store whose snapshot of some campaigns, and binding of some cycles, can't be read."""

    def __init__(self, campaigns) -> None:
        super().__init__()
        self.unreadable_campaigns, self.unreadable_cycles = set(campaigns), set()

    async def get_snapshot(self, unit_kind, unit_id):
        if unit_id in self.unreadable_campaigns:
            raise TimeoutError("the snapshot did not answer")
        return await super().get_snapshot(unit_kind, unit_id)

    async def get_cycle_binding(self, cycle_id):
        if cycle_id in self.unreadable_cycles:
            raise TimeoutError("the binding did not answer")
        return await super().get_cycle_binding(cycle_id)


async def test_a_stale_write_adds_its_own_revision_and_never_touches_another():
    """The third and fifth reads of #2570. Bug caught: a writer that read the snapshot before a
    re-binding (the sweep, or a second re-binding) storing the older revision over the newer one
    the re-binding just stored, so the cycle reads the re-bound record from the campaign's pin and
    holds. Each revision is its own entry, so the older one lands beside it and the pinned one is
    still the one handed."""
    from squadops.memory.cycle_bindings import as_bound_for
    from squadops.memory.records import InstructionApplicability, PinnedInstruction

    where = InstructionApplicability((DESIGN,), ("*",), ("*",))
    store = InMemoryCrossCycleMemoryStore()

    def entry(revision, ref="fake:doc:spec@current"):
        return PinnedInstruction("mrec_ref", revision, f"r{revision}", where,
                                 (Reference(ref, True, digest=f"d{revision}"),))  # fmt: skip

    await store.record_cycle_bindings("cyc_x", "campaign", CID, (entry(3, "fake:doc:spec@b3"),), T0)
    await store.record_cycle_bindings("cyc_x", "campaign", CID, (entry(2, "fake:doc:spec@b2"),), T0)

    binding = await store.get_cycle_binding("cyc_x")
    assert [p.revision for p in binding.instructions] == [2, 3]
    [handed] = as_bound_for((entry(3),), binding)
    assert handed.references[0].ref == "fake:doc:spec@b3"


async def test_a_rebinding_holds_launches_and_stores_each_cycles_entry_before_its_commit():
    """The fifth read of #2570, entered at the route. Bugs caught:
    - the running cycles listed outside the launch lock, so a cycle launched between the listing
      and the commit binds the revision being replaced, and nothing binds the new one;
    - the cycles' entries stored after the snapshot names the new revision, so a dispatch between
      the two reads the new revision with no entry and holds;
    - the new revision's entry replacing the old one's, so a dispatch before the commit, still on
      the old revision, finds no entry and holds."""
    from squadops.memory.records import pinned_of

    api, [record_id], (running, _paused, _ended) = await _campaign_world(REF)
    at_launch = await instructions_bound_for(
        (pinned_of(await api.records.get(record_id)),),
        {"fake": _PerCycle()},
        cycle_binding(running),
    )
    await api.store.record_cycle_bindings(running.cycle_id, "campaign", CID, at_launch, T0)
    _revise(api, record_id, REF, "Read the spec, then its notes.")
    lock, seen = api.launches.lock, {}
    listed, commit = api.campaigns.launch_intents, api.store.rebind_snapshot

    async def launch_intents(campaign_id):
        seen["listed_held"] = lock.locked()
        return await listed(campaign_id)

    async def rebind_snapshot(snapshot):
        held = (await api.store.get_cycle_binding(running.cycle_id)).instructions
        seen["at_commit"] = (lock.locked(), sorted(p.revision for p in held))
        await commit(snapshot)

    api.campaigns.launch_intents, api.store.rebind_snapshot = launch_intents, rebind_snapshot

    applied = api.rebind(record_id, kind="campaign", unit_id=CID, why="the spec moved")

    assert applied.status_code == 201, applied.text
    assert seen == {"listed_held": True, "at_commit": (True, [1, 2])}
    assert not lock.locked()


async def test_a_drain_launches_nothing_while_a_rebinding_holds_its_launches(world, monkeypatch):  # noqa: F811
    """The fifth read of #2570, entered at the drain. Bug caught: the lock a re-binding holds not
    being the one every drain launches under, so the launch it exists to keep out still falls
    between the re-binding's listing and its commit."""
    import asyncio

    from squadops.api import campaign_launch
    from squadops.campaigns.models import LaunchIntentState

    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _pinned_campaign(store, records)
    prepare = campaign_launch.prepare_cycle

    async def fault(*args, **kwargs):
        raise RuntimeError("the artifact vault is unreachable")

    monkeypatch.setattr(campaign_launch, "prepare_cycle", fault)
    world.start()  # the start's own drain faults, so its intent is still pending
    monkeypatch.setattr(campaign_launch, "prepare_cycle", prepare)
    launcher = _launcher(world, records, store)

    async with launcher.launches_held():
        drain = asyncio.create_task(launcher.drain())
        await asyncio.sleep(0.05)
        states = [i.state for i in await world.campaigns.launch_intents(CID)]
        assert not drain.done()
    await drain

    assert states == [LaunchIntentState.PENDING]
    assert [i.state for i in await world.campaigns.launch_intents(CID)] == [
        LaunchIntentState.LAUNCHED
    ]


@pytest.mark.parametrize("change", ["withdrawn", "names-a-revision"])
async def test_a_rebinding_with_nothing_for_a_cycle_to_bind_reads_no_cycle(change):
    """The fourth read of #2570. Bugs caught: a withdrawal refused (503) as if its cycles had to
    bind it; a replacement naming no ``@current`` refused because the cycles couldn't be read,
    though no cycle had anything to bind."""
    from squadops.campaigns.models import ControlOperation
    from tests.unit.api.test_rebinding import RECORDS

    api, [record_id], (running, _paused, _ended) = await _campaign_world(REF)
    if change == "withdrawn":
        api.client.post(f"{RECORDS}/{record_id}/withdrawal", json={"why": "no longer applies"})
    else:
        _revise(api, record_id, "fake:doc:spec@r9", "Read revision r9 of the spec.")

    async def unreadable(_campaign_id):
        raise TimeoutError("the campaign registry did not answer")

    api.campaigns.launch_intents = unreadable

    applied = api.rebind(record_id, kind="campaign", unit_id=CID, why=change)

    assert applied.status_code == 201, applied.text
    assert [e.entry_id for e in await api.campaigns.control_log(CID)
            if e.operation is ControlOperation.REBIND] == [applied.json()["control_log_entry_id"]]  # fmt: skip
    assert await api.store.get_cycle_binding(running.cycle_id) is None


async def test_a_same_revision_write_never_rewrites_an_entry():
    """The fourth read of #2570. Bug caught: the sweep, having read "missing" before a re-binding
    stored the entry, writing the same revision again after a dispatch was handed it, so the
    cycle's later tasks could read a different binding of the same revision."""
    from squadops.memory.records import InstructionApplicability, PinnedInstruction

    where = InstructionApplicability((DESIGN,), ("*",), ("*",))
    store = InMemoryCrossCycleMemoryStore()

    def entry(digest):
        return PinnedInstruction("mrec_ref", 2, "r2", where,
                                 (Reference("fake:doc:spec@r2", True, digest=digest),))  # fmt: skip

    await store.record_cycle_bindings("cyc_x", "campaign", CID, (entry("sha256:first"),), T0)
    await store.record_cycle_bindings("cyc_x", "campaign", CID, (entry("sha256:again"),), T0)

    [held] = (await store.get_cycle_binding("cyc_x")).instructions
    assert held.references[0].digest == "sha256:first"


async def test_the_sweep_fills_every_project_after_one_whose_campaigns_cant_be_listed(world):  # noqa: F811
    """The fifth read of #2570, entered at the sweep's own reconciliation. Bug caught: one project
    whose campaigns can't be listed stopping the fill for every project after it."""
    from types import SimpleNamespace

    from squadops.campaigns.models import LaunchIntentState

    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _pinned_campaign(store, records)
    world.start()
    launcher = _launcher(world, records, store)
    cycle = dataclasses.replace(_framing_cycle(), cycle_id="cyc_fillable0", campaign_id=CID)
    await world.cycles.create_cycle(cycle)
    projects = [SimpleNamespace(project_id="broken"), SimpleNamespace(project_id="group_run")]

    async def list_projects():
        return projects

    registry = SimpleNamespace(list_projects=list_projects)
    launcher._creation = dataclasses.replace(launcher._creation, project_registry=registry)
    listed = world.campaigns.list_campaigns

    async def list_campaigns(project_id):
        if project_id == "broken":
            raise TimeoutError("the registry did not answer")
        return await listed(project_id)

    async def launch_intents(_campaign_id):
        return [SimpleNamespace(state=LaunchIntentState.LAUNCHED, cycle_id=cycle.cycle_id)]

    world.campaigns.list_campaigns, world.campaigns.launch_intents = list_campaigns, launch_intents

    assert await launcher.reconcile_bindings() == ["cyc_fillable0"]


async def test_a_repeated_launch_fills_the_cycle_it_finds_before_its_first_run(world, monkeypatch):  # noqa: F811
    """The sixth read of #2570, entered at the drain. Bug caught: a launch repeated by its launch
    id (its first attempt stored the cycle, then faulted before the mark) binds the cycle it builds
    and throws away, not the stored one it finds; a re-binding committed between the attempts
    listed no launched cycle, so the stored cycle starts holding only the old revision and its
    first task holds."""
    from squadops.api import campaign_launch
    from squadops.campaigns.models import LaunchIntentState
    from squadops.memory.rebinding import rebound
    from squadops.memory.records import Revision, Source, pinned_of, revised

    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await _pinned_campaign(store, records)
    prepare = campaign_launch.prepare_cycle

    async def fault(*args, **kwargs):
        raise RuntimeError("the artifact vault is unreachable")

    monkeypatch.setattr(campaign_launch, "prepare_cycle", fault)
    world.start()  # the start's own drain faults, so its intent is still pending
    monkeypatch.setattr(campaign_launch, "prepare_cycle", prepare)
    launcher = _launcher(world, records, store)
    mark, marks = world.campaigns.mark_launch_intent_launched, []

    async def mark_once_faulting(*args, **kwargs):
        marks.append(args)
        if len(marks) == 1:
            raise ConnectionError("the registry dropped the mark after the cycle was stored")
        return await mark(*args, **kwargs)

    world.campaigns.mark_launch_intent_launched = mark_once_faulting
    await launcher.drain()
    [stored] = await world.cycles.list_cycles("group_run")
    record = await records.get("mrec_ref")
    second = revised(
        record,
        Revision(number=2, body="Read the revised spec.", author="ada", created_at=T0,
                 source=Source("api_call"), confirmed_by="ada",
                 applicability=record.current.applicability, references=(Reference(REF, True),)),
    )  # fmt: skip
    await records.append_revision("mrec_ref", second.current)
    snapshot = await store.get_snapshot(UnitKind.CAMPAIGN, CID)
    replacement = dataclasses.replace(pinned_of(second), unbound=((REF, "pins no source commit"),))
    await store.rebind_snapshot(
        rebound(snapshot, second, by="ada", at=T0, why="the spec moved", replacement=replacement)
    )  # the re-binding lists no launched cycle of the campaign, so it reaches none

    started = await launcher.drain()

    [intent] = await world.campaigns.launch_intents(CID)
    assert (intent.state, intent.cycle_id) == (LaunchIntentState.LAUNCHED, stored.cycle_id)
    assert [r.cycle_id for r in started] == [stored.cycle_id]
    assert await _handed(store, records, stored.cycle_id) == [
        {"ref": f"fake:doc:spec@{stored.cycle_id}", "required": True,
         "digest": f"sha256:{stored.cycle_id}", "content": stored.cycle_id},
    ]  # fmt: skip
