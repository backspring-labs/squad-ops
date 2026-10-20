"""A project instruction's ``@current`` reference, bound at its unit's admission (SIP-0110 Appendix A
§3.6, §3.7; #2179 T16, the project part). Entered where admission pins (``pin_unit``,
``pin_standalone_cycle``) and where the live composer supplies (``supply_lessons``), with a resolver
standing in for a family's (the repository's is Project Lifecycle Management's, SIP-0112 §B.5.1).

What bugs would these catch? ``@current`` resolved at dispatch, so a target revised mid-unit reaches
the unit's later tasks; two arms admitted together binding different revisions; a unit admitted
after the change still binding the old one; a required reference that won't bind handed to the task
half-bound instead of holding it; the resolver not told the commit the unit's source pins.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.recall import SnapshotRecall
from adapters.memory.records import InMemoryMemoryRecords
from squadops.capabilities.lesson_supply import supply_lessons, unit_of
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import pin_campaign, pin_standalone_cycle, pin_unit
from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.records import Reference
from squadops.memory.task_instructions import TaskInstructionsUnavailable
from squadops.ports.memory.references import (
    BoundReference,
    ReferenceResolverPort,
    ReferenceUnresolved,
)
from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan
from tests.unit.memory.test_project_instructions import DESIGN, T0, _instruction

pytestmark = [pytest.mark.domain_memory]

REF = "fake:doc:spec@current"


class _Resolver(ReferenceResolverPort):
    """A family whose current revision the test moves, and which can refuse."""

    family = "fake"

    def __init__(self) -> None:
        self.revision, self.refuse, self.seen = "r1", None, []

    async def bind(self, ref: str, ctx) -> BoundReference:
        self.seen.append(ctx)
        if self.refuse:
            raise ReferenceUnresolved(self.refuse)
        base = ref.rsplit("@", 1)[0]
        return BoundReference(f"{base}@{self.revision}", self.revision, f"sha256:{self.revision}")

    async def read(self, bound: BoundReference, ctx) -> str:
        return bound.revision


async def _world(*, required: bool = True):
    store, records, resolver = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords(), _Resolver()
    await records.create(_instruction("mrec_ref", DESIGN, references=(Reference(REF, required),)))
    return store, records, resolver


async def _admit(store, records, resolver, unit_id: str):
    return await pin_unit(
        store, unit_kind=UnitKind.CYCLE, unit_id=unit_id, project_id="group_run", pinned_at=T0,
        disabled=False, records=records, resolvers={"fake": resolver},
    )  # fmt: skip


async def _handed(store, records, cycle):
    envelopes = await supply_lessons(
        _plan(cycle), recall=SnapshotRecall(store, records=records), unit=unit_of(cycle),
        stack="fullstack_fastapi_react", run_id="run_ref000001", now=T0,
    )  # fmt: skip
    [design] = [e for e in envelopes if str(e.task_type) == DESIGN]
    [instruction] = design.inputs[PROJECT_INSTRUCTIONS_INPUT]["instructions"]
    [exposure] = [
        e for e in await store.list_exposures("run_ref000001") if e.query.task_type == DESIGN
    ]
    return instruction["references"], exposure


async def test_a_unit_keeps_the_revision_bound_at_admission_and_a_later_unit_binds_the_new_one():
    """T16, project part. Bugs caught: ``@current`` resolved again at dispatch, after the target
    moved; the two arms of a comparison admitted together bound to different revisions; a unit
    admitted after the move still bound to the old revision."""
    store, records, resolver = await _world()
    cycle = _framing_cycle()
    arm_a = await _admit(store, records, resolver, cycle.cycle_id)
    arm_b = await _admit(store, records, resolver, "cyc_arm_b")
    resolver.revision = "r2"  # the target is revised after admission

    handed, exposure = await _handed(store, records, cycle)
    later = await _admit(store, records, resolver, "cyc_later")

    assert handed == [{"ref": "fake:doc:spec@r1", "required": True, "digest": "sha256:r1"}]
    assert exposure.project_instructions["bound_references"] == [
        {"record_id": "mrec_ref", "ref": "fake:doc:spec@r1", "digest": "sha256:r1"}
    ]
    assert [r.ref for p in (arm_a, arm_b) for r in p.instructions[0].references] == [
        "fake:doc:spec@r1", "fake:doc:spec@r1",
    ]  # fmt: skip
    assert later.instructions[0].references[0].ref == "fake:doc:spec@r2"


async def test_a_required_reference_that_wont_bind_holds_its_task_and_an_optional_one_runs():
    """§3.6. Bugs caught: a required reference that couldn't be bound handed to the task as written,
    so it runs without what it was required to read; an optional one holding the task."""
    for required in (True, False):
        store, records, resolver = await _world(required=required)
        resolver.refuse = "no file at that commit"
        cycle = _framing_cycle()
        pinned = await _admit(store, records, resolver, cycle.cycle_id)

        assert pinned.instructions[0].unbound == ((REF, "no file at that commit"),)
        if required:
            with pytest.raises(TaskInstructionsUnavailable, match=f"required reference {REF}"):
                await _handed(store, records, cycle)
        else:
            handed, _ = await _handed(store, records, cycle)
            assert handed == [{"ref": REF, "required": False}]


class _Sourced:
    """A cycle with the source context Project Lifecycle Management gives it (#2484)."""

    def __init__(self, cycle, commit: str) -> None:
        self._cycle = cycle
        self.source_context = SimpleNamespace(development_baseline_commit=commit)

    def __getattr__(self, name):
        return getattr(self._cycle, name)


async def test_the_resolver_is_given_the_commit_the_units_source_pins():
    """SIP-0112 §B.5.1. Bugs caught: a repository reference bound at a default commit, or at none,
    on a cycle whose source context pins one; a campaign, which has no source of its own, handed
    a commit from somewhere."""
    store, records, resolver = await _world()
    commit = "a" * 40

    await pin_standalone_cycle(
        store, _Sourced(_framing_cycle(), commit), now=T0, records=records,
        resolvers={"fake": resolver},
    )  # fmt: skip
    await pin_campaign(
        store, SimpleNamespace(campaign_id="cmp_ref", project_id="group_run"), now=T0,
        records=records, resolvers={"fake": resolver},
    )  # fmt: skip

    assert [(c.unit_kind, c.source_commit) for c in resolver.seen] == [
        ("cycle", commit), ("campaign", None),
    ]  # fmt: skip


async def test_a_pin_with_no_resolver_for_the_family_keeps_the_reference_unbound():
    store, records, resolver = await _world()
    pinned = await pin_unit(
        store, unit_kind=UnitKind.CYCLE, unit_id=dataclasses.replace(_framing_cycle()).cycle_id,
        project_id="group_run", pinned_at=T0, disabled=False, records=records, resolvers={},
    )  # fmt: skip

    assert pinned.instructions[0].held_by == [(REF, "no resolver binds the fake family")]
