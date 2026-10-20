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

import logging
from collections.abc import Mapping
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from squadops.api.memory_schemas import (
    AbsenceRateResponse,
    AnnotationRequest,
    AnnotationResponse,
    AnnotationReviewRequest,
    ApplicabilityDTO,
    ApprovalResponse,
    AssessmentRequest,
    AssessmentResponse,
    ExposureResponse,
    LessonApprovalRequest,
    LessonDraftRequest,
    LessonResponse,
    ObservationResponse,
    RevocationRequest,
    RevocationResponse,
    SuppliedTogetherResponse,
)
from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.memory.held_units import next_step, running_and_finished, unit_row
from squadops.api.runtime.deps import get_memory_records, get_memory_store
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
from squadops.memory.exposures import Exposure
from squadops.memory.lessons import (
    Applicability,
    Approval,
    PatternRevision,
    RecallDisposition,
)
from squadops.memory.record_uses import handed_instructions, withdrawn_uses
from squadops.memory.records import MemoryRecord

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["memory"])
logger = logging.getLogger(__name__)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"error": {"code": code, "message": message, "details": None}})


def _store(request: Request):

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


def _lesson(revision: PatternRevision, approvals: list[Approval]) -> LessonResponse:
    return LessonResponse.model_validate(
        {
            "revision_id": revision.revision_id,
            **revision.to_dict(),
            "approvals": [a.to_dict() for a in approvals if a.revision_id == revision.revision_id],
        }
    )


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
) -> list[LessonResponse]:
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
) -> LessonResponse:
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
) -> SuppliedTogetherResponse:
    """The approved lessons, in force now, that a task inside the revision's applicability could be
    supplied beside it: the set the auditor's combined check covers before approval (§0.6)."""
    store = _store(request)
    revision = await _revision(store, project_id, revision_id)
    revisions = await store.list_revisions(project_id)
    return SuppliedTogetherResponse.model_validate(
        {
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
    )


@router.post("/lessons/{revision_id}/approvals", status_code=201)
async def approve_lesson(
    request: Request,
    project_id: str,
    revision_id: str,
    body: LessonApprovalRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_APPROVE)),
) -> ApprovalResponse:
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
    return ApprovalResponse.model_validate(approval.to_dict())


@router.post("/approvals/{approval_id}/revocation")
async def revoke_lesson(
    request: Request,
    project_id: str,
    approval_id: str,
    body: RevocationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_APPROVE)),
) -> RevocationResponse:
    """The owner's revocation. Units admitted afterwards pin without it; the answer names the
    running units that hold it, and apart from them the finished units that ran with it (§0.7,
    D9; #2210)."""
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
    live, finished = await running_and_finished(
        request, await store.list_snapshots_holding(approval_id)
    )
    return RevocationResponse.model_validate(
        {
            "approval": revoked.to_dict(),
            "units_holding_it": [unit_row(s) for s in live],
            "finished_units_holding_it": [unit_row(s) for s in finished],
            "next": next_step(live, finished, rule="SIP-0110 §0.7"),
        }
    )


@router.get("/observations")
async def list_observations(
    request: Request,
    project_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> list[ObservationResponse]:
    """The project's observations, each as projected, with its annotations and the classification
    memory reads for it: the latest reviewed annotation's, or the projected one (§0.4)."""
    store = _store(request)
    annotations = await store.list_annotations(project_id)
    return [
        ObservationResponse.model_validate(
            {
                **o.to_dict(),
                "annotations": [a.to_dict() for a in annotations if a.source_id == o.source_id],
                "effective_classification": effective_classification(o, annotations).to_dict(),
            }
        )
        for o in await store.list_observations(project_id)
    ]


@router.post("/observations/{source_id}/annotations", status_code=201)
async def annotate_observation(
    request: Request,
    project_id: str,
    source_id: str,
    body: AnnotationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_DRAFT)),
) -> AnnotationResponse:
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
    return AnnotationResponse.model_validate(annotation.to_dict())


@router.post("/annotations/{annotation_id}/review")
async def review_annotation(
    request: Request,
    project_id: str,
    annotation_id: str,
    body: AnnotationReviewRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_APPROVE)),
) -> AnnotationResponse:
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
    return AnnotationResponse.model_validate(reviewed.to_dict())


@router.get("/exposures")
async def list_exposures(
    request: Request,
    project_id: str,
    run_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> list[ExposureResponse]:
    """A run's exposures, each with the latest assessment of each target (§0.8 step 7, §0.10), and
    the instructions it was handed that are withdrawn now, marked (Appendix A §3.8)."""
    store = _store(request)
    read = latest(await store.list_assessments(project_id))
    exposures = [e for e in await store.list_exposures(run_id) if e.query.project_id == project_id]
    records = await _records_by_id(request, project_id, exposures)
    return [
        ExposureResponse.model_validate(
            {
                **e.to_dict(),
                "assessments": [
                    a.to_dict()
                    for (exposure_id, _), a in read.items()
                    if exposure_id == e.exposure_id
                ],
                "withdrawn_instructions": _withdrawn(e, records),
            }
        )
        for e in exposures
    ]


async def _records_by_id(
    request: Request, project_id: str, exposures: list[Exposure]
) -> Mapping[str, MemoryRecord] | None:
    """The project's records by id, read only when an exposure was handed an instruction; ``None``
    when they can't be read, so a mark that couldn't be checked never reads as "none withdrawn"."""
    if not any(handed_instructions(e) for e in exposures):
        return {}
    records = get_memory_records(request)
    try:
        if records is None:
            raise LookupError("the memory records' store is not configured")
        return {r.record_id: r for r in await records.list_project(project_id)}
    except Exception:  # noqa: BLE001 — unread is said, never read as unwithdrawn
        logger.warning("memory_exposure_records_unread project=%s", project_id, exc_info=True)
        return None


def _withdrawn(e: Exposure, records: Mapping[str, MemoryRecord] | None) -> list[dict] | None:
    if records is None:
        return None if handed_instructions(e) else []
    return [
        {**vars(w), "withdrawn_at": w.withdrawn_at.isoformat()} for w in withdrawn_uses(e, records)
    ]


@router.post("/exposures/{exposure_id}/assessments", status_code=201)
async def assess_exposure(
    request: Request,
    project_id: str,
    exposure_id: str,
    body: AssessmentRequest,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_DRAFT)),
) -> AssessmentResponse:
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
            context_withheld=exposure.disposition == RecallDisposition.CONTEXT_NONE,
        )
    except AssessmentRefused as e:
        raise _error(422, "VALIDATION_ERROR", str(e)) from e
    await store.record_assessment(assessment)
    return AssessmentResponse.model_validate(assessment.to_dict())


@router.get("/lessons/absence-rates")
async def absence_rates(
    request: Request,
    project_id: str,
    identity: Identity | None = Depends(require_scopes(Scope.MEMORY_READ)),
) -> list[AbsenceRateResponse]:
    """``target_absence_rate`` per target, the supplied and unsupplied series apart, over the latest
    assessments of applicable, assessed exposures (§0.10). Observational, not a causal estimate."""
    return [
        AbsenceRateResponse.model_validate(
            {
                "pattern_id": r.pattern_id,
                "supplied": r.supplied,
                "absent": r.absent,
                "assessed": r.assessed,
                "not_applicable": r.not_applicable,
                "unassessed": r.unassessed,
                "rate": r.rate,
            }
        )
        for r in target_absence_rates(await _store(request).list_assessments(project_id))
    ]
