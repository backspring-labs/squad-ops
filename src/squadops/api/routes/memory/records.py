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

Nothing here reaches a task yet: task instructions are bound to dispatch in #2178, and project
instructions to a unit's snapshot in #2179.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request

from squadops.api.errors import http_error
from squadops.api.memory_schemas import (
    MemoryRecordContent,
    MemoryRecordCreateRequest,
    MemoryRecordResponse,
    MemoryRecordRevisionResponse,
    MemoryRecordWithdrawalRequest,
)
from squadops.api.middleware.auth import require_scopes
from squadops.api.runtime.deps import get_cycle_registry, get_memory_records
from squadops.auth.models import Identity, scopes_for_roles
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.memory.records import (
    InstructionApplicability,
    MemoryRecord,
    NotPermitted,
    RecordKind,
    RecordRefused,
    RecordScope,
    Revision,
    Source,
    TaskTarget,
    authorize_write,
    new_record,
    reference_of,
    retrieved,
    revised,
    revision_document,
    shown_source,
    visible,
    withdrawn,
)
from squadops.ports.memory.records import RecordConflict

router = APIRouter(prefix="/api/v1/memory-records", tags=["memory"])


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


async def _campaign_cycle(request: Request, scope: str, project_id: str | None, target) -> bool:
    """Whether a task instruction's target is a campaign's cycle, after checking it is a cycle
    of the record's project and that every task type it selects is an authoring task (#2178: an
    instruction for any other would reach nothing). ``False`` for any other record."""
    if scope != RecordScope.TASK or target is None:
        return False
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
    return bool(getattr(cycle, "campaign_id", None))


def _revision(content: MemoryRecordContent, *, actor: str, kind: str, now: datetime) -> Revision:
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


def _response(record: MemoryRecord, viewer: str) -> MemoryRecordResponse:
    def one(revision: Revision) -> MemoryRecordRevisionResponse:
        doc = revision_document(revision)
        doc["source"] = shown_source(record, revision, viewer_id=viewer)
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
    )


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
    campaign = await _campaign_cycle(request, body.scope, body.project_id, revision.target)
    try:
        authorize_write(
            body.kind, body.scope, actor_id=actor, actor_scopes=scopes, owner_id=actor,
            campaign_cycle=campaign,
        )  # fmt: skip
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
    return _response(record, actor)


@router.get("")
async def list_memory_records(
    request: Request,
    project_id: str | None = None,
    kind: str | None = None,
    identity: Identity | None = Depends(require_scopes()),
) -> list[MemoryRecordResponse]:
    """The active records a query bound to ``project_id`` answers with (unbound: the caller's
    own private records only, T4), oldest first."""
    actor, scopes = _who(identity)
    store = _store(request)
    held = await store.list_owned(actor)
    if project_id is not None:
        held += await store.list_project(project_id)
    found = retrieved(held, viewer_id=actor, viewer_scopes=scopes, project_id=project_id)
    return [_response(r, actor) for r in found if kind is None or r.kind == kind]


@router.get("/{record_id}")
async def get_memory_record(
    request: Request,
    record_id: str,
    identity: Identity | None = Depends(require_scopes()),
) -> MemoryRecordResponse:
    """One record with every revision and status change, withdrawn ones included."""
    actor, scopes = _who(identity)
    return _response(await _readable(request, record_id, actor, scopes), actor)


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
    campaign = await _campaign_cycle(request, record.scope, record.project_id, revision.target)
    try:
        authorize_write(
            record.kind, record.scope, actor_id=actor, actor_scopes=scopes,
            owner_id=record.owner_id, campaign_cycle=campaign,
        )  # fmt: skip
        updated = revised(record, revision)
        await _store(request).append_revision(record_id, updated.current)
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    except RecordConflict as e:
        raise http_error(409, "CONFLICT", str(e)) from e
    return _response(updated, actor)


@router.post("/{record_id}/withdrawal", status_code=201)
async def withdraw_memory_record(
    request: Request,
    record_id: str,
    body: MemoryRecordWithdrawalRequest,
    identity: Identity | None = Depends(require_scopes()),
) -> MemoryRecordResponse:
    """A withdrawal: the record is no longer retrieved, and every revision is kept (§A.3.8)."""
    actor, scopes = _who(identity)
    record = await _readable(request, record_id, actor, scopes)
    target: Any = record.current.target
    campaign = await _campaign_cycle(request, record.scope, record.project_id, target)
    try:
        authorize_write(
            record.kind, record.scope, actor_id=actor, actor_scopes=scopes,
            owner_id=record.owner_id, campaign_cycle=campaign,
        )  # fmt: skip
        updated = withdrawn(record, by=actor, at=datetime.now(UTC), why=body.why)
        await _store(request).append_status(record_id, updated.status_changes[-1])
    except NotPermitted as e:
        raise http_error(403, "FORBIDDEN", str(e)) from e
    except RecordRefused as e:
        raise http_error(422, "VALIDATION_ERROR", str(e)) from e
    return _response(updated, actor)
