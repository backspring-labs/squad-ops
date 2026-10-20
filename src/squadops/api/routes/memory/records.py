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
from squadops.api.routes.memory.interventions import record_on_control_log
from squadops.api.runtime.deps import (
    get_campaign_registry,
    get_cycle_registry,
    get_memory_records,
    get_memory_store,
)
from squadops.auth.models import Identity, scopes_for_roles
from squadops.campaigns.models import ControlOperation
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.comms.models import SessionNotFoundError
from squadops.cycles.models import RunStatus
from squadops.memory.build_report import exposure_builds
from squadops.memory.indicators import BuildRow
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
    new_record,
    reference_of,
    revised,
    revision_document,
    shown_source,
    visible,
    withdrawn,
)
from squadops.memory.task_instructions import dispatched
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


async def _target_cycle(request: Request, scope: str, project_id: str | None, target) -> Any:
    """A task instruction's target cycle, after checking it is a cycle of the record's project and
    that every task type it selects is an authoring task (#2178: an instruction for any other would
    reach nothing). ``None`` for any other record."""
    if scope != RecordScope.TASK or target is None:
        return None
    unreachable = [t for t in target.task_types if authoring_seam_of(t) is None]
    if unreachable:
        raise http_error(
            422,
            "VALIDATION_ERROR",
            f"{', '.join(unreachable)} authors nothing an instruction reaches",
        )
    try:
        cycle = await get_cycle_registry(request).get_cycle(target.cycle_id)
    except Exception as e:
        raise http_error(422, "VALIDATION_ERROR", f"no cycle {target.cycle_id}") from e
    if cycle.project_id != project_id:
        raise http_error(
            422, "VALIDATION_ERROR", f"{target.cycle_id} is not a cycle of {project_id}"
        )
    return cycle


def _of_campaign(cycle: Any) -> bool:
    return bool(getattr(cycle, "campaign_id", None))


#: A run in one of these may still dispatch: an instruction added for a task it dispatched would
#: reach the task's re-takes and repairs with a binding its first dispatch never had (§3.5).
_LIVE_RUN = frozenset({RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.PAUSED.value})


async def _refuse_dispatched(request: Request, cycle: Any, target: Any) -> None:
    """Refuse (409) an instruction added or revised after admission for a task its cycle has
    dispatched in a run still running; unknown refuses too (503), never reads as undispatched."""
    try:
        runs = await get_cycle_registry(request).list_runs(cycle.cycle_id)
        live = [r.run_id for r in runs if r.status in _LIVE_RUN]
        store = get_memory_store(request)
        if live and store is None:
            raise LookupError("the memory store is not configured")
        exposures = [e for run_id in live for e in await store.list_exposures(run_id)]
    except Exception:  # noqa: BLE001 — an unknown dispatch is refused, never assumed absent
        logger.warning("task_instruction_dispatch_unread cycle=%s", cycle.cycle_id, exc_info=True)
        raise http_error(
            503,
            "MEMORY_UNAVAILABLE",
            f"whether {cycle.cycle_id}'s selected tasks have dispatched can't be read",
        ) from None
    hit = dispatched(target.task_types, exposures, live)
    if hit:
        raise http_error(
            409,
            "TASK_DISPATCHED",
            f"{', '.join(f'{run} {task}' for run, task in hit)} already dispatched: an instruction "
            "added now would reach its re-takes and repairs with a binding its first dispatch "
            "didn't have. Give it to the cycle's next run (SIP-0110 Appendix A §3.5)",
        )


async def _log_intervention(
    request: Request, identity: Identity | None, cycle: Any, record: MemoryRecord, action: str
) -> str | None:
    """A campaign cycle's task instruction changed after admission, as a row in the campaign's
    control log (§3.5): ``None`` for a standalone cycle's, or when the row couldn't be written."""
    if not _of_campaign(cycle):
        return None
    current = record.current
    return await record_on_control_log(
        request,
        identity,
        cycle.campaign_id,
        operation=ControlOperation.INSTRUCT,
        reason=current.body if action != "withdraw" else record.status_changes[-1].why,
        idempotency_key=f"instruct:{record.record_id}:{action}:{current.number}",
        target=record.record_id,
        binding={
            "action": action,
            "record_id": record.record_id,
            "revision": current.number,
            "cycle_id": cycle.cycle_id,
            "task_types": list(current.target.task_types) if current.target else [],
        },
    )


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
                TaskTarget(content.target.cycle_id, tuple(content.target.task_types))
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
    cycle = await _target_cycle(request, body.scope, body.project_id, revision.target)
    try:
        authorize_write(
            body.kind, body.scope, actor_id=actor, actor_scopes=scopes, owner_id=actor,
            campaign_cycle=_of_campaign(cycle),
        )  # fmt: skip
        record = new_record(
            record_id=f"mrec_{uuid.uuid4().hex[:16]}",
            kind=body.kind,
            scope=body.scope,
            project_id=body.project_id,
            owner_id=actor,
            revision=revision,
        )
        if cycle is not None:
            # §3.5: a task instruction written here comes after its cycle's admission.
            await _refuse_dispatched(request, cycle, revision.target)
        await _store(request).create(record)
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    except RecordConflict as e:
        raise http_error(409, "CONFLICT", str(e)) from e
    entry = await _log_intervention(request, identity, cycle, record, "add")
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
    cycle = await _target_cycle(request, record.scope, record.project_id, revision.target)
    try:
        authorize_write(
            record.kind, record.scope, actor_id=actor, actor_scopes=scopes,
            owner_id=record.owner_id, campaign_cycle=_of_campaign(cycle),
        )  # fmt: skip
        updated = revised(record, revision)
        if cycle is not None:
            # §3.8: a task instruction is corrected before its task dispatches, or not at all.
            await _refuse_dispatched(request, cycle, revision.target)
        await _store(request).append_revision(record_id, updated.current)
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    except RecordConflict as e:
        raise http_error(409, "CONFLICT", str(e)) from e
    entry = await _log_intervention(request, identity, cycle, updated, "revise")
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
    cycle = await _target_cycle(request, record.scope, record.project_id, target)
    try:
        authorize_write(
            record.kind, record.scope, actor_id=actor, actor_scopes=scopes,
            owner_id=record.owner_id, campaign_cycle=_of_campaign(cycle),
        )  # fmt: skip
        updated = withdrawn(record, by=actor, at=datetime.now(UTC), why=body.why)
        await _store(request).append_status(record_id, updated.status_changes[-1])
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    entry = await _log_intervention(request, identity, cycle, updated, "withdraw")
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
