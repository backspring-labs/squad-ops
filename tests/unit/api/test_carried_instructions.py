"""A task instruction given with ``carries_into: continuations`` reaches a campaign's repair or retry of
its cycle (SIP-0110 Appendix A §3.7, T12; #2178), entered where the launcher builds that cycle
(``CampaignLaunchService._build_cycle``) from the repair the owner's word launches: its request names
the cycle it continues, and its deciding row (a ``resume``) names none.

What bugs would these catch? A continuation that inherits every instruction of the cycle it repairs,
or another cycle's, or none of the ones given to carry; a withdrawn one carried; the copy not linked
to its original, so withdrawing one withdraws both, or neither can be told apart; a copy read as an
intervention, or losing the lesson it applies; a launch that isn't a continuation carrying anything;
one naming nothing it continues faulting every drain.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from adapters.memory.records import InMemoryMemoryRecords
from squadops.campaigns.launcher import LaunchRefused
from squadops.campaigns.models import CycleKind
from squadops.memory.records import (
    LESSON_CITED,
    Revision,
    Source,
    TaskTarget,
    new_record,
    withdrawn,
)
from squadops.memory.task_instructions import is_intervention
from tests.unit.api.test_campaign_start import _sandbox_provider, world  # noqa: F401
from tests.unit.api.test_launch_instructions import _service
from tests.unit.memory.test_project_instructions import T0

pytestmark = pytest.mark.auth

CONTINUED = "cyc_continued00"


def _instruction(record_id: str, carries: bool, cycle: str = CONTINUED, lesson: str | None = None):
    return new_record(
        record_id=record_id, kind="instruction", scope="task", project_id="group_run",
        owner_id="ada",
        revision=Revision(
            number=1, body=f"text of {record_id}", author="ada", created_at=T0,
            source=Source("api_call", {LESSON_CITED: lesson} if lesson else {}), confirmed_by="ada",
            target=TaskTarget(cycle, ("development.develop",),
                              "continuations" if carries else None),
        ),
    )  # fmt: skip


async def _repair_intent(w, *, continues: str | None = CONTINUED):
    """The calibration intent a start writes, as the repair the owner's word launches: its
    request names the cycle it continues, as a repair's or a retry's does (``_bound_launch``), and
    its deciding row is a ``resume``, whose binding names no cycle (``owner_action``)."""
    w.start()
    [intent] = await w.campaigns.launch_intents("cmp_start0000001")
    body = intent.cycle_request["body"]
    overrides = dict(body.get("execution_overrides") or {})
    block = dict(overrides.get("campaign_proposal") or {})
    if continues:
        block["continues"] = continues
    overrides["campaign_proposal"] = block
    request = {**intent.cycle_request, "body": {**body, "execution_overrides": overrides}}
    resume = SimpleNamespace(
        entry_id="ctl_resume", binding={"action": "repair", "executes": "held"}
    )
    log = w.campaigns.control_log

    async def control_log(campaign_id):
        return [*await log(campaign_id), resume]

    w.campaigns.control_log = control_log
    return dataclasses.replace(
        intent, cycle_kind=CycleKind.REPAIR, decision_entry_id="ctl_resume", cycle_request=request
    )


async def test_a_repair_carries_the_instructions_given_to_carry_and_only_those(world):  # noqa: F811
    records = InMemoryMemoryRecords()
    project = "group_run"
    await records.create(_instruction("mrec_carry", carries=True, lesson="les_1@2"))
    await records.create(_instruction("mrec_stay", carries=False))
    await records.create(_instruction("mrec_elsewhere", carries=True, cycle="cyc_unrelated00"))
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
    assert copy.current.source.ids[LESSON_CITED] == "les_1@2"  # its provenance kept
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


async def test_a_repair_naming_no_cycle_it_continues_is_refused_not_a_fault(world):  # noqa: F811
    """The second read of PR #2556. Bugs caught: the launch going ahead with no carried
    instruction because it couldn't tell which cycle it continues; or a fault, which every drain
    repeats, holding every intent queued behind it while no row says why. A refusal escalates."""
    intent = await _repair_intent(world, continues=None)

    with pytest.raises(LaunchRefused, match="names no cycle it continues"):
        await _service(world, InMemoryMemoryRecords())._build_cycle(intent)
