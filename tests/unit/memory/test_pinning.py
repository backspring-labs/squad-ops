"""Pinning through the store (SIP-0110 §0.2, §0.7; slice 3c, #2096): a revision is immutable, a unit
pins once and a restart gets the original, and what is approved later reaches only later units."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore, RevisionConflict
from squadops.memory.approval import revoke
from squadops.memory.declarations import memory_disabled
from squadops.memory.lessons import RecallDisposition, Snapshot, UnitKind, recall
from squadops.memory.pinning import pin_unit
from tests.unit.memory.test_lessons import ASK, T0, _approve, _revision

pytestmark = [pytest.mark.domain_memory]


async def test_a_revision_is_immutable_once_stored():
    """Bug caught: a lesson's text edited in place, so units that pinned it supplied different
    words than the ones its approval and replay check were given for."""
    store = InMemoryCrossCycleMemoryStore()
    rev = _revision("criterion_already_satisfied")

    assert await store.record_revision(rev) is True
    assert await store.record_revision(rev) is False
    with pytest.raises(RevisionConflict):
        await store.record_revision(_revision("criterion_already_satisfied", text="edited"))


async def test_a_unit_pins_once_and_a_restart_gets_the_original():
    """§0.15 restart and unit freeze, through the store. Bugs caught: a restart re-pinning with a
    lesson approved meanwhile, or a running unit seeing an approval given after it was admitted."""
    store = InMemoryCrossCycleMemoryStore()
    rev = _revision("criterion_already_satisfied")
    await store.record_revision(rev)
    admitted = T0 + timedelta(hours=1)

    first = await pin_unit(
        store,
        unit_kind=UnitKind.CAMPAIGN,
        unit_id="cmp_x",
        project_id="group_run",
        pinned_at=admitted,
        disabled=False,
    )
    await store.record_approval(_approve(rev, at=admitted + timedelta(minutes=5)))
    after_restart = await pin_unit(
        store,
        unit_kind=UnitKind.CAMPAIGN,
        unit_id="cmp_x",
        project_id="group_run",
        pinned_at=admitted + timedelta(hours=1),
        disabled=False,
    )
    later_unit = await pin_unit(
        store,
        unit_kind=UnitKind.CYCLE,
        unit_id="cyc_later",
        project_id="group_run",
        pinned_at=admitted + timedelta(hours=1),
        disabled=False,
    )

    assert after_restart == first and first.entries == ()
    assert recall(first, ASK).disposition is RecallDisposition.NONE_ELIGIBLE
    assert recall(later_unit, ASK).disposition is RecallDisposition.SUPPLIED


async def test_a_revocation_reaches_units_admitted_after_it_only():
    """§0.7. Bug caught: a revocation silently changing a running unit's guidance (emergency
    revocation restarts the work under a new snapshot instead)."""
    store = InMemoryCrossCycleMemoryStore()
    rev = _revision("criterion_already_satisfied")
    await store.record_revision(rev)
    approval = _approve(rev)
    await store.record_approval(approval)
    running = await pin_unit(
        store,
        unit_kind=UnitKind.CYCLE,
        unit_id="cyc_running",
        project_id="group_run",
        pinned_at=T0 + timedelta(hours=1),
        disabled=False,
    )

    await store.record_revocation(
        revoke(approval, by="owner", reason="harmful", now=T0 + timedelta(hours=2))
    )
    later = await pin_unit(
        store,
        unit_kind=UnitKind.CYCLE,
        unit_id="cyc_later",
        project_id="group_run",
        pinned_at=T0 + timedelta(hours=3),
        disabled=False,
    )

    assert len((await store.get_snapshot(UnitKind.CYCLE, "cyc_running")).entries) == 1
    assert running.entries and later.entries == ()
    # §0.7, D9: the revocation names the running unit that holds it, for its halt or restart.
    assert [s.unit_id for s in await store.list_snapshots_holding(approval.approval_id)] == [
        "cyc_running"
    ]


async def test_a_snapshot_survives_the_store_whole():
    """Bug caught: a stored pin that re-reads its lessons from rows later, so it is not the pin."""
    store = InMemoryCrossCycleMemoryStore()
    rev = _revision("criterion_already_satisfied")
    await store.record_revision(rev)
    await store.record_approval(_approve(rev))
    snapshot = await pin_unit(
        store,
        unit_kind=UnitKind.CAMPAIGN,
        unit_id="cmp_x",
        project_id="group_run",
        pinned_at=T0 + timedelta(hours=1),
        disabled=False,
    )

    assert Snapshot.from_dict(json.loads(json.dumps(snapshot.to_dict()))) == snapshot


@pytest.mark.parametrize(
    "config, disabled",
    [
        (None, False),
        ({}, False),
        ({"memory": "enabled"}, False),
        ({"memory": " Disabled "}, True),
        ({"memory": "off"}, ValueError),
        ({"memory": False}, ValueError),  # YAML's `memory: no`
        ({"memory": ""}, ValueError),
    ],
)
def test_the_declaration_is_one_of_two_words_and_anything_else_is_refused(config, disabled):
    """§0.7. Bug caught: an unknown value read either way. Read as enabled it hands a counted roll
    its lessons (D12); read as disabled it leaves a memory arm without memory."""
    if disabled is ValueError:
        with pytest.raises(ValueError, match="memory must be 'disabled' or 'enabled'"):
            memory_disabled(config)
    else:
        assert memory_disabled(config) is disabled


class _WithdrawnOnceRead:
    """A records store where a withdrawal lands just after the pin's first read (#2545's race)."""

    def __init__(self, inner, record_id: str) -> None:
        self._inner, self._id, self.reads = inner, record_id, 0

    async def list_project(self, project_id: str):
        self.reads += 1
        held = await self._inner.list_project(project_id)
        if self.reads == 1:
            from squadops.memory.records import withdrawn

            record = await self._inner.get(self._id)
            gone = withdrawn(record, by="ada", at=T0, why="harmful")
            await self._inner.append_status(self._id, gone.status_changes[-1])
        return held


class _RevokedOnceRead(InMemoryCrossCycleMemoryStore):
    """A lesson store where the approval is revoked just after the pin's first read of them."""

    reads = 0

    async def list_approvals(self, project_id: str):
        self.reads += 1
        held = await super().list_approvals(project_id)
        if self.reads == 1:
            for a in held:
                await self.record_revocation(revoke(a, by="owner", reason="harm", now=T0))
        return held


