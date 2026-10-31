"""The re-binding rules and their store (SIP-0110 Appendix A §3.7; #2179 stage 2).

What bugs would these catch? A re-binding made on a pin that withheld or couldn't read the
instructions, so it invents a binding; a replacement that reorders the unit's instructions; a
re-binding dropped when the snapshot is read back; two re-bindings read from one snapshot both
landing, the second erasing the first; another unit's dispatch, or another revision's, deciding
the path.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.records import InMemoryMemoryRecords
from squadops.memory.lessons import Snapshot, UnitKind
from squadops.memory.rebinding import RebindRefused, rebound, runs_handed
from squadops.memory.records import revised, withdrawn
from squadops.ports.memory.cross_cycle import SnapshotMoved
from tests.unit.memory.test_indicators import _exposure
from tests.unit.memory.test_project_instructions import T0, _admit, _instruction

pytestmark = [pytest.mark.domain_memory]


def _revision_two(record):
    return revised(record, replace(record.current, body="Name each run by its route and date."))


async def _pinned(*records) -> Snapshot:
    store, held = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    for r in records:
        await held.create(r)
    return await _admit(store, held)


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"context_withheld": True}, "memory_context: none"),
        ({"instructions_unread": "the store was down"}, "what it binds is unknown"),
    ],
)
async def test_a_pin_that_holds_no_known_binding_is_never_rebound(change, says):
    record = _instruction("mrec_a", "qa.test")
    snapshot = replace(await _pinned(record), **change)

    with pytest.raises(RebindRefused, match=says):
        rebound(snapshot, _revision_two(record), by="ada", at=T0, why="clarified")


async def test_an_empty_reason_is_refused():
    record = _instruction("mrec_a", "qa.test")
    with pytest.raises(RebindRefused, match="says why"):
        rebound(await _pinned(record), _revision_two(record), by="ada", at=T0, why=" ")


async def test_a_replacement_keeps_its_place_and_a_withdrawal_removes_only_its_own():
    a, b, c = (_instruction(f"mrec_{x}", "qa.test") for x in "abc")
    snapshot = await _pinned(a, b, c)

    swapped = rebound(snapshot, _revision_two(b), by="ada", at=T0, why="clarified")
    dropped = rebound(
        swapped, withdrawn(a, by="ada", at=T0, why="harmful"), by="ada", at=T0, why="withdrawn"
    )

    assert [(p.record_id, p.revision) for p in swapped.instructions] == [
        ("mrec_a", 1), ("mrec_b", 2), ("mrec_c", 1),
    ]  # fmt: skip
    assert [p.record_id for p in dropped.instructions] == ["mrec_b", "mrec_c"]
    assert [(r.record_id, r.replaced.revision) for r in dropped.rebindings] == [
        ("mrec_b", 1), ("mrec_a", 1),
    ]  # fmt: skip


async def test_the_store_keeps_every_rebinding_and_refuses_one_read_from_a_stale_snapshot():
    store, records = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    record = _instruction("mrec_a", "qa.test")
    await records.create(record)
    read = await _admit(store, records)
    first = rebound(read, _revision_two(record), by="ada", at=T0, why="clarified")
    late = rebound(read, withdrawn(record, by="bo", at=T0, why="x"), by="bo", at=T0, why="x")

    with pytest.raises(SnapshotMoved):  # another pin's snapshot, at the right count
        await store.rebind_snapshot(replace(first, snapshot_id="snap_other"))
    await store.rebind_snapshot(first)
    with pytest.raises(SnapshotMoved):
        await store.rebind_snapshot(late)

    held = await store.get_snapshot(UnitKind.CYCLE, "cyc_recall")
    assert Snapshot.from_dict(held.to_dict()) == held == first
    assert [p.revision for p in held.instructions] == [2]


async def test_only_the_units_own_dispatches_of_the_bound_revision_decide_the_path():
    record = _instruction("mrec_a", "qa.test")
    snapshot = await _pinned(record)
    handed = {"disposition": "supplied", "supplied": [{"record_id": "mrec_a", "revision": "1"}]}
    other_revision = {"disposition": "supplied", "supplied": [{"record_id": "mrec_a", "revision": "2"}]}  # fmt: skip
    mine = replace(_exposure("run_mine"), project_instructions=handed)
    mine = replace(mine, query=replace(mine.query, unit_kind=UnitKind.CYCLE, unit_id="cyc_recall"))
    theirs = replace(mine, run_id="run_theirs", query=replace(mine.query, unit_id="cyc_other"))
    stale = replace(mine, run_id="run_stale", project_instructions=other_revision)

    runs = runs_handed(snapshot, "mrec_a", [mine, theirs, stale, mine])

    assert runs == [(mine.cycle_id, "run_mine")]
