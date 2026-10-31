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
        _plan(cycle), recall=SnapshotRecall(store, records=records, resolvers={"fake": _Resolver()}),
        unit=unit_of(cycle),
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

    # #2179: handed with its content, read at the revision bound (the fake reads its revision).
    assert handed == [
        {"ref": "fake:doc:spec@r1", "required": True, "digest": "sha256:r1", "content": "r1"}
    ]
    assert exposure.project_instructions["bound_references"] == [
        {"record_id": "mrec_ref", "ref": "fake:doc:spec@r1", "digest": "sha256:r1"}
    ]
    assert [r.ref for p in (arm_a, arm_b) for r in p.instructions[0].references] == [
        "fake:doc:spec@r1", "fake:doc:spec@r1",
    ]  # fmt: skip
    assert later.instructions[0].references[0].ref == "fake:doc:spec@r2"


@pytest.mark.parametrize("required", [True, False], ids=["required", "optional"])
async def test_a_reference_that_wont_bind_holds_its_task_if_required_and_is_omitted_if_not(
    required,
):
    """§3.6. Bugs caught: a required reference that couldn't be bound handed to the task as written,
    so it runs without what it was required to read; an optional one holding the task, or handed
    as ``@current`` as if bound rather than omitted and disclosed (the second read)."""
    store, records, resolver = await _world(required=required)
    resolver.refuse = "no file at that commit"
    cycle = _framing_cycle()
    pinned = await _admit(store, records, resolver, cycle.cycle_id)

    assert pinned.instructions[0].unbound == ((REF, "no file at that commit"),)
    if required:
        with pytest.raises(TaskInstructionsUnavailable, match=f"required reference {REF}"):
            await _handed(store, records, cycle)
    else:
        handed, exposure = await _handed(store, records, cycle)
        assert handed == []
        assert exposure.project_instructions["omitted_references"] == [
            {"record_id": "mrec_ref", "ref": REF, "why": "no file at that commit"}
        ]


class _Crashing(_Resolver):
    async def bind(self, ref, ctx):
        raise TimeoutError("the repository did not answer")


async def test_a_resolver_that_fails_leaves_its_reference_unbound_not_the_unit_unread():
    """The second read. Bug caught: a timeout in one family's resolver read as the records being
    unreadable, holding every task of the unit for good, its lessons and other instructions too."""
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await records.create(_instruction("mrec_ref", DESIGN, references=(Reference(REF, False),)))
    await records.create(_instruction("mrec_plain", DESIGN, text="Keep the join idempotent."))

    pinned = await pin_unit(
        store, unit_kind=UnitKind.CYCLE, unit_id="cyc_x", project_id="group_run", pinned_at=T0,
        disabled=False, records=records, resolvers={"fake": _Crashing()},
    )  # fmt: skip

    assert pinned.instructions_unread is None
    assert [p.record_id for p in pinned.instructions] == ["mrec_ref", "mrec_plain"]
    assert pinned.instructions[0].unbound == ((REF, "the fake resolver failed: TimeoutError"),)


async def test_a_bound_reference_survives_the_stored_snapshot():
    """Bug caught: the digest or the unbound list dropped when a snapshot is read back, so a
    restart hands what admission didn't bind, or names no revision."""
    from squadops.memory.lessons import Snapshot

    store, records, resolver = await _world()
    await records.create(
        _instruction("mrec_opt", DESIGN, references=(Reference("other:doc:x@current", False),))
    )
    pinned = await _admit(store, records, resolver, "cyc_rt")

    again = Snapshot.from_dict(pinned.to_dict())

    assert again.instructions == pinned.instructions
    assert again.instructions[0].references[0].digest == "sha256:r1"
    assert again.instructions[1].unbound == (
        ("other:doc:x@current", "no resolver binds the other family"),
    )


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
