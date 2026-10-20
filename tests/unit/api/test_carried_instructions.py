"""A task instruction given with ``carries_into: continuations`` reaches a campaign's repair or retry of
its cycle (SIP-0110 Appendix A §3.7, T12; #2178), entered where the launcher builds that cycle
(``CampaignLaunchService._build_cycle``) from a repair intent whose deciding row names the cycle it
continues.

What bugs would these catch? A continuation that inherits every instruction of the cycle it repairs,
or none of the ones given to carry; a withdrawn one carried; the copy not linked to its original, so
withdrawing one withdraws both, or neither can be told apart; a copy read as an intervention; a launch
that isn't a continuation carrying anything.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from adapters.memory.records import InMemoryMemoryRecords
from squadops.campaigns.models import CycleKind
from squadops.memory.records import Revision, Source, TaskTarget, new_record, withdrawn
from squadops.memory.task_instructions import is_intervention
from tests.unit.api.test_campaign_start import _sandbox_provider, world  # noqa: F401
from tests.unit.api.test_launch_instructions import _service
from tests.unit.memory.test_project_instructions import T0

pytestmark = pytest.mark.auth

CONTINUED = "cyc_continued00"


def _instruction(record_id: str, carries: bool):
    return new_record(
        record_id=record_id, kind="instruction", scope="task", project_id="group_run",
        owner_id="ada",
        revision=Revision(
            number=1, body=f"text of {record_id}", author="ada", created_at=T0,
            source=Source("api_call"), confirmed_by="ada",
            target=TaskTarget(CONTINUED, ("development.develop",),
                              "continuations" if carries else None),
        ),
    )  # fmt: skip


async def _repair_intent(w, *, decided_cycle: str | None = CONTINUED):
    """The calibration intent a start writes, as a repair whose deciding row names ``decided``."""
    w.start()
    [intent] = await w.campaigns.launch_intents("cmp_start0000001")
    repair = dataclasses.replace(intent, cycle_kind=CycleKind.REPAIR)
    row = SimpleNamespace(
        entry_id=repair.decision_entry_id,
        binding={"cycle_id": decided_cycle} if decided_cycle else {},
    )

    async def control_log(_campaign_id):
        return [row]

    w.campaigns.control_log = control_log
    return repair


async def test_a_repair_carries_the_instructions_given_to_carry_and_only_those(world):  # noqa: F811
    records = InMemoryMemoryRecords()
    project = "group_run"
    await records.create(_instruction("mrec_carry", carries=True))
    await records.create(_instruction("mrec_stay", carries=False))
    gone = _instruction("mrec_gone", carries=True)
    await records.create(gone)
    change = withdrawn(gone, by="ada", at=T0, why="superseded").status_changes[-1]
    await records.append_status("mrec_gone", change)
    intent = await _repair_intent(world)

    cycle = await _service(world, records)._build_cycle(intent)

    copies = [r for r in await records.list_project(cycle.project_id)
              if r.current.target.cycle_id == cycle.cycle_id]  # fmt: skip
    [copy] = copies
    assert cycle.project_id == project
    assert copy.current.source.ids["carried_from"] == "mrec_carry"
    assert copy.current.target.carries_into == "continuations"
    assert copy.record_id != "mrec_carry"
    assert not is_intervention(copy)


async def test_a_launch_that_continues_nothing_carries_nothing(world):  # noqa: F811
    records = InMemoryMemoryRecords()
    await records.create(_instruction("mrec_carry", carries=True))
    world.start()
    [intent] = await world.campaigns.launch_intents("cmp_start0000001")

    cycle = await _service(world, records)._build_cycle(intent)

    assert [r for r in await records.list_project(cycle.project_id)
            if r.current.target.cycle_id == cycle.cycle_id] == []  # fmt: skip


async def test_a_repair_whose_deciding_row_names_no_cycle_is_a_fault(world):  # noqa: F811
    """Bug caught: the launch going ahead with no carried instruction because it couldn't tell
    which cycle it continues."""
    intent = await _repair_intent(world, decided_cycle=None)

    with pytest.raises(RuntimeError, match="names no cycle it continues"):
        await _service(world, InMemoryMemoryRecords())._build_cycle(intent)
