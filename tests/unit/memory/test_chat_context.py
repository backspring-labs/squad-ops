"""A chat turn's memory context and its capture rules (SIP-0110 Appendix A §3.3–§3.6, §3.10; #2180
stage A): what a turn may hold, how it is bounded, and what a capture card may offer. The routes'
wiring is ``tests/unit/api/test_chat_memory_routes.py``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from adapters.memory.records import InMemoryMemoryRecords
from squadops.auth.models import Scope
from squadops.memory.chat import (
    ChatLimits,
    Loaded,
    capture_choices,
    chat_context,
    memory_lines,
    proposed_capture,
)
from squadops.memory.context import ChatTurn, Disposition, SectionKind
from squadops.memory.records import (
    InstructionApplicability,
    Revision,
    Source,
    TaskTarget,
    new_record,
    withdrawn,
)

pytestmark = [pytest.mark.domain_memory]

T0 = datetime(2026, 10, 19, tzinfo=UTC)
CYCLE = "cyc_0123456789ab"


def _record(record_id, kind, scope, body, *, owner="ada", project="group_run", at=T0, **rev):
    return new_record(
        record_id=record_id, kind=kind, scope=scope,
        project_id=None if scope == "user" else project, owner_id=owner,
        revision=Revision(
            number=1, body=body, author=owner, created_at=at, source=Source("api_call"),
            confirmed_by=owner if kind == "instruction" else None, **rev,
        ),
    )  # fmt: skip


def _turn(text="what do we know about the join?", scopes=(Scope.MEMORY_READ,)):
    return ChatTurn("s1", "m1", "ada", "comms-agent", text=text, viewer_scopes=frozenset(scopes))


def _sections(sections):
    return {s.kind: s for s in sections}


def test_a_turn_fills_instructions_first_and_leaves_a_record_out_whole_naming_the_limit():
    """§3.6's chat budget. Bug caught: a note cut mid-text to fit, the instructions crowded out by
    notes, an omission with no limit named, or a count bound read as a token one."""
    instruction = _record("mrec_i", "instruction", "project", "x" * 400,
                          applicability=InstructionApplicability(("*",), ("*",), ("*",)))  # fmt: skip
    preference = _record("mrec_pref", "preference", "user", "answer briefly")
    notes = [_record(f"mrec_n{i}", "note", "user", f"note {i}") for i in range(3)]
    big = _record("mrec_big", "note", "user", "y" * 400)

    sections, handed = chat_context(
        turn=_turn(),
        project_id="group_run",
        reads={
            SectionKind.PROJECT_INSTRUCTIONS: Loaded((instruction,)),
            SectionKind.TASK_INSTRUCTIONS: Loaded((instruction,)),
            SectionKind.PREFERENCES: Loaded((preference,)),
            SectionKind.NOTES: Loaded((big, *notes)),
        },
        limits=ChatLimits(max_notes=2, max_tokens=110),
    )

    by_kind = _sections(sections)
    assert [r.record_id for r in by_kind[SectionKind.PROJECT_INSTRUCTIONS].supplied] == ["mrec_i"]
    assert [r.record_id for r in by_kind[SectionKind.PREFERENCES].supplied] == ["mrec_pref"]
    assert [r.record_id for r in by_kind[SectionKind.NOTES].supplied] == ["mrec_n0", "mrec_n1"]
    assert [(r.record_id, why) for r, why in by_kind[SectionKind.NOTES].omitted] == [
        ("mrec_big", "budget"), ("mrec_n2", "count"),
    ]  # fmt: skip
    assert by_kind[SectionKind.LESSONS].disposition is Disposition.NOT_APPLICABLE
    [notes_handed] = [s for s in handed["sections"] if s["kind"] == "notes"]
    assert ([e["text"] for e in notes_handed["entries"]], notes_handed["omitted"]) == (
        ["note 0", "note 1"], 2,
    )  # fmt: skip


def test_an_unbound_turn_sees_only_its_owners_records_and_a_bound_one_only_its_project():
    """T4. Bug caught: another person's private note, another project's note or instruction, or a
    project's records on an unbound session reaching the agent."""
    mine = _record("mrec_mine", "note", "user", "mine")
    theirs = _record("mrec_theirs", "note", "user", "theirs", owner="bo")
    project = _record("mrec_p1", "note", "project", "p1 note")
    other = _record("mrec_p2", "note", "project", "p2 note", project="play_game")
    reads = {
        SectionKind.PROJECT_INSTRUCTIONS: Loaded(()),
        SectionKind.TASK_INSTRUCTIONS: Loaded(()),
        SectionKind.PREFERENCES: Loaded(()),
        SectionKind.NOTES: Loaded((mine, theirs, project, other)),
    }
    limits = ChatLimits(max_notes=8, max_tokens=1500)

    bound, _ = chat_context(turn=_turn(), project_id="group_run", reads=reads, limits=limits)
    unbound, _ = chat_context(turn=_turn(), project_id=None, reads=reads, limits=limits)

    assert [r.record_id for r in _sections(bound)[SectionKind.NOTES].supplied] == [
        "mrec_mine", "mrec_p1",
    ]  # fmt: skip
    assert [r.record_id for r in _sections(unbound)[SectionKind.NOTES].supplied] == ["mrec_mine"]
    assert _sections(unbound)[SectionKind.PROJECT_INSTRUCTIONS].disposition is (
        Disposition.NOT_APPLICABLE
    )


