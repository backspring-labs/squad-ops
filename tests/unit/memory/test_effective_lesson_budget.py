"""The effective lesson budget (SIP-0110 Appendix A §3.6, T17; #2179 stage 2): the lessons take the smaller of
the snapshot's budget and what the binding sections leave after the lesson slot's framing, in recall's one
selection pass, each omission naming its limit, nothing trimmed after."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from squadops.memory.lessons import RecallDisposition, recall
from tests.unit.memory.test_lessons import ASK, T0, _approve, _revision, _snapshot

pytestmark = [pytest.mark.domain_memory]


def _two_lessons():
    """§A.5 T17's two eligible lessons, of 260 and 280 tokens (four characters a token), the 260
    approved first."""
    small = _revision("behavior_small", text="s" * (260 * 4))
    large = _revision("behavior_large", text="l" * (280 * 4))
    approvals = [_approve(small, at=T0), _approve(large, at=T0 + timedelta(minutes=1))]
    return small, large, _snapshot([small, large], approvals)


def test_t17_the_effective_budget_is_what_the_binding_sections_leave_and_the_rest_is_omitted_whole():
    """T17 as §A.5 states it. Bug caught: the 280-token lesson cut to fit, supplied past what the
    binding sections left, or omitted as ``budget`` when only the remaining room omitted it."""
    small, large, snapshot = _two_lessons()

    got = recall(snapshot, dataclasses.replace(ASK, available_lesson_tokens=300))

    assert [e.revision.revision_id for e in got.supplied] == [small.revision_id]
    assert got.omitted == ((large.revision_id, "remaining"),)
    assert got.lesson_budget == {"effective": 300, "snapshot": 600, "remaining": 300}
    assert got.exposure()["lesson_budget"] == {"effective": 300, "snapshot": 600, "remaining": 300}


@pytest.mark.parametrize("available", [600, 10_000])
def test_t17_with_room_for_the_snapshots_budget_the_lessons_are_todays_recall(available):
    """Bug caught: an instruction's presence changing which lessons a task receives when it left the
    snapshot's whole budget free."""
    _, _, snapshot = _two_lessons()

    today = recall(snapshot, ASK)
    bounded = recall(snapshot, dataclasses.replace(ASK, available_lesson_tokens=available))

    assert (bounded.supplied, bounded.omitted) == (today.supplied, today.omitted)
    assert today.lesson_budget is None and "lesson_budget" not in today.exposure()


def test_t17_less_room_than_the_framing_omits_the_section_whole_and_the_task_runs():
    """Bug caught: a negative leftover read as unlimited, or a lesson squeezed into a prompt that
    has no room for even its slot's heading."""
    small, large, snapshot = _two_lessons()

    got = recall(snapshot, dataclasses.replace(ASK, available_lesson_tokens=-5))

    assert got.supplied == ()
    assert got.omitted == ((small.revision_id, "remaining"), (large.revision_id, "remaining"))
    assert got.disposition is RecallDisposition.OMITTED_BY_BUDGET
    assert got.lesson_budget["effective"] == 0


@pytest.mark.parametrize(
    ("sizes", "available", "labels"),
    [
        ((280, 290, 310), 300, ("remaining", "budget")),
        ((164, 392, 104, 142, 26), 482, ("remaining", "remaining")),
    ],
    ids=["today-omits-the-310-too", "the-26-is-displaced"],
)
def test_each_omission_is_named_against_todays_recall(sizes, available, labels):
    """The second read of PR #2526. Bug caught: a label decided inside the bounded pass: the 310,
    which today's recall omits for its own budget, blamed on the instructions; or the 26, which
    today's recall supplies and the instructions displaced, reported as the snapshot's cap."""
    revisions = [_revision(f"behavior_{n}", text="t" * (size * 4)) for n, size in enumerate(sizes)]
    approvals = [_approve(r, at=T0 + timedelta(minutes=n)) for n, r in enumerate(revisions)]
    snapshot = _snapshot(revisions, approvals)

    got = recall(snapshot, dataclasses.replace(ASK, available_lesson_tokens=available))

    # Today's recall: (280, 290) supplied, 310 omitted by its own budget; (164, 392, 26) supplied,
    # 104 and 142 omitted. So the second and last lessons' labels say which pass left them out.
    named = dict(got.omitted)
    assert (named[revisions[1].revision_id], named[revisions[-1].revision_id]) == labels


def test_an_omission_the_snapshots_own_budget_makes_is_budget_even_when_room_is_short_too():
    """§3.6's naming rule. Bug caught: a lesson the snapshot itself could never fit reported as
    crowded out by the instructions, so the instructions are blamed for a cap they didn't set."""
    huge = _revision("behavior_huge", text="h" * (700 * 4))
    snapshot = _snapshot([huge], [_approve(huge)])

    got = recall(snapshot, dataclasses.replace(ASK, available_lesson_tokens=100))

    assert got.omitted == ((huge.revision_id, "budget"),)


async def test_the_composer_hands_recall_what_the_binding_sections_leave_and_nothing_without_them():
    """The wiring, at ``supply_lessons``: with a project instruction pinned, recall is asked with the
    budget less both binding sections and the lesson slot's framing; with none, it is asked exactly
    as before (``None``). Bug caught: the leftover never reaching recall, or reaching it on every
    task, so a deploy with no instruction recalls differently from today."""
    from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
    from adapters.memory.records import InMemoryMemoryRecords
    from squadops.capabilities import lesson_supply
    from squadops.capabilities.lesson_supply import supply_lessons, unit_of
    from squadops.capabilities.prompt_budget import prompt_budget
    from squadops.memory.lessons import UnitKind
    from squadops.memory.pinning import pin_unit
    from tests.unit.cycles.test_failure_recall import _framing_cycle, _plan
    from tests.unit.memory.test_project_instructions import _instruction

    class Asked:
        def __init__(self, inner):
            self.inner, self.queries = inner, []

        async def recall(self, query):
            self.queries.append(query)
            return await self.inner.recall(query)

        def __getattr__(self, name):
            return getattr(self.inner, name)

    from adapters.memory.recall import SnapshotRecall

    async def asked(records):
        store = InMemoryCrossCycleMemoryStore()
        cycle = _framing_cycle()
        await pin_unit(store, unit_kind=UnitKind.CYCLE, unit_id=cycle.cycle_id, project_id="group_run",
                       pinned_at=T0, disabled=False, records=records)  # fmt: skip
        recall_port = Asked(SnapshotRecall(store, records=records))
        plan = _plan(cycle)
        await supply_lessons(plan, recall=recall_port, unit=unit_of(cycle),
                             stack="fullstack_fastapi_react", run_id="run_t17", now=T0)  # fmt: skip
        return plan, recall_port.queries

    with_one = InMemoryMemoryRecords()
    await with_one.create(_instruction("mrec_t17", "development.design_plan", text="x" * 400))
    plan, queries = await asked(with_one)
    _, none_queries = await asked(InMemoryMemoryRecords())

    design = next(e for e in plan if str(e.task_type) == "development.design_plan")
    expected = (
        prompt_budget(design)
        - (lesson_supply._framing(lesson_supply._PROJECT_SLOT) + 100)
        - lesson_supply._framing(lesson_supply._LESSON_SLOT)
    )
    by_task = {q.task_type: q.available_lesson_tokens for q in queries}
    assert by_task["development.design_plan"] == expected
    assert {t: a for t, a in by_task.items() if t != "development.design_plan"} == {
        t: None for t in by_task if t != "development.design_plan"
    }
    assert {q.available_lesson_tokens for q in none_queries} == {None}
