"""A Project's goal set (SIP-0115 §4, §8.1; slice 1, #2884; slice 3, #2886).

Read with whatever reads a Project (``cycles:read``). The whole-document write (any edit, a
reorder included) is the owner's alone, with the scope that writes a Development Configuration,
``admin:write``: the crew never reorders (Q41).

Slice 3's actions are each a revision too, with who may do what from §6 and Q41 (ruled
2026-11-03): the owner (``admin:write``) may do each; the crew's supervisor seat
(``campaigns:supervise``) may add a candidate, and may promote, drop or split only within a
Campaign the owner started, named in the request. Triage reads, and nothing else (#1719).
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from squadops.api.cycle_schemas import (
    BacklogItemSplitRequest,
    CandidateDropRequest,
    CandidatePromotionRequest,
    CandidateRequest,
    GoalSetActionRequest,
    GoalSetRecordedResponse,
    GoalSetRevisionRequest,
    GoalSetRevisionResponse,
)
from squadops.api.errors import http_error
from squadops.api.middleware.auth import holds_scopes, require_scopes
from squadops.api.runtime.deps import (
    get_campaign_registry,
    get_goal_set_registry,
    get_project_registry,
)
from squadops.auth.models import Identity, Scope
from squadops.projects.goal_set import (
    BacklogItemNotFound,
    CandidateNotFound,
    GoalSetInvalid,
    GoalSetRevision,
    revise_goal_set,
)
from squadops.projects.goal_set_actions import (
    ActionWrite,
    Actor,
    BacklogItemInProgress,
    NotDelegated,
    record_candidate,
    record_drop,
    record_promotion,
    record_split,
)

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
        change=revision.change.to_document() if revision.change is not None else None,
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


# --- slice 3's actions (§5.4, §5.5a, §6, Q41) ---


def _actor(request: Request, identity: Identity | None) -> Actor:
    """Who acts, by the scope held: the owner (``admin:write``), or the crew's supervisor seat
    (``campaigns:supervise``). Anyone else is refused here, before the Project is read."""
    owner = holds_scopes(request, Scope.ADMIN_WRITE)
    if not owner and not holds_scopes(request, Scope.CAMPAIGNS_SUPERVISE):
        raise http_error(
            403,
            "FORBIDDEN",
            "acting on a goal set needs admin:write (the owner) or campaigns:supervise (the "
            "crew's supervisor seat, within a Campaign the owner started) (SIP-0115 §6)",
        )
    return Actor(identity.user_id if identity is not None else "anonymous", owner)


def _write(
    request: Request,
    identity: Identity | None,
    body: GoalSetActionRequest,
    *,
    campaign_id: str | None = None,
) -> ActionWrite:
    return ActionWrite(
        actor=_actor(request, identity),
        expected_revision=body.expected_revision,
        reason=body.reason,
        idempotency_key=body.idempotency_key,
        source_ref=body.source_ref,
        campaign_id=campaign_id,
    )


def _recorded(
    written: tuple[GoalSetRevision, bool], body: GoalSetActionRequest
) -> GoalSetRecordedResponse:
    revision, replayed = written
    return GoalSetRecordedResponse(
        revision=_revision(revision), idempotency_key=body.idempotency_key, replayed=replayed
    )


#: The actions' own refusals, in the envelope; the stores' (a stale revision, a reused key, an
#: unknown Project, goal set or Campaign) are the registered handlers'.
_REFUSALS: tuple[tuple[type[Exception], int, str], ...] = (
    (CandidateNotFound, 404, "CANDIDATE_NOT_FOUND"),
    (BacklogItemNotFound, 404, "BACKLOG_ITEM_NOT_FOUND"),
    (NotDelegated, 403, "NOT_DELEGATED"),
    (BacklogItemInProgress, 409, "BACKLOG_ITEM_IN_PROGRESS"),
)


def _refused(e: Exception) -> HTTPException:
    if isinstance(e, GoalSetInvalid):
        return http_error(422, "GOAL_SET_INVALID", str(e), {"field": e.field})
    for exc_type, status, code in _REFUSALS:
        if isinstance(e, exc_type):
            return http_error(status, code, str(e))
    raise e


@router.post("/{project_id}/goal-set/candidates", status_code=201)
async def add_candidate(
    request: Request,
    project_id: str,
    body: CandidateRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CYCLES_READ)),
) -> GoalSetRecordedResponse:
    """Add a candidate (§5.4): what the crew or the owner found, which nobody has ordered yet.
    The next revision, with the acting principal as its author."""
    try:
        written = await record_candidate(
            project_id,
            body.candidate,
            _write(request, identity, body),
            projects=get_project_registry(request),
            goal_sets=get_goal_set_registry(request),
        )
    except (GoalSetInvalid, CandidateNotFound) as e:
        raise _refused(e) from e
    return _recorded(written, body)


@router.post("/{project_id}/goal-set/candidates/{candidate_id}/promote", status_code=201)
async def promote_candidate(
    request: Request,
    project_id: str,
    candidate_id: str,
    body: CandidatePromotionRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CYCLES_READ)),
) -> GoalSetRecordedResponse:
    """Promote a candidate into the backlog (§5.4), keeping its id: at ``position``, or the end.
    The owner may put it anywhere; the crew, within a Campaign the owner started (``campaign_id``),
    appends (Q41): ``403 NOT_DELEGATED`` otherwise."""
    try:
        written = await record_promotion(
            project_id,
            candidate_id,
            serves=body.serves,
            position=body.position,
            write=_write(request, identity, body, campaign_id=body.campaign_id),
            projects=get_project_registry(request),
            goal_sets=get_goal_set_registry(request),
            campaigns=get_campaign_registry(request),
        )
    except (GoalSetInvalid, CandidateNotFound, NotDelegated) as e:
        raise _refused(e) from e
    return _recorded(written, body)


@router.post("/{project_id}/goal-set/candidates/{candidate_id}/drop", status_code=201)
async def drop_candidate(
    request: Request,
    project_id: str,
    candidate_id: str,
    body: CandidateDropRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CYCLES_READ)),
) -> GoalSetRecordedResponse:
    """Drop a candidate (§5.4), with the reason. Who may is as for a promotion."""
    try:
        written = await record_drop(
            project_id,
            candidate_id,
            write=_write(request, identity, body, campaign_id=body.campaign_id),
            projects=get_project_registry(request),
            goal_sets=get_goal_set_registry(request),
            campaigns=get_campaign_registry(request),
        )
    except (GoalSetInvalid, CandidateNotFound, NotDelegated) as e:
        raise _refused(e) from e
    return _recorded(written, body)


@router.post("/{project_id}/goal-set/backlog/{item_id}/split", status_code=201)
async def split_backlog_item(
    request: Request,
    project_id: str,
    item_id: str,
    body: BacklogItemSplitRequest,
    identity: Identity | None = Depends(require_scopes(Scope.CYCLES_READ)),
) -> GoalSetRecordedResponse:
    """Split a backlog item (§5.5a): the parts take its place, in order, inheriting what it
    served unless they say otherwise, and start ``pending``; the revision names them. Refused
    (``409 BACKLOG_ITEM_IN_PROGRESS``) while a live Campaign reads the item ``proposed`` or
    ``in_increment``. Who may is as for a promotion."""
    try:
        written = await record_split(
            project_id,
            item_id,
            body.into,
            write=_write(request, identity, body, campaign_id=body.campaign_id),
            projects=get_project_registry(request),
            goal_sets=get_goal_set_registry(request),
            campaigns=get_campaign_registry(request),
        )
    except (GoalSetInvalid, BacklogItemNotFound, NotDelegated, BacklogItemInProgress) as e:
        raise _refused(e) from e
    return _recorded(written, body)


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
