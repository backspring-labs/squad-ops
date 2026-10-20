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
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_unit
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
        _plan(cycle), recall=SnapshotRecall(store, records=records), unit=unit_of(cycle),
        stack="fullstack_fastapi_react", run_id=f"run_{cycle_id[-10:]}", now=T0,
    )  # fmt: skip
    [design] = [e for e in envelopes if str(e.task_type) == DESIGN]
    [instruction] = design.inputs[PROJECT_INSTRUCTIONS_INPUT]["instructions"]
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
             "digest": f"sha256:{cycle.cycle_id}"},
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

    async def record_cycle_binding(self, binding):
        self.writes += 1
        await super().record_cycle_binding(binding)


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

    assert handed == [{"ref": "fake:doc:spec@r9", "required": True}]
    assert (store.reads, store.writes) == (0, 0)


async def test_a_rebinding_reaches_a_running_cycle_as_that_cycle_binds_it():
    """§5ad with §5v. Bugs caught: a campaign's re-bound revision reaching its running cycle
    with its ``@current`` reference unbound, holding the very tasks the re-binding was for; an
    ended cycle's binding rewritten after the fact."""
    from types import SimpleNamespace

    from squadops.campaigns.models import LaunchIntentState
    from tests.unit.api.test_rebinding import RECORDS, WHERE, _World
    from tests.unit.campaigns.builders import campaign

    api = _World()
    api.client.app.state.reference_resolvers = {"fake": _PerCycle()}
    body = {"kind": "instruction", "scope": "project", "project_id": "group_run",
            "body": "Read the spec.", "applicability": WHERE,
            "references": [{"ref": REF, "required": True}]}  # fmt: skip
    record_id = api.client.post(RECORDS, json=body).json()["record_id"]
    cmp = campaign(CID)
    await api.campaigns.create_campaign(
        cmp, actor="ada", actor_role="admin", reason="t", idempotency_key="create"
    )
    from squadops.memory.pinning import pin_campaign

    await pin_campaign(api.store, cmp, now=T0, records=api.records,
                       resolvers={"fake": _PerCycle()})  # fmt: skip
    running, ended = (
        dataclasses.replace(_framing_cycle(), cycle_id=c, campaign_id=CID)
        for c in ("cyc_running00", "cyc_ended0000")
    )
    for c in (running, ended):
        await api.cycles.create_cycle(c)
    launched = [SimpleNamespace(state=LaunchIntentState.LAUNCHED, cycle_id=c.cycle_id)
                for c in (running, ended)]  # fmt: skip

    async def launch_intents(_campaign_id):
        return launched

    async def get_cycle_end(cycle_id):
        return object() if cycle_id == ended.cycle_id else None

    api.campaigns.launch_intents = launch_intents
    api.cycles.get_cycle_end = get_cycle_end
    api.client.post(f"{RECORDS}/{record_id}/revisions",
                      json={**{k: body[k] for k in ("applicability", "references")},
                            "body": "Read the spec, then its notes."})  # fmt: skip

    applied = api.rebind(record_id, kind="campaign", unit_id=CID, why="the spec moved")

    assert applied.status_code == 201, applied.text
    binding = await api.store.get_cycle_binding(running.cycle_id)
    [instruction] = binding.instructions
    assert (instruction.revision, [r.ref for r in instruction.references]) == (
        2, [f"fake:doc:spec@{running.cycle_id}"],
    )  # fmt: skip
    assert await api.store.get_cycle_binding(ended.cycle_id) is None


async def test_a_binding_of_an_earlier_revision_is_never_handed_for_the_pinned_one():
    """§5ad with §5v. Bug caught: a cycle's binding matched by record alone. After a re-binding
    that couldn't reach this cycle, the cycle would be handed the replaced revision's text, bound,
    under the pin that replaced it, rather than holding."""
    from squadops.memory.cycle_bindings import CycleBinding
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
    await store.record_cycle_binding(
        CycleBinding("cyc_stale0000", UnitKind.CAMPAIGN.value, CID, (stale,), T0)
    )

    with pytest.raises(TaskInstructionsUnavailable, match=f"required reference {REF}"):
        await _handed(store, records, "cyc_stale0000")


async def _pinned_campaign_as_is(store, records):
    return await pin_unit(
        store, unit_kind=UnitKind.CAMPAIGN, unit_id=CID, project_id="group_run", pinned_at=T0,
        disabled=False, records=records, resolvers={"fake": _PerCycle()},
    )  # fmt: skip
