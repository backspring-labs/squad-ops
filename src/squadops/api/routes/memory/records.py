"""``/api/v1/memory-records``: the typed memory records (SIP-0110 Appendix A, §A.3.2–§A.3.4,
§A.3.8; #2177).

Notes, preferences and instructions, each a record of immutable revisions. Who may write one is
decided by its kind and scope (§A.3.3), and the same rule holds through chat (#2180):
- a user-private note or preference: its owner, for themselves;
- a project note: ``memory:note``;
- a project instruction: ``memory:instruct``, which confirms it;
- a task instruction: ``cycles:write`` for a standalone cycle, ``campaigns:supervise`` for a
  campaign's.

A query is bound to a project or unbound. Bound, it answers with that project's records the caller
may read (``memory:read``) and the caller's own private ones. Unbound, only the caller's own (T4). A
withdrawn record is never retrieved, though its history is kept. A record the caller may not read
answers 404, never saying whether it exists.

A task instruction reaches the dispatches its target selects (#2178), and a project instruction the
units admitted after it is confirmed, through their snapshots (#2179). A unit already admitted keeps
the revision it pinned, so a project instruction's withdrawal answers with the units holding it: its
emergency withdrawal (§A.3.8), the way a lesson's revocation names them (SIP-0110 §0.7).

A record captured in chat is written there (#2180), never here: its source is the chat turn, which only
chat can vouch for. Its link opens that one turn, and only for the session's owner (T15).
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from squadops.api.errors import http_error
from squadops.api.memory_schemas import (
    MemoryRecordBuild,
    MemoryRecordChatUse,
    MemoryRecordContent,
    MemoryRecordCreateRequest,
    MemoryRecordResponse,
    MemoryRecordRevisionResponse,
    MemoryRecordSourceTurnResponse,
    MemoryRecordTaskUse,
    MemoryRecordUsesResponse,
    MemoryRecordWithdrawalRequest,
    MemoryRecordWithdrawalResponse,
)
from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.memory.applicability import refuse_unmatched
from squadops.api.routes.memory.held_units import next_step, running_and_finished, unit_row
from squadops.api.routes.memory.interventions import (
    dispatch_turn,
    log_intervention,
    of_campaign,
    refuse_dispatched,
    refuse_lesson_for_control,
    target_cycle,
    turn_of,
)
from squadops.api.runtime.deps import (
    get_campaign_registry,
    get_cycle_registry,
    get_memory_records,
    get_memory_store,
    get_reference_resolvers,
)
from squadops.auth.models import Identity, scopes_for_roles
from squadops.comms.models import SessionNotFoundError
from squadops.memory.build_report import exposure_builds
from squadops.memory.indicators import BuildRow
from squadops.memory.pinning import cycle_binding
from squadops.memory.record_uses import NO_EFFECT_MEASURED, chat_uses, task_uses
from squadops.memory.records import (
    InstructionApplicability,
    MemoryRecord,
    NotPermitted,
    RecordKind,
    RecordRefused,
    RecordScope,
    RecordStatus,
    Revision,
    Source,
    SourceKind,
    TaskTarget,
    authorize_write,
    is_current,
    new_record,
    reference_of,
    revised,
    revision_document,
    shown_source,
    unbindable,
    visible,
    withdrawn,
)
from squadops.memory.reference_binding import bound_for_cycle, with_bindings
from squadops.ports.memory.records import RecordConflict

router = APIRouter(prefix="/api/v1/memory-records", tags=["memory"])
logger = logging.getLogger(__name__)


def _store(request: Request):
    store = get_memory_records(request)
    if store is None:
        raise http_error(
            503, "MEMORY_RECORDS_UNAVAILABLE", "the memory records' store is not configured"
        )
    return store


def _who(identity: Identity | None) -> tuple[str, frozenset[str]]:
    if identity is None:
        raise http_error(401, "UNAUTHENTICATED", "a memory record names who wrote it")
    return identity.user_id, frozenset(identity.scopes) | scopes_for_roles(identity.roles)


async def _bound_with_cycle(request: Request, cycle: Any, revision: Revision) -> Revision:
    """A task instruction's revision, its ``@current`` references bound for its cycle as it is
    written (§3.7; #2178 T16), or the refusal for one that won't bind. Any other record's is as
    written: a project instruction's is bound when a unit pins it."""
    if cycle is None:
        return revision
    bound = await bound_for_cycle(
        revision.references, get_reference_resolvers(request), cycle_binding(cycle)
    )
    return dataclasses.replace(revision, references=with_bindings(revision.references, bound))


async def _refuse_unbindable(request: Request, revision: Revision, project_id: str | None) -> None:
    """Refuse (422) an ``@current`` reference no registered resolver can bind (#2179 T16): it
    could never be bound at a unit's admission, so every task it applied to would be held. One
    whose family binds nothing for the record's project is refused too, naming why (§5ac)."""
    resolvers = get_reference_resolvers(request)
    unbound = unbindable(revision, resolvers.keys())
    if unbound:
        raise http_error(
            422,
            "VALIDATION_ERROR",
            f"no resolver binds @current for {', '.join(unbound)}: name the revision it means",
        )
    if not project_id:
        return
    refused = []
    for reference in revision.references:
        if not is_current(reference.ref):
            continue
        try:
            why = await resolvers[reference.family].binds_nothing_for(project_id)
        except Exception:  # noqa: BLE001 — an early refusal only; admission still binds or holds
            logger.warning("reference_family_unread ref=%s", reference.ref, exc_info=True)
            continue
        if why:
            refused.append(f"{reference.ref} ({why})")
    if refused:
        raise http_error(
            422,
            "VALIDATION_ERROR",
            f"no unit of {project_id} can bind {'; '.join(refused)}: the reference can't apply to "
            "this project",
        )


#: Sources only their own route writes (the cycle's create request; a gate's decision): never
#: claimed through this one (§A.3.4).
_VOUCHED_ELSEWHERE = frozenset({SourceKind.CYCLE_REQUEST, SourceKind.GATE_DECISION})


def _revision(content: MemoryRecordContent, *, actor: str, kind: str, now: datetime) -> Revision:
    if content.source.kind == SourceKind.CHAT_MESSAGE:
        # #2180: a chat turn's record is captured in chat, which checks the session is the
        # writer's and records the turn itself; a source claimed here is never trusted.
        raise http_error(
            422,
            "VALIDATION_ERROR",
            "a chat turn's record is captured in chat (POST /api/v1/chat/sessions/{session_id}/"
            "captures), which records its source",
        )
    if content.source.kind in _VOUCHED_ELSEWHERE:
        # #2178: a source only its own route writes. A task instruction claiming the cycle's create
        # request would read as admitted, reaching its task unmarked as the intervention it is.
        raise http_error(
            422,
            "VALIDATION_ERROR",
            f"a {content.source.kind} record is written by its own route, which vouches for it; "
            "one written here is an api_call",
        )
    if content.applicability is not None:
        refuse_unmatched(content.applicability)
    try:
        return Revision(
            number=1,
            body=content.body,
            author=actor,
            created_at=now,
            source=Source(content.source.kind, dict(content.source.ids)),
            # An instruction written through the API is confirmed by the one who holds the scope
            # its kind needs; chat's capture confirms separately (#2180).
            confirmed_by=actor if kind == RecordKind.INSTRUCTION else None,
            suggestion=content.suggestion,
            applicability=(
                InstructionApplicability(
                    tuple(content.applicability.task_types),
                    tuple(content.applicability.roles),
                    tuple(content.applicability.stacks),
                )
                if content.applicability
                else None
            ),
            target=(
                TaskTarget(
                    content.target.cycle_id,
                    tuple(content.target.task_types),
                    content.target.carries_into,
                )
                if content.target
                else None
            ),
            references=tuple(reference_of(r) for r in content.references),
        )
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e


def _response(
    record: MemoryRecord,
    viewer: str,
    deleted: frozenset[str] = frozenset(),
    *,
    control_log_entry_id: str | None = None,
) -> MemoryRecordResponse:
    def one(revision: Revision) -> MemoryRecordRevisionResponse:
        doc = revision_document(revision)
        doc["source"] = shown_source(
            record,
            revision,
            viewer_id=viewer,
            session_deleted=_chat_session_of(revision) in deleted,
        )
        return MemoryRecordRevisionResponse.model_validate(doc)

    return MemoryRecordResponse(
        record_id=record.record_id,
        kind=record.kind,
        scope=record.scope,
        project_id=record.project_id,
        owner_id=record.owner_id,
        status=record.status,
        current=one(record.current),
        revisions=[one(r) for r in record.revisions],
        status_changes=[
            {"status": c.status, "by": c.by, "at": c.at.isoformat(), "why": c.why}
            for c in record.status_changes
        ],
        control_log_entry_id=control_log_entry_id,
    )


def _chat_session_of(revision: Revision) -> str | None:
    if revision.source.kind != SourceKind.CHAT_MESSAGE:
        return None
    return revision.source.ids.get("session_id")


async def _deleted_sessions(request: Request, records: list[MemoryRecord]) -> frozenset[str]:
    """The chat sessions these records came from that their owners have deleted (Q29), so each
    record says it. A session that can't be read is left unmarked, and the read is logged."""
    chat_repo = getattr(request.app.state, "chat_repo", None)
    sessions = {s for r in records for v in r.revisions if (s := _chat_session_of(v))}
    if chat_repo is None or not sessions:
        return frozenset()
    deleted = set()
    for session_id in sessions:
        try:
            session = await chat_repo.get_session(session_id)
        except SessionNotFoundError:
            continue
        except Exception:  # noqa: BLE001 — the record is still answered, unmarked
            logger.warning("memory_record_source_unread session=%s", session_id, exc_info=True)
            continue
        if session.deleted_at is not None:
            deleted.add(session_id)
    return frozenset(deleted)


async def _readable(request: Request, record_id: str, actor: str, scopes) -> MemoryRecord:
    record = await _store(request).get(record_id)
    if record is None or not visible(
        record, viewer_id=actor, viewer_scopes=scopes, project_id=record.project_id
    ):
        raise http_error(404, "NOT_FOUND", f"no memory record {record_id}")
    return record


@router.post("", status_code=201)
async def create_memory_record(
    request: Request,
    body: MemoryRecordCreateRequest,
    identity: Identity | None = Depends(require_scopes()),
) -> MemoryRecordResponse:
    """A new record, its first revision. Refused (403) when the caller doesn't hold what its
    kind and scope need, and (422) when the record breaks §A.3.2's rules."""
    actor, scopes = _who(identity)
    revision = _revision(body, actor=actor, kind=body.kind, now=datetime.now(UTC))
    cycle = await target_cycle(request, body.scope, body.project_id, revision.target)
    try:
        authorize_write(
            body.kind, body.scope, actor_id=actor, actor_scopes=scopes, owner_id=actor,
            campaign_cycle=of_campaign(cycle),
        )  # fmt: skip
        await _refuse_unbindable(request, revision, body.project_id)
        # #2545: from the dispatched check to the write, no dispatch of the cycle composes.
        async with dispatch_turn(request, turn_of(cycle)):
            if cycle is not None:
                # §3.5: a task instruction written here comes after its cycle's admission. Refused
                # before its references are bound, which neither refusal reads (T16).
                await refuse_lesson_for_control(request, cycle, revision)
                await refuse_dispatched(request, cycle, revision.target)
            revision = await _bound_with_cycle(request, cycle, revision)
            record = new_record(
                record_id=f"mrec_{uuid.uuid4().hex[:16]}",
                kind=body.kind,
                scope=body.scope,
                project_id=body.project_id,
                owner_id=actor,
                revision=revision,
            )
            await _store(request).create(record)
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    except RecordConflict as e:
        raise http_error(409, "CONFLICT", str(e)) from e
    entry = await log_intervention(request, identity, cycle, record, "add")
    return _response(record, actor, control_log_entry_id=entry)


@router.get("")
async def list_memory_records(
    request: Request,
    project_id: str | None = None,
    kind: str | None = None,
    scope: str | None = None,
    status: str = RecordStatus.ACTIVE,
    identity: Identity | None = Depends(require_scopes()),
) -> list[MemoryRecordResponse]:
    """The records a query bound to ``project_id`` answers with (unbound: the caller's own private
    records only, T4), oldest first. Active ones by default, as a retrieval answers; ``status``
    ``withdrawn`` or ``all`` lists the rest for the memory view (#2182), every revision kept."""
    if status not in (*RecordStatus.ALL, "all"):
        raise http_error(
            422, "VALIDATION_ERROR", f"status is one of {sorted(RecordStatus.ALL)} or all"
        )
    actor, scopes = _who(identity)
    store = _store(request)
    held = await store.list_owned(actor)
    if project_id is not None:
        held += await store.list_project(project_id)
    # A private record that names a project is in both lists: answered once, oldest first.
    unique = sorted(
        {r.record_id: r for r in held}.values(),
        key=lambda r: (r.revisions[0].created_at, r.record_id),
    )
    found = [
        r
        for r in unique
        if visible(r, viewer_id=actor, viewer_scopes=scopes, project_id=project_id)
        and (status == "all" or r.status == status)
        and (kind is None or r.kind == kind)
        and (scope is None or r.scope == scope)
    ]
    deleted = await _deleted_sessions(request, found)
    return [_response(r, actor, deleted) for r in found]


@router.get("/{record_id}")
async def get_memory_record(
    request: Request,
    record_id: str,
    identity: Identity | None = Depends(require_scopes()),
) -> MemoryRecordResponse:
    """One record with every revision and status change, withdrawn ones included."""
    actor, scopes = _who(identity)
    record = await _readable(request, record_id, actor, scopes)
    return _response(record, actor, await _deleted_sessions(request, [record]))


def _build(row: BuildRow) -> MemoryRecordBuild:
    """One build the record's dispatches fed, with its indicators, or none when its evidence is
    missing (§0.10: never a failure)."""
    i = row.indicators
    return MemoryRecordBuild(
        run_id=row.run_id,
        exposures=list(row.exposures),
        verdict=i.verdict if i else None,
        failed_rounds=i.failed_rounds if i else None,
        refunded_rounds=i.refunded_rounds if i else None,
        rounds_to_green=i.rounds_to_green if i else None,
        accepted=i.accepted if i else None,
    )


@router.get("/{record_id}/uses")
async def memory_record_uses(
    request: Request,
    record_id: str,
    identity: Identity | None = Depends(require_scopes()),
) -> MemoryRecordUsesResponse:
    """What used the record (Appendix A §3.11, T11): each dispatch that was handed it or held for it,
    with the revision and the section's disposition; the reader's own chat turns that held it, and a
    count of other people's; each build its dispatches fed, once, with its indicators observed. Its
    effect is kept apart, and for a note or an instruction none is measured."""
    actor, scopes = _who(identity)
    record = await _readable(request, record_id, actor, scopes)
    store = get_memory_store(request)
    if store is None:
        raise http_error(503, "MEMORY_UNAVAILABLE", "the memory store is not configured")
    exposures = await store.list_project_exposures(record.project_id) if record.project_id else []
    tasks = task_uses(record_id, exposures)
    supplied = {t.exposure_id for t in tasks if t.held is None}
    report = await exposure_builds(
        [e for e in exposures if e.exposure_id in supplied],
        cycles=get_cycle_registry(request),
        campaigns=get_campaign_registry(request),
    )
    chats, others = chat_uses(
        record_id, await store.list_chat_exposures_supplying(record_id), viewer_id=actor
    )
    return MemoryRecordUsesResponse(
        record_id=record_id,
        tasks=[MemoryRecordTaskUse(**vars(t)) for t in tasks],
        chats=[
            MemoryRecordChatUse(**{**vars(c), "assembled_at": c.assembled_at.isoformat()})
            for c in chats
        ],
        others_chat_turns=others,
        builds=[_build(row) for row in report.builds],
        unbuilt={state.value: list(ids) for state, ids in report.unbuilt.items()},
        effect=NO_EFFECT_MEASURED,
    )


@router.get("/{record_id}/revisions/{number}/source")
async def follow_memory_record_source(
    request: Request,
    record_id: str,
    number: int,
    identity: Identity | None = Depends(require_scopes()),
) -> MemoryRecordSourceTurnResponse:
    """The chat turn a revision came from (§A.3.4, T15). Following the link is authorized like
    reading its target: only the session's owner opens it, and it opens that one turn, never the
    session's others. Anyone else is refused, however they read the record."""
    actor, scopes = _who(identity)
    record = await _readable(request, record_id, actor, scopes)
    revision = next((r for r in record.revisions if r.number == number), None)
    if revision is None:
        raise http_error(404, "NOT_FOUND", f"{record_id} has no revision {number}")
    session_id = _chat_session_of(revision)
    if session_id is None:
        raise http_error(
            422, "VALIDATION_ERROR", f"its source is a {revision.source.kind}, not a chat turn"
        )
    chat_repo = getattr(request.app.state, "chat_repo", None)
    if chat_repo is None:
        raise http_error(503, "CHAT_UNAVAILABLE", "the chat store is not configured")
    try:
        session = await chat_repo.get_session(session_id)
    except SessionNotFoundError:
        session = None
    if session is None or session.user_id != actor:
        raise http_error(
            403, "FORBIDDEN", "a private chat turn is opened only by its session's owner"
        )
    if session.deleted_at is not None:
        raise http_error(404, "NOT_FOUND", "the turn's session was deleted by its owner")
    message = await chat_repo.get_message(str(revision.source.ids.get("message_id") or ""))
    if message is None or message.session_id != session_id:
        raise http_error(404, "NOT_FOUND", "the turn is no longer in its session")
    return MemoryRecordSourceTurnResponse(
        session_id=message.session_id,
        message_id=message.message_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat(),
    )


@router.post("/{record_id}/revisions", status_code=201)
async def revise_memory_record(
    request: Request,
    record_id: str,
    body: MemoryRecordContent,
    identity: Identity | None = Depends(require_scopes()),
) -> MemoryRecordResponse:
    """A correction: a new revision that supersedes the current one, which is kept (§A.3.8)."""
    actor, scopes = _who(identity)
    record = await _readable(request, record_id, actor, scopes)
    revision = _revision(body, actor=actor, kind=record.kind, now=datetime.now(UTC))
    cycle = await target_cycle(request, record.scope, record.project_id, revision.target)
    try:
        authorize_write(
            record.kind, record.scope, actor_id=actor, actor_scopes=scopes,
            owner_id=record.owner_id, campaign_cycle=of_campaign(cycle),
        )  # fmt: skip
        await _refuse_unbindable(request, revision, record.project_id)
        # #2545: from the dispatched check to the write, no dispatch of the cycle composes.
        async with dispatch_turn(request, turn_of(cycle)):
            if cycle is not None:
                # §3.8: a task instruction is corrected before its task dispatches, or not at all:
                # the types it drops are checked as well as those it names (the second read of
                # #2178). Refused before its references are bound, which neither refusal reads
                # (T16).
                before = record.current.target.task_types if record.current.target else ()
                after = revision.target.task_types if revision.target else ()
                together = tuple(dict.fromkeys((*before, *after)))
                await refuse_lesson_for_control(request, cycle, revision)
                await refuse_dispatched(request, cycle, TaskTarget(cycle.cycle_id, together))
            revision = await _bound_with_cycle(request, cycle, revision)
            updated = revised(record, revision)
            await _store(request).append_revision(record_id, updated.current)
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    except RecordConflict as e:
        raise http_error(409, "CONFLICT", str(e)) from e
    entry = await log_intervention(request, identity, cycle, updated, "revise")
    return _response(
        updated, actor, await _deleted_sessions(request, [updated]), control_log_entry_id=entry
    )


@router.post("/{record_id}/withdrawal", status_code=201)
async def withdraw_memory_record(
    request: Request,
    record_id: str,
    body: MemoryRecordWithdrawalRequest,
    identity: Identity | None = Depends(require_scopes()),
) -> MemoryRecordWithdrawalResponse:
    """A withdrawal: the record is no longer retrieved, and every revision is kept (§A.3.8). A
    project instruction's answers with the units whose snapshot pinned it, as a lesson's revocation
    does: units admitted from now pin without it, and those named keep it until their work is
    halted or restarted under a new snapshot (its emergency withdrawal, SIP-0110 §0.7)."""
    actor, scopes = _who(identity)
    record = await _readable(request, record_id, actor, scopes)
    target: Any = record.current.target
    cycle = await target_cycle(request, record.scope, record.project_id, target)
    try:
        authorize_write(
            record.kind, record.scope, actor_id=actor, actor_scopes=scopes,
            owner_id=record.owner_id, campaign_cycle=of_campaign(cycle),
        )  # fmt: skip
        updated = withdrawn(record, by=actor, at=datetime.now(UTC), why=body.why)
        await _store(request).append_status(record_id, updated.status_changes[-1])
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    entry = await log_intervention(request, identity, cycle, updated, "withdraw")
    shown = _response(
        updated, actor, await _deleted_sessions(request, [updated]), control_log_entry_id=entry
    )
    held: dict[str, Any] = {}
    if record.kind == RecordKind.INSTRUCTION and record.scope == RecordScope.PROJECT:
        held = await _units_pinning(request, record_id)
    return MemoryRecordWithdrawalResponse(**shown.model_dump(), **held)


#: The rule a project instruction's emergency withdrawal follows.
_WITHDRAWAL_RULE = "SIP-0110 §0.7, Appendix A §3.8"


async def _units_pinning(request: Request, record_id: str) -> dict[str, Any]:
    """The units whose snapshot pinned the instruction, running then finished, and the next step;
    or, when the snapshots can't be read, no lists and a next step that says so. The withdrawal
    stands either way: the record's store took it."""
    store = get_memory_store(request)
    try:
        if store is None:
            raise LookupError("the memory store is not configured")
        live, finished = await running_and_finished(
            request, await store.list_snapshots_pinning(record_id)
        )
    except Exception:  # noqa: BLE001 — an unknown holder is named, never read as none
        logger.warning("memory_withdrawal_units_unread record=%s", record_id, exc_info=True)
        return {
            "units_holding_it": None,
            "finished_units_holding_it": None,
            "next": (
                "units admitted from now pin without it. The snapshots couldn't be read, so "
                "the units already holding it are unknown: find them before relying on any unit "
                f"admitted while it was in force ({_WITHDRAWAL_RULE})."
            ),
        }
    return {
        "units_holding_it": [unit_row(s) for s in live],
        "finished_units_holding_it": [unit_row(s) for s in finished],
        "next": next_step(live, finished, rule=_WITHDRAWAL_RULE),
    }
