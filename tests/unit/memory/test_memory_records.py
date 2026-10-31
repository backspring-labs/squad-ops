"""The typed memory records' rules (SIP-0110 Appendix A, §A.3.2–§A.3.4, §A.3.8; #2177)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.memory.records import InMemoryMemoryRecords
from squadops.auth.models import Scope
from squadops.memory.records import (
    InstructionApplicability,
    NotPermitted,
    RecordRefused,
    RecordStatus,
    Reference,
    Revision,
    Source,
    TaskTarget,
    authorize_write,
    new_record,
    reference_of,
    retrieved,
    revised,
    revision_document,
    revision_from_document,
    shown_source,
    withdrawn,
)
from squadops.ports.memory.records import RecordConflict

T0 = datetime(2026, 10, 19, tzinfo=UTC)
API = Source("api_call")
ANYWHERE = InstructionApplicability(("*",), ("*",), ("*",))


def _revision(body: str = "keep the join idempotent", source: Source = API, **change) -> Revision:
    return Revision(number=1, body=body, author="ada", created_at=T0, source=source, **change)


def _record(record_id: str, kind: str, scope: str, project: str | None, owner: str = "ada", **rev):
    return new_record(
        record_id=record_id, kind=kind, scope=scope, project_id=project, owner_id=owner,
        revision=_revision(**rev),
    )  # fmt: skip


@pytest.mark.parametrize(
    ("kind", "scope", "actor", "scopes", "campaign", "refused"),
    [
        ("note", "user", "ada", (), False, None),
        ("note", "user", "bo", (Scope.MEMORY_NOTE, Scope.MEMORY_INSTRUCT), False, "its owner"),
        ("preference", "user", "ada", (), False, None),
        ("note", "project", "ada", (Scope.MEMORY_NOTE,), False, None),
        ("note", "project", "ada", (Scope.MEMORY_READ,), False, "memory:note"),
        ("instruction", "project", "ada", (Scope.MEMORY_INSTRUCT,), False, None),
        ("instruction", "project", "ada", (Scope.MEMORY_NOTE,), False, "memory:instruct"),
        ("instruction", "task", "ada", (Scope.CYCLES_WRITE,), False, None),
        ("instruction", "task", "ada", (Scope.CYCLES_WRITE,), True, "campaigns:supervise"),
        ("instruction", "task", "ada", (Scope.CAMPAIGNS_SUPERVISE,), True, None),
    ],
    ids=[
        "own-private-note", "anothers-private-note", "own-preference", "project-note",
        "project-note-without-memory-note", "project-instruction",
        "project-instruction-with-only-memory-note", "standalone-task-instruction",
        "campaign-task-instruction-with-cycles-write", "campaign-task-instruction",
    ],
)  # fmt: skip
def test_who_may_write_each_kind_and_scope(kind, scope, actor, scopes, campaign, refused):
    """§A.3.3's table. Bug caught: an admin writing someone's private note, a project note
    written with read access, or a campaign's task directed by anyone who may write cycles."""
    write = lambda: authorize_write(  # noqa: E731
        kind, scope, actor_id=actor, actor_scopes=scopes, owner_id="ada", campaign_cycle=campaign
    )
    if refused is None:
        write()
    else:
        with pytest.raises(NotPermitted, match=refused):
            write()


def test_a_query_answers_only_with_what_its_binding_may_read():
    """T4. Bug caught: P2's records answering a P1 query, one person's private note reaching
    another, or an unbound query reaching any project's records."""
    records = [
        _record("p1-note", "note", "project", "p1"),
        _record("p2-note", "note", "project", "p2"),
        _record("ada-private", "note", "user", None, owner="ada"),
        _record("bo-private", "note", "user", None, owner="bo"),
    ]
    reader = {Scope.MEMORY_READ}

    def ids(viewer, scopes, project):
        found = retrieved(records, viewer_id=viewer, viewer_scopes=scopes, project_id=project)
        return sorted(r.record_id for r in found)

    assert ids("ada", reader, "p1") == ["ada-private", "p1-note"]
    assert ids("bo", reader, "p1") == ["bo-private", "p1-note"]
    assert ids("ada", reader, None) == ["ada-private"]
    assert ids("ada", set(), "p1") == ["ada-private"]