def test_task_instructions_reach_a_turn_only_for_the_cycles_it_names():
    """§3.5. Bug caught: every cycle's task instructions shown on every turn, or a named cycle's
    missed because its id sits mid-sentence."""
    named = _record("mrec_t", "instruction", "task", "keep the join idempotent",
                    target=TaskTarget(CYCLE, ("qa.test",)))  # fmt: skip
    unnamed = _record("mrec_u", "instruction", "task", "other",
                      target=TaskTarget("cyc_ffffffffffff", ("qa.test",)))  # fmt: skip
    reads = {k: Loaded((named, unnamed)) for k in SectionKind if k is not SectionKind.LESSONS}

    sections, handed = chat_context(
        turn=_turn(f"why did {CYCLE}'s qa fail?"),
        project_id="group_run",
        reads=reads,
        limits=ChatLimits(max_notes=8, max_tokens=1500),
    )

    assert [r.record_id for r in _sections(sections)[SectionKind.TASK_INSTRUCTIONS].supplied] == [
        "mrec_t"
    ]
    assert "cyc_0123456789ab, qa.test: keep the join idempotent" in memory_lines(handed)


def test_a_read_that_failed_is_failed_and_says_so_never_none():
    """T8's chat part. Bug caught: a store failure reading as "you have no notes", so the agent
    answers as if nothing were recorded."""
    sections, handed = chat_context(
        turn=_turn(),
        project_id=None,
        reads={
            SectionKind.PREFERENCES: Loaded(()),
            SectionKind.NOTES: Loaded(failure="ConnectionError: down"),
        },
        limits=ChatLimits(max_notes=8, max_tokens=1500),
    )

    assert _sections(sections)[SectionKind.NOTES].disposition is Disposition.FAILED
    assert handed["unavailable"] == ["notes"]
    assert "Couldn't be read for this turn: notes" in memory_lines(handed)


@pytest.mark.parametrize(
    ("reply", "proposed", "shown"),
    [
        ('Sure.\n<memory-capture>{"text": "mock the clock", "kind": "note"}</memory-capture>',
         ("mock the clock", "note", "user"), "Sure."),
        ('<memory-capture>{"text": "brief", "kind": "preference", "scope": "user"}</memory-capture>',
         ("brief", "preference", "user"), ""),
        ('Ok <memory-capture>{"text": "x", "kind": "instruction"}</memory-capture>',
         ("x", "instruction", "project"), "Ok"),
        ('Ok <memory-capture>{"text": "x", "kind": "instruction", "scope": "task"}</memory-capture>',
         ("x", "instruction", "task"), "Ok"),
        ('Ok <memory-capture>{"text": "x", "kind": "note", "scope": ["user"]}</memory-capture>', None, "Ok"),
        ("Ok <memory-capture>not json</memory-capture>", None, "Ok"),
        ('<memory-capture>{"text": "", "kind": "note"}</memory-capture>Done', None, "Done"),
        ("No capture here.", None, "No capture here."),
    ],
    ids=["a-note", "a-preference", "a-project-instruction", "a-task-instruction",
         "a-scope-that-isnt-a-string",
         "malformed", "empty", "none"],
)  # fmt: skip
def test_a_reply_proposes_at_most_one_well_formed_capture_and_never_shows_the_block(
    reply, proposed, shown
):
    """Bug caught: an instruction captured from chat before stage B, a malformed block shown to the
    person or proposing garbage, or the block left in the stored reply."""
    proposal, text = proposed_capture(reply)

    assert (
        None if proposal is None else (proposal.text, proposal.kind, proposal.scope)
    ) == proposed
    assert text == shown


@pytest.mark.parametrize(
    ("scopes", "project_id", "offered"),
    [
        ((Scope.MEMORY_READ,), None, {("note", "user"), ("preference", "user")}),
        ((Scope.MEMORY_READ,), "group_run", {("note", "user"), ("preference", "user")}),
        ((Scope.MEMORY_NOTE,), None, {("note", "user"), ("preference", "user")}),
        ((Scope.MEMORY_NOTE,), "group_run", {("note", "user"), ("preference", "user"), ("note", "project")}),
    ],
    ids=["a-reader", "a-reader-bound", "a-noter-unbound", "a-noter-bound"],
)  # fmt: skip
def test_a_card_offers_only_what_the_person_may_write_in_this_session(scopes, project_id, offered):
    """§3.3. Bug caught: a project note offered to someone without ``memory:note``, or on an
    unbound session, which has no project to write it to."""
    choices = capture_choices(scopes=scopes, project_id=project_id)

    assert {(c.kind, c.scope) for c in choices} == offered


