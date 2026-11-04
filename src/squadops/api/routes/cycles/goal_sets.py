"""A Project's goal set (SIP-0115 §4, §8.1, slice 1, #2884).

Read with whatever reads a Project (``cycles:read``). Written by the owner alone in this slice
(§6: the goal and expected results are the owner's), with the scope that writes a Development
Configuration, ``admin:write``. The crew's principals hold neither write scope.
"""

from fastapi import APIRouter, Depends, Request

from squadops.api.cycle_schemas import (
    GoalSetRecordedResponse,
    GoalSetRevisionRequest,
    GoalSetRevisionResponse,
)
from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.runtime.deps import get_goal_set_registry, get_project_registry
from squadops.auth.models import Identity, Scope
from squadops.projects.goal_set import GoalSetInvalid, GoalSetRevision, revise_goal_set

router = APIRouter(prefix="/api/v1/projects", tags=["goal-sets"])


def _revision(revision: GoalSetRevision) -> GoalSetRevisionResponse:
    return GoalSetRevisionResponse(
        project_id=revision.project_id,
        revision=revision.revision,
        author=revision.author,
        reason=revision.reason,
        source_ref=revision.source_ref,
        created_at=revision.created_at,
        goal_set=revision.goal_set.to_document(),
    )


@router.post("/{project_id}/goal-set/revisions", status_code=201)
async def write_goal_set_revision(
    request: Request,
    project_id: str,
    body: GoalSetRevisionRequest,
    identity: Identity | None = Depends(require_scopes(Scope.ADMIN_WRITE)),
) -> GoalSetRecordedResponse:
    """Write the Project's next goal-set revision: any edit, a reorder included. A retry with
    the same key and body replays; the same key with another body is a conflict."""
    try:
        revision, replayed = await revise_goal_set(
            project_id,
            body.goal_set,
            expected_revision=body.expected_revision,
            reason=body.reason,
            source_ref=body.source_ref,
            projects=get_project_registry(request),
            goal_sets=get_goal_set_registry(request),
            author=identity.user_id if identity is not None else "anonymous",
            idempotency_key=body.idempotency_key,
        )
    except GoalSetInvalid as e:
        raise http_error(422, "GOAL_SET_INVALID", str(e), {"field": e.field}) from e
    return GoalSetRecordedResponse(
        revision=_revision(revision), idempotency_key=body.idempotency_key, replayed=replayed
    )


@router.get("/{project_id}/goal-set", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_goal_set(request: Request, project_id: str) -> GoalSetRevisionResponse:
    """The Project's active goal set: its latest revision (Q44)."""
    await get_project_registry(request).get_project(project_id)
    return _revision(await get_goal_set_registry(request).get_revision(project_id))


@router.get(
    "/{project_id}/goal-set/revisions",
    dependencies=[Depends(require_scopes(Scope.CYCLES_READ))],
)
async def list_goal_set_revisions(
    request: Request, project_id: str
) -> list[GoalSetRevisionResponse]:
    """Every revision of the Project's goal set, newest first."""
    await get_project_registry(request).get_project(project_id)
    revisions = await get_goal_set_registry(request).list_revisions(project_id)
    return [_revision(r) for r in revisions]


@router.get(
    "/{project_id}/goal-set/revisions/{revision}",
    dependencies=[Depends(require_scopes(Scope.CYCLES_READ))],
)
async def get_goal_set_revision(
    request: Request, project_id: str, revision: int
) -> GoalSetRevisionResponse:
    """One revision, as it was written: revisions are never edited."""
    await get_project_registry(request).get_project(project_id)
    return _revision(await get_goal_set_registry(request).get_revision(project_id, revision))
