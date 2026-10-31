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
from squadops.campaigns.models import ControlOperation, CycleKind
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


async def _repair_intent(w, *, continues: str | None = CONTINUED, decided: str | None = None):
    """The calibration intent a start writes, as the repair the owner's word launches: its
    request names the cycle it continues, as a repair's or a retry's does (``_bound_launch``), and
    its deciding row is a ``resume``, whose binding names no cycle (``owner_action``). ``decided``
    puts a decision for that cycle before the resume, as the owner's word follows one."""
    w.start()
    [intent] = await w.campaigns.launch_intents("cmp_start0000001")
    body = intent.cycle_request["body"]
    overrides = dict(body.get("execution_overrides") or {})
    block = dict(overrides.get("campaign_proposal") or {})
    # A repair's block carries its increment's proposal id (``CONTINUED_KEYS``), which the
    # launcher reads as the cycle's increment (#2578 part 2).
    block["proposal_id"] = "prop_carried0001"
    if continues:
        block["continues"] = continues
    overrides["campaign_proposal"] = block
    request = {**intent.cycle_request, "body": {**body, "execution_overrides": overrides}}
    resume = SimpleNamespace(
        entry_id="ctl_resume", operation=ControlOperation.RESUME, target=None,
        binding={"action": "repair", "executes": "held"},
    )  # fmt: skip
    decision = SimpleNamespace(
        entry_id="ctl_decide", operation=ControlOperation.DECIDE, target=decided,
        binding={"cycle_id": decided, "action": "escalate"},
    )  # fmt: skip
    log = w.campaigns.control_log

    async def control_log(campaign_id):
        return [*await log(campaign_id), *([decision] if decided else []), resume]

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


async def test_a_repair_written_before_its_request_named_the_cycle_reads_it_from_its_log(world):  # noqa: F811
    """The third read of PR #2556. Bug caught: an owner-resumed repair or retry pending across the
    deploy refused for good, though the decision the owner's word executed names its cycle."""
    records = InMemoryMemoryRecords()
    await records.create(_instruction("mrec_carry", carries=True))
    intent = await _repair_intent(world, continues=None, decided=CONTINUED)

    cycle = await _service(world, records)._build_cycle(intent)

    [copy] = [r for r in await records.list_project("group_run")
              if r.current.target.cycle_id == cycle.cycle_id]  # fmt: skip
    assert copy.current.source.ids["carried_from"] == "mrec_carry"


async def test_a_repair_naming_no_cycle_it_continues_is_refused_not_a_fault(world):  # noqa: F811
    """The second read of PR #2556. Bugs caught: the launch going ahead with no carried
    instruction because it couldn't tell which cycle it continues; or a fault, which every drain
    repeats, holding every intent queued behind it while no row says why. A refusal escalates."""
    intent = await _repair_intent(world, continues=None)

    with pytest.raises(LaunchRefused, match="names no cycle it continues"):
        await _service(world, InMemoryMemoryRecords())._build_cycle(intent)


def _resolving(w, records, resolver):
    service = _service(w, records)
    service._creation = dataclasses.replace(
        service._creation, reference_resolvers={"fake": resolver}
    )
    return service


async def test_a_carried_reference_is_bound_again_for_the_continuation(world):  # noqa: F811
    """T16's task part, §3.7: "the new cycle's admission records its own binding". Bugs caught: the
    copy keeping the revision its original's cycle bound, so a repair reads a target revised since;
    a carry whose reference won't bind for the continuation launched without it, rather than
    refused for the supervisor."""
    from squadops.memory.records import Reference
    from tests.unit.memory.test_reference_binding import _Resolver

    records = InMemoryMemoryRecords()
    original = _instruction("mrec_carry", carries=True)
    bound = Reference("fake:doc:spec@r1", True, digest="sha256:r1", written="fake:doc:spec@current")
    original = dataclasses.replace(
        original, revisions=(dataclasses.replace(original.current, references=(bound,)),)
    )
    await records.create(original)
    resolver = _Resolver()
    resolver.revision = "r2"  # the target was revised after the original's cycle bound it
    intent = await _repair_intent(world)

    cycle = await _resolving(world, records, resolver)._build_cycle(intent)

    [copy] = [r for r in await records.list_project("group_run")
              if r.current.target.cycle_id == cycle.cycle_id]  # fmt: skip
    [reference] = copy.current.references
    assert (reference.ref, reference.digest, reference.written) == (
        "fake:doc:spec@r2", "sha256:r2", "fake:doc:spec@current",
    )  # fmt: skip
    assert [c.unit_id for c in resolver.seen] == [cycle.cycle_id]

    resolver.refuse = "the document was deleted"
    with pytest.raises(LaunchRefused, match="the document was deleted"):
        await _resolving(world, records, resolver)._build_cycle(await _repair_intent(world))