async def test_the_note_search_filters_before_it_ranks_then_orders_by_match_and_recency():
    """§3.10 on the memory twin (the Postgres query is the integration test's). Bug caught: a
    withdrawn or another project's note returned, or an older match outranked by a newer miss."""
    records = InMemoryMemoryRecords()
    for record in (
        _record("mrec_old", "note", "user", "the join stays idempotent"),
        _record("mrec_new", "note", "user", "the join checks capacity", at=T0 + timedelta(hours=1)),
        _record("mrec_miss", "note", "user", "unrelated", at=T0 + timedelta(hours=2)),
        _record("mrec_p2", "note", "project", "the join", project="play_game"),
        _record("mrec_gone", "note", "user", "a withdrawn join"),
    ):
        await records.create(record)
    gone = withdrawn(await records.get("mrec_gone"), by="ada", at=T0, why="wrong")
    await records.append_status("mrec_gone", gone.status_changes[-1])

    found = await records.search_notes(owner_id="ada", project_id="group_run", text="join")

    assert [r.record_id for r in found] == ["mrec_new", "mrec_old", "mrec_miss"]


def _lessons(*, revoked=False, failure=None, texts=("Name the manifest element.",)):
    from squadops.memory.chat import LessonsLoaded
    from tests.unit.memory.test_lessons import _approve, _revision

    revisions = tuple(_revision(f"behavior_{n}", text=t) for n, t in enumerate(texts))
    approvals = tuple(
        _approve(r, revoked_at=T0 if revoked and n == 0 else None, ruling="the owner, 10-19")
        for n, r in enumerate(revisions)
    )
    return revisions, LessonsLoaded(revisions, approvals, failure=failure)


def test_a_turn_that_asks_about_lessons_inspects_the_approved_ones_and_is_never_guided_by_them():
    """#2181. Bug caught: a revoked lesson shown as approved, a lesson the turn names buried after
    the others, its evidence or approval missing, or the lesson section a task holds reaching chat."""
    revisions, lessons = _lessons(revoked=True, texts=("revoked one", "kept one", "named one"))
    named = revisions[2].revision_id

    sections, handed = chat_context(
        turn=_turn(f"why does {named} exist, and what other lessons are there?"),
        project_id="group_run",
        reads={},
        limits=ChatLimits(max_notes=8, max_tokens=1500),
        lessons=lessons,
    )

    inspected = _sections(sections)[SectionKind.INSPECTED_LESSONS]
    assert [r.record_id + "@" + r.revision for r in inspected.supplied] == [
        named, revisions[1].revision_id,
    ]  # fmt: skip
    assert _sections(sections)[SectionKind.LESSONS].disposition is Disposition.NOT_APPLICABLE
    [section] = [s for s in handed["sections"] if s["kind"] == "inspected_lessons"]
    first = section["entries"][0]
    assert (first["text"], first["cited_observations"], first["approval"]["ruling"]) == (
        "named one", ["proposal_ruling:cmp_c4b81554bd59:e14"], "the owner, 10-19",
    )  # fmt: skip
    assert f"1. {named}, for behavior_2: named one" in memory_lines(handed)


@pytest.mark.parametrize(
    ("project_id", "loaded", "disposition"),
    [
        (None, "loaded", Disposition.NOT_APPLICABLE),
        ("group_run", None, Disposition.NOT_APPLICABLE),
        ("group_run", "failed", Disposition.FAILED),
    ],
    ids=["unbound", "didnt-ask", "the-read-failed"],
)
def test_lessons_are_inspected_only_on_a_bound_turn_that_asked(project_id, loaded, disposition):
    """Bug caught: an unbound session inspecting a project's lessons, or a failed read shown as a
    project with no lessons."""
    _, lessons = _lessons(failure="ConnectionError: down" if loaded == "failed" else None)

    sections, _ = chat_context(
        turn=_turn("which lessons apply?"),
        project_id=project_id,
        reads={},
        limits=ChatLimits(max_notes=8, max_tokens=1500),
        lessons=None if loaded is None else lessons,
    )

    assert _sections(sections)[SectionKind.INSPECTED_LESSONS].disposition is disposition


@pytest.mark.parametrize(
    "applicability",
    ['"qa.test"', '{"task_types": "qa.test"}', '{"task_type": ["qa.test"]}', "null"],
    ids=["a-string", "a-field-as-a-string", "a-misspelled-field", "none"],
)
def test_a_malformed_or_missing_applicability_is_proposed_blank_never_as_any(applicability):
    """The second read of PR #2525. Bug caught: an agent's malformed applicability read as ``*`` in
    every field, so the card offered "applies to every task" (§A.3.2: an unknown never means
    everywhere)."""
    proposal, _ = proposed_capture(
        f'<memory-capture>{{"text": "x", "kind": "instruction", "applicability": {applicability}}}'
        "</memory-capture>"
    )

    assert proposal.applicability == {"task_types": (), "roles": (), "stacks": ()}
