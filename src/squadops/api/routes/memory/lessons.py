"""``/api/v1/projects/{project_id}/lessons`` and ``…/exposures`` — Cross-Cycle Memory's lessons and
what each consuming task was supplied (SIP-0110 §0.4, §0.6–§0.7, §0.10; slice 3d, #2096).

- **read** (``memory:read``): the project's revisions with their approvals, and the approved lessons
  a revision would be supplied beside;
- **draft** (``memory:draft``): the auditor writes a revision (the 2.2 plan's D15), and assesses an
  exposure's output against a target (§0.10). In 2.2 the auditor is the outer loop's model in the
  supervisor's seat, which holds ``admin``;
- **approve** (``memory:approve``, the owner alone): approve a revision for an applicability, with
  the ruling, the replay check and the combined check it rests on; revoke an approval.
- **annotations** (§0.4, #2160): the auditor proposes a classification for an observation classified
  only in prose (``memory:draft``), and the owner reviews it (``memory:approve``). Only a reviewed
  annotation classifies, and a lesson cites only classified observations.

Nothing here changes a running unit: an approval or a revocation reaches units admitted after it
(§0.7). A revocation answers with the running units that hold it, so their work can be halted or
restarted under a new snapshot and their measurements set apart (D9).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from squadops.api.memory_schemas import (
    AnnotationRequest,
    AnnotationReviewRequest,
    ApplicabilityDTO,
    AssessmentRequest,
    LessonApprovalRequest,
    LessonDraftRequest,
    RevocationRequest,
)
from squadops.api.middleware.auth import require_scopes
from squadops.auth.models import Identity, Scope
from squadops.memory.annotation import (
    AnnotationRefused,
    annotate,
    citable,
    effective_classification,
    review,
)
from squadops.memory.approval import (
    CombinedCheck,
    LessonRefused,
    approve,
    draft_revision,
    revoke,
    supplied_together,
)
from squadops.memory.assessment import (
    AssessmentRefused,
    TargetState,
    assess,
    latest,
    supplied_to,
    target_absence_rates,
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
    allowed = citable(
        await store.list_observations(project_id), await store.list_annotations(project_id)
    )
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
            citable_observations=allowed,
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


@router.get("/observations")
async def list_observations(
    request: Request,
    project_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> list[dict[str, Any]]:
    """The project's observations, each as projected, with its annotations and the classification
    memory reads for it: the latest reviewed annotation's, or the projected one (§0.4)."""
    store = _store(request)
    annotations = await store.list_annotations(project_id)
    return [
        {
            **o.to_dict(),
            "annotations": [a.to_dict() for a in annotations if a.source_id == o.source_id],
            "effective_classification": effective_classification(o, annotations).to_dict(),
        }
        for o in await store.list_observations(project_id)
    ]


@router.post("/observations/{source_id}/annotations", status_code=201)
async def annotate_observation(
    request: Request,
    project_id: str,
    source_id: str,
    body: AnnotationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_DRAFT)),
) -> dict[str, Any]:
    """A proposed classification of the observation, stored beside it. The observation is never
    edited, and the annotation classifies nothing until it is reviewed."""
    _actor(identity)
    store = _store(request)
    observation = next(
        (o for o in await store.list_observations(project_id) if o.source_id == source_id), None
    )
    if observation is None:
        raise _error(404, "NOT_FOUND", f"no observation {source_id} in {project_id}")
    try:
        annotation = annotate(
            observation,
            values=body.values,
            target_behavior=body.target_behavior,
            evidence=body.evidence,
            context=body.context,
            annotator=body.annotator,
            now=datetime.now(UTC),
            rationale=body.rationale,
        )
    except AnnotationRefused as e:
        raise _error(422, "VALIDATION_ERROR", str(e)) from e
    await store.record_annotation(annotation)
    return annotation.to_dict()


@router.post("/annotations/{annotation_id}/review")
async def review_annotation(
    request: Request,
    project_id: str,
    annotation_id: str,
    body: AnnotationReviewRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_APPROVE)),
) -> dict[str, Any]:
    """The owner's review: from now on the annotation is its observation's classification, and a
    lesson may cite the observation. A review is never rewritten."""
    reviewer = _actor(identity)
    store = _store(request)
    held = next(
        (a for a in await store.list_annotations(project_id) if a.annotation_id == annotation_id),
        None,
    )
    if held is None:
        raise _error(404, "NOT_FOUND", f"no annotation {annotation_id} in {project_id}")
    try:
        reviewed = review(held, reviewed_by=reviewer, now=datetime.now(UTC), note=body.note)
    except AnnotationRefused as e:
        raise _error(409, "ALREADY_REVIEWED", str(e)) from e
    await store.record_annotation_review(reviewed)
    return reviewed.to_dict()


@router.get("/exposures")
async def list_exposures(
    request: Request,
    project_id: str,
    run_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> list[dict[str, Any]]:
    """A run's exposures, each with the latest assessment of each target (§0.8 step 7, §0.10)."""
    store = _store(request)
    read = latest(await store.list_assessments(project_id))
    return [
        {
            **e.to_dict(),
            "assessments": [
                a.to_dict() for (exposure_id, _), a in read.items() if exposure_id == e.exposure_id
            ],
        }
        for e in await store.list_exposures(run_id)
        if e.query.project_id == project_id
    ]


@router.post("/exposures/{exposure_id}/assessments", status_code=201)
async def assess_exposure(
    request: Request,
    project_id: str,
    exposure_id: str,
    body: AssessmentRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_DRAFT)),
) -> dict[str, Any]:
    """One target's state in the exposure's authored output, by the target's rubric (§0.10). An
    absence is refused unless the output did its required work."""
    assessed_by = _actor(identity)
    store = _store(request)
    exposure = await store.get_exposure(exposure_id)
    if exposure is None or exposure.query.project_id != project_id:
        raise _error(404, "NOT_FOUND", f"no exposure {exposure_id} in {project_id}")
    try:
        assessment = assess(
            project_id=project_id,
            exposure_id=exposure_id,
            pattern_id=body.pattern_id,
            state=TargetState(body.state),
            required_work_done=body.required_work_done,
            supplied=supplied_to(exposure.recalled.get("intervention"), body.pattern_id),
            rubric=body.rubric,
            evidence=body.evidence,
            assessed_by=assessed_by,
            now=datetime.now(UTC),
        )
    except AssessmentRefused as e:
        raise _error(422, "VALIDATION_ERROR", str(e)) from e
    await store.record_assessment(assessment)
    return assessment.to_dict()


@router.get("/lessons/absence-rates")
async def absence_rates(
    request: Request,
    project_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> list[dict[str, Any]]:
    """``target_absence_rate`` per target, the supplied and unsupplied series apart, over the latest
    assessments of applicable, assessed exposures (§0.10). Observational, not a causal estimate."""
    return [
        {
            "pattern_id": r.pattern_id,
            "supplied": r.supplied,
            "absent": r.absent,
            "assessed": r.assessed,
            "not_applicable": r.not_applicable,
            "unassessed": r.unassessed,
            "rate": r.rate,
        }
        for r in target_absence_rates(await _store(request).list_assessments(project_id))
    ]