def test_a_correction_keeps_every_revision_and_a_withdrawal_stops_retrieval():
    """§A.3.8. Bug caught: a correction that rewrites the record, so an exposure that used
    revision 1 can no longer find what it used; or a withdrawn record still retrieved."""
    note = _record("n", "note", "project", "p1")
    note = revised(note, _revision("keep the join idempotent, and say why"))
    note = withdrawn(note, by="ada", at=T0, why="superseded by an instruction")

    assert [(r.number, r.supersedes) for r in note.revisions] == [(1, None), (2, 1)]
    assert note.revisions[0].body == "keep the join idempotent"
    assert note.status == RecordStatus.WITHDRAWN
    assert (
        retrieved([note], viewer_id="ada", viewer_scopes={Scope.MEMORY_READ}, project_id="p1") == []
    )
    with pytest.raises(RecordRefused, match="withdrawn"):
        revised(note, _revision("again"))
    with pytest.raises(RecordRefused, match="already withdrawn"):
        withdrawn(note, by="ada", at=T0, why="twice")


@pytest.mark.parametrize(
    ("kind", "scope", "project", "change", "refused"),
    [
        ("preference", "project", "p1", {}, "takes scope"),
        ("note", "task", "p1", {}, "takes scope"),
        ("note", "project", None, {}, "names its project"),
        ("note", "project", "p1", {"applicability": ANYWHERE}, "reaches no task"),
        ("preference", "user", None, {"suggestion": True}, "a note marked as a claim"),
        ("instruction", "project", "p1", {"confirmed_by": "ada"}, "names its applicability"),
        ("instruction", "project", "p1", {"applicability": ANYWHERE}, "is confirmed"),
        ("instruction", "task", "p1", {"confirmed_by": "ada"}, "names its target"),
        ("note", "user", None, {"body": "  "}, "body is empty"),
    ],
    ids=["preference-in-a-project", "note-on-a-task", "project-note-without-project",
         "note-with-applicability", "suggestion-not-a-note", "instruction-without-applicability",
         "instruction-unconfirmed", "task-instruction-without-target", "empty-body"],
)  # fmt: skip
def test_a_record_that_breaks_the_kinds_rules_is_refused(kind, scope, project, change, refused):
    """§A.3.2. Bug caught: a note reaching a task through an applicability, an unconfirmed
    instruction binding the work, or a task instruction with nothing to bind to."""
    with pytest.raises(RecordRefused, match=refused):
        _record("r", kind, scope, project, **change)


def test_a_reference_is_kept_as_a_reference_and_a_copy_is_refused_naming_the_change_path():
    """§A.3.2. Bug caught: memory storing an authoritative decision's content, a second copy
    that drifts from the manifest, or a malformed reference stored as though it named one."""
    kept = reference_of({"ref": "manifest:decision:join-is-idempotent@3", "required": True})
    assert kept == Reference("manifest:decision:join-is-idempotent@3", True)
    with pytest.raises(RecordRefused, match=r"never a copy.*operator edit \(SIP-0103"):
        reference_of({"ref": "manifest:decision:join@3", "content": "joins are not idempotent"})
    with pytest.raises(RecordRefused, match="<family>:<kind>:<id>@<revision>"):
        reference_of({"ref": "the join decision"})


def test_a_chat_turns_source_shows_its_ids_only_to_its_author():
    """§A.3.4. Bug caught: a project instruction converted from a private chat turn opening that
    conversation to everyone who reads the instruction."""
    record = _record(
        "i", "instruction", "project", "p1", applicability=ANYWHERE, confirmed_by="ada",
        source=Source("chat_message", {"session_id": "s1", "message_id": "m7"}),
    )  # fmt: skip

    assert shown_source(record, record.current, viewer_id="ada")["ids"] == {
        "session_id": "s1",
        "message_id": "m7",
    }
    other = shown_source(record, record.current, viewer_id="bo")
    assert "ids" not in other and other["summary"].startswith(
        "converted from a private chat turn by ada"
    )


def test_a_revision_reads_back_as_it_was_written():
    """Bug caught: a stored revision losing its target, its references' requiredness or its
    supersession on the way through the store."""
    revision = _revision(
        target=TaskTarget("cyc_1", ("qa.test",)), confirmed_by="ada", supersedes=1,
        references=(Reference("manifest:decision:d@2", True),),
    )  # fmt: skip
    assert revision_from_document(revision_document(revision)) == revision


async def test_the_store_appends_and_refuses_a_lost_race():
    """Bug caught: two corrections racing, both stored as revision 2, so one is silently lost."""
    store = InMemoryMemoryRecords()
    record = _record("n", "note", "user", None)
    await store.create(record)
    with pytest.raises(RecordConflict):
        await store.create(record)
    await store.append_revision("n", revised(record, _revision("v2")).current)
    with pytest.raises(RecordConflict, match="next revision is 3"):
        await store.append_revision("n", revised(record, _revision("v2 again")).current)
    assert [r.number for r in (await store.get("n")).revisions] == [1, 2]
    assert [r.record_id for r in await store.list_owned("ada")] == ["n"]
    assert await store.list_owned("bo") == []