async def test_an_instruction_withdrawn_while_the_unit_is_pinned_is_not_held_by_it():
    """#2545, through ``pin_unit``. Bug caught: a withdrawal answered between the pin's read and
    its write found no snapshot, told the operator later units pin without it, and the unit being
    admitted pinned it anyway, unnamed."""
    from adapters.memory.records import InMemoryMemoryRecords
    from tests.unit.memory.test_project_instructions import _instruction

    store, inner = InMemoryCrossCycleMemoryStore(), InMemoryMemoryRecords()
    await inner.create(_instruction("mrec_w", "qa.test"))

    pinned = await pin_unit(
        store, unit_kind=UnitKind.CYCLE, unit_id="cyc_x", project_id="group_run", pinned_at=T0,
        disabled=False, records=_WithdrawnOnceRead(inner, "mrec_w"),
    )  # fmt: skip

    assert pinned.instructions == ()
    assert (await store.get_snapshot(UnitKind.CYCLE, "cyc_x")).instructions == ()
    assert await store.list_snapshots_pinning("mrec_w") == []


async def test_a_lesson_revoked_while_the_unit_is_pinned_is_not_held_by_it():
    """The same race for a revocation (#2545): the unit being admitted must not hold a lesson
    whose revocation found no snapshot to name."""
    store = _RevokedOnceRead()
    rev = _revision("criterion_already_satisfied")
    await store.record_revision(rev)
    approval = _approve(rev, at=T0 - timedelta(hours=1))
    await store.record_approval(approval)

    pinned = await pin_unit(
        store, unit_kind=UnitKind.CAMPAIGN, unit_id="cmp_x", project_id="group_run",
        pinned_at=T0, disabled=False,
    )  # fmt: skip

    assert pinned.entries == ()
    assert await store.list_snapshots_holding(approval.approval_id) == []


async def test_a_pin_with_no_removal_is_written_once_and_a_settle_read_that_fails_keeps_it():
    """Bugs caught: every pin rewritten on the settle read; a settle read that fails costing the
    unit its snapshot."""
    from adapters.memory.records import InMemoryMemoryRecords
    from tests.unit.memory.test_project_instructions import _instruction

    class _FailsSecondRead(InMemoryMemoryRecords):
        reads = 0

        async def list_project(self, project_id: str):
            self.reads += 1
            if self.reads > 1:
                raise ConnectionError("the pool is gone")
            return await super().list_project(project_id)

    class _CountsRebinds(InMemoryCrossCycleMemoryStore):
        writes = 0

        async def rebind_snapshot(self, snapshot, *, after):
            self.writes += 1
            await super().rebind_snapshot(snapshot, after=after)

    for records in (InMemoryMemoryRecords(), _FailsSecondRead()):
        await records.create(_instruction("mrec_k", "qa.test"))
        store = _CountsRebinds()

        pinned = await pin_unit(
            store, unit_kind=UnitKind.CYCLE, unit_id="cyc_y", project_id="group_run",
            pinned_at=T0, disabled=False, records=records,
        )  # fmt: skip

        assert [p.record_id for p in pinned.instructions] == ["mrec_k"]
        assert store.writes == 0
