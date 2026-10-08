"""``/api/v1/projects/{project_id}/lessons`` — Cross-Cycle Memory's lessons (SIP-0110 §0.4, §0.6–§0.7;
slice 3d, #2096).

- **read** (``memory:read``): the project's revisions with their approvals, and the approved lessons
  a revision would be supplied beside;
- **draft** (``memory:draft``): the auditor writes a revision (the 2.2 plan's D15). In 2.2 the
  auditor is the outer loop's model in the supervisor's seat, which holds ``admin``;
- **approve** (``memory:approve``, the owner alone): approve a revision for an applicability, with
  the ruling, the replay check and the combined check it rests on; revoke an approval.

Nothing here changes a running unit: an approval or a revocation reaches units admitted after it
(§0.7). A revocation answers with the running units that hold it, so their work can be halted or
restarted under a new snapshot and their measurements set apart (D9).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from squadops.api.memory_schemas import (
    ApplicabilityDTO,
    LessonApprovalRequest,
    LessonDraftRequest,
    RevocationRequest,
)
from squadops.api.middleware.auth import require_scopes
from squadops.auth.models import Identity, Scope
from squadops.memory.approval import (
    CombinedCheck,
    LessonRefused,
    approve,
    draft_revision,
    revoke,
    supplied_together,
)
from squadops.memory.lessons import Applicability, Approval, PatternRevision

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["memory"])


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, "details": None}})


def _store(request: Request):
    from squadops.api.runtime.deps import get_memory_store

    store = get_memory_store(request)
    if store is None:
        raise _error(
            503, "MEMORY_STORE_UNAVAILABLE", "Cross-Cycle Memory's store is not configured"
        )
    return store


def _actor(identity: Identity | None) -> str:
    if identity is None:
        raise _error(401, "UNAUTHENTICATED", "a lesson's record names who wrote it")
    return identity.user_id


def _applicability(project_id: str, dto: ApplicabilityDTO) -> Applicability:
    try:
        return Applicability(
            project_id=project_id,
            task_types=tuple(dto.task_types),
            roles=tuple(dto.roles),
            stacks=tuple(dto.stacks),
            model_families=tuple(dto.model_families),
        )
    except ValueError as e:
        raise _error(422, "VALIDATION_ERROR", str(e)) from e


def _lesson(revision: PatternRevision, approvals: list[Approval]) -> dict[str, Any]:
    return {
        "revision_id": revision.revision_id,
        **revision.to_dict(),
        "approvals": [a.to_dict() for a in approvals if a.revision_id == revision.revision_id],
    }


async def _revision(store, project_id: str, revision_id: str) -> PatternRevision:
    for revision in await store.list_revisions(project_id):
        if revision.revision_id == revision_id:
            return revision
    raise _error(404, "NOT_FOUND", f"no revision {revision_id} in {project_id}")


@router.get("/lessons")
async def list_lessons(
    request: Request,
    project_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> list[dict[str, Any]]:
    """Every revision of the project's lessons, by pattern and revision, each with its approvals,
    revoked ones included."""
    store = _store(request)
    approvals = await store.list_approvals(project_id)
    return [_lesson(r, approvals) for r in await store.list_revisions(project_id)]


@router.post("/lessons", status_code=201)
async def draft_lesson(
    request: Request,
    project_id: str,
    body: LessonDraftRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_DRAFT)),
) -> dict[str, Any]:
    """The auditor's draft, stored as its pattern's next revision. It reaches no task until the
    owner approves it."""
    _actor(identity)
    store = _store(request)
    known = {o.source_id for o in await store.list_observations(project_id)}
    try:
        revision = draft_revision(
            target_behavior=body.target_behavior,
            text=body.text,
            applicability=_applicability(project_id, body.applicability),
            template_id=body.template_id,
            template_version=body.template_version,
            drafter_model=body.drafter_model,
            drafter_version=body.drafter_version,
            cited_observations=body.cited_observations,
            known_observations=known,
            revisions=await store.list_revisions(project_id),
            now=datetime.now(UTC),
        )
    except LessonRefused as e:
        raise _error(422, "VALIDATION_ERROR", str(e)) from e
    await store.record_revision(revision)
    return _lesson(revision, [])


@router.get("/lessons/{revision_id}/supplied-together")
async def lessons_supplied_together(
    request: Request,
    project_id: str,
    revision_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> dict[str, Any]:
    """The approved lessons, in force now, that a task inside the revision's applicability could be
    supplied beside it: the set the auditor's combined check covers before approval (§0.6)."""
    store = _store(request)
    revision = await _revision(store, project_id, revision_id)
    revisions = await store.list_revisions(project_id)
    return {
        "revision_id": revision_id,
        "revision_ids": list(
            supplied_together(
                revision.applicability,
                pattern_id=revision.pattern_id,
                revisions=revisions,
                approvals=await store.list_approvals(project_id),
                at=datetime.now(UTC),
            )
        ),
    }


