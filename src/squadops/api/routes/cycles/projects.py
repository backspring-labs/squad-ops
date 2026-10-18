"""
Project API routes (SIP-0064 §9.1).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from squadops.api.cycle_schemas import (
    ProjectRegistrationRequest,
    ProjectRegistrationResponse,
    ProjectResponse,
)
from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.cycles.mapping import project_to_response
from squadops.api.runtime.deps import get_project_locator_policy, get_project_registry
from squadops.auth.models import Identity, Scope
from squadops.projects.registration import RegistrationRefused, prepare_registration

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def list_projects(request: Request) -> list[ProjectResponse]:

    registry = get_project_registry(request)
    projects = await registry.list_projects()
    return [project_to_response(p) for p in projects]


@router.post("", status_code=201)
async def register_project(
    request: Request,
    body: ProjectRegistrationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.ADMIN_WRITE)),
) -> ProjectRegistrationResponse:
    """Register an existing product (SIP-0112 FR-02, E.4.1), as ``REGISTERING`` until its source
    is proven reachable (E.4.2). Registering a product is the owner's act: ``admin:write`` (R6).
    A retry with the same key and body replays; the same key with another body is a conflict."""
    try:
        registration = prepare_registration(
            idempotency_key=body.idempotency_key,
            project_id=body.project_id,
            name=body.name,
            description=body.description,
            tags=body.tags,
            repo_uri=body.source.repo_uri,
            base_ref=body.source.base_ref,
            contribution_mode=body.source.contribution_mode,
            repository_root=body.source.repository_root,
            owner=body.ownership.owner,
            delegated_actions=body.ownership.delegated_actions,
            acceptance_policy_ref=body.ownership.acceptance_policy_ref,
            policy=get_project_locator_policy(request),
        )
    except RegistrationRefused as e:
        raise http_error(422, e.code, str(e), e.details or None) from e
    actor = identity.user_id if identity is not None else "anonymous"
    project, replayed = await get_project_registry(request).register_project(
        registration, actor=actor
    )
    return ProjectRegistrationResponse(
        project=project_to_response(project),
        idempotency_key=registration.idempotency_key,
        replayed=replayed,
    )


@router.get("/{project_id}", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_project(request: Request, project_id: str) -> ProjectResponse:

    registry = get_project_registry(request)
    project = await registry.get_project(project_id)
    return project_to_response(project)


@router.get(
    "/{project_id}/prd-content",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_scopes(Scope.CYCLES_READ))],
)
async def get_project_prd_content(request: Request, project_id: str) -> PlainTextResponse:
    """Read PRD file content for a project (SIP-0074 §3.5).

    Best-effort: returns 404 if prd_path is not configured or the file is not
    readable (e.g. containerized deployment where the PRD lives on the host).
    """

    registry = get_project_registry(request)
    project = await registry.get_project(project_id)

    if not project.prd_path:
        raise http_error(404, "PRD_NOT_FOUND", "No PRD file configured for this project")

    prd_path = Path(project.prd_path)
    if not prd_path.is_file():
        raise http_error(404, "PRD_NOT_FOUND", f"PRD file not found: {project.prd_path}")

    try:
        content = prd_path.read_text()
    except OSError as exc:
        raise http_error(
            404, "PRD_NOT_FOUND", f"PRD file not readable: {project.prd_path}"
        ) from exc

    return PlainTextResponse(content)