@router.post("/lessons/{revision_id}/approvals", status_code=201)
async def approve_lesson(
    request: Request,
    project_id: str,
    revision_id: str,
    body: LessonApprovalRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_APPROVE)),
) -> dict[str, Any]:
    """The owner's approval. Refused when it would widen the revision, when it does not record its
    ruling and replay check, or when its combined check did not cover every approved lesson
    supplied beside it or found a conflict (§0.6). It reaches units admitted afterwards (§0.7)."""
    approved_by = _actor(identity)
    store = _store(request)
    revision = await _revision(store, project_id, revision_id)
    applicability = (
        _applicability(project_id, body.applicability)
        if body.applicability is not None
        else revision.applicability
    )
    try:
        approval = approve(
            revision,
            applicability=applicability,
            approved_by=approved_by,
            ruling=body.ruling,
            replay_check=body.replay_check.model_dump(),
            combined_check=CombinedCheck(
                tuple(body.combined_check.revision_ids),
                body.combined_check.verdict,
                body.combined_check.reference,
            ),
            revisions=await store.list_revisions(project_id),
            approvals=await store.list_approvals(project_id),
            now=datetime.now(UTC),
        )
    except LessonRefused as e:
        raise _error(422, "VALIDATION_ERROR", str(e)) from e
    await store.record_approval(approval)
    return approval.to_dict()


@router.post("/approvals/{approval_id}/revocation")
async def revoke_lesson(
    request: Request,
    project_id: str,
    approval_id: str,
    body: RevocationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_APPROVE)),
) -> dict[str, Any]:
    """The owner's revocation. Units admitted afterwards pin without it; the answer names the
    running units that hold it (§0.7, D9)."""
    revoked_by = _actor(identity)
    store = _store(request)
    held = next(
        (a for a in await store.list_approvals(project_id) if a.approval_id == approval_id), None
    )
    if held is None:
        raise _error(404, "NOT_FOUND", f"no approval {approval_id} in {project_id}")
    try:
        revoked = revoke(held, by=revoked_by, reason=body.reason, now=datetime.now(UTC))
    except LessonRefused as e:
        if held.revoked_at is not None:
            raise _error(409, "ALREADY_REVOKED", str(e)) from e
        raise _error(422, "VALIDATION_ERROR", str(e)) from e
    await store.record_revocation(revoked)
    holding = await store.list_snapshots_holding(approval_id)
    return {
        "approval": revoked.to_dict(),
        "units_holding_it": [
            {
                "unit_kind": s.unit_kind.value,
                "unit_id": s.unit_id,
                "snapshot_id": s.snapshot_id,
                "pinned_at": s.pinned_at.isoformat(),
            }
            for s in holding
        ],
        "next": (
            "units admitted from now pin without it. Each unit named here keeps it while it runs: "
            "halt or restart its work under a new snapshot, and set its measurements apart "
            "(SIP-0110 §0.7)."
            if holding
            else "units admitted from now pin without it; no unit holds it"
        ),
    }
