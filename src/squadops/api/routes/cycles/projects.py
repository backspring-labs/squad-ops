"""
Project API routes (SIP-0064 §9.1).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from squadops.api.cycle_schemas import (
    ContributionRequest,
    ContributionResponse,
    DevelopmentConfigurationRecordedResponse,
    DevelopmentConfigurationRequest,
    DevelopmentConfigurationResponse,
    InheritedBaselineRequest,
    InheritedBaselineResponse,
    ProjectRegistrationRequest,
    ProjectRegistrationResponse,
    ProjectResponse,
    ProjectValidationRequest,
)
from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.routes.cycles.mapping import project_to_response
from squadops.api.runtime.deps import (
    get_project_locator_policy,
    get_project_registry,
    get_review_request_tokens,
    get_review_requests,
    get_sandbox_client,
    get_source_repository,
)
from squadops.auth.models import Identity, Scope
from squadops.ports.projects.review_request import ReviewRequestFailed
from squadops.projects.configuration import configure_project
from squadops.projects.contribution import ContributionRefused, contribute
from squadops.projects.development_configuration import (
    ConfigurationInvalid,
    DevelopmentConfiguration,
)
from squadops.projects.models import SourceUnavailable
from squadops.projects.registration import RegistrationRefused, prepare_registration
from squadops.projects.validation import validate_project
from squadops.projects.workspaces import SandboxUnavailable, capture_inherited_baseline

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


@router.post("/{project_id}/validate")
async def validate_registered_project(
    request: Request,
    project_id: str,
    body: ProjectValidationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.ADMIN_WRITE)),
) -> ProjectRegistrationResponse:
    """Reach a registered Project's source through the managed clone (SIP-0112 E.4.2): READY
    at the base ref's commit, or FAILED_REGISTRATION with the reason. A failure is an answer,
    not an error: the Project records it, and a retry validates again."""
    project, replayed = await validate_project(
        project_id,
        registry=get_project_registry(request),
        repository=get_source_repository(request),
        actor=identity.user_id if identity is not None else "anonymous",
        idempotency_key=body.idempotency_key,
    )
    return ProjectRegistrationResponse(
        project=project_to_response(project),
        idempotency_key=body.idempotency_key,
        replayed=replayed,
    )


def _configuration(configuration: DevelopmentConfiguration) -> DevelopmentConfigurationResponse:
    return DevelopmentConfigurationResponse(
        project_id=configuration.project_id,
        revision=configuration.revision,
        document=configuration.to_document(),
    )


@router.post("/{project_id}/development-configurations", status_code=201)
async def record_development_configuration(
    request: Request,
    project_id: str,
    body: DevelopmentConfigurationRequest,
    identity: Identity | None = Depends(require_scopes(Scope.ADMIN_WRITE)),
) -> DevelopmentConfigurationRecordedResponse:
    """Record the next revision of a READY Project's Development Configuration (SIP-0112 E.4.2):
    its checks and start declaration, validated, with the repository's instruction sources at
    the baseline commit."""
    try:
        configuration, replayed = await configure_project(
            project_id,
            body.model_dump(include={"technical", "quality"}, exclude_none=True),
            expected_revision=body.expected_revision,
            registry=get_project_registry(request),
            repository=get_source_repository(request),
            actor=identity.user_id if identity is not None else "anonymous",
            idempotency_key=body.idempotency_key,
        )
    except ConfigurationInvalid as e:
        raise http_error(422, "CONFIGURATION_INVALID", str(e), {"field": e.field}) from e
    return DevelopmentConfigurationRecordedResponse(
        configuration=_configuration(configuration),
        idempotency_key=body.idempotency_key,
        replayed=replayed,
    )


@router.get(
    "/{project_id}/development-configuration",
    dependencies=[Depends(require_scopes(Scope.CYCLES_READ))],
)
async def get_current_development_configuration(
    request: Request, project_id: str
) -> DevelopmentConfigurationResponse:
    """The Project's current Development Configuration revision."""
    return _configuration(
        await get_project_registry(request).get_development_configuration(project_id)
    )


@router.get(
    "/{project_id}/development-configurations/{revision}",
    dependencies=[Depends(require_scopes(Scope.CYCLES_READ))],
)
async def get_development_configuration_revision(
    request: Request, project_id: str, revision: int
) -> DevelopmentConfigurationResponse:
    """One revision, as a unit pinned it: revisions are never edited."""
    return _configuration(
        await get_project_registry(request).get_development_configuration(project_id, revision)
    )


@router.post("/{project_id}/baselines", status_code=201)
async def capture_baseline(
    request: Request,
    project_id: str,
    body: InheritedBaselineRequest,
    identity: Identity | None = Depends(require_scopes(Scope.ADMIN_WRITE)),
) -> InheritedBaselineResponse:
    """Run the product's own checks on its pinned, unmodified baseline in the sandbox, and record
    what happened (SIP-0112 FR-20, E.4.2): PASS and FAIL attributed inherited, UNVERIFIED with
    the reason a check couldn't run."""
    try:
        baseline, replayed = await capture_inherited_baseline(
            project_id,
            registry=get_project_registry(request),
            repository=get_source_repository(request),
            sandbox=get_sandbox_client(request),
            actor=identity.user_id if identity is not None else "anonymous",
            idempotency_key=body.idempotency_key,
        )
    except SandboxUnavailable as e:
        raise http_error(503, "SANDBOX_UNAVAILABLE", str(e)) from e
    return InheritedBaselineResponse(
        project_id=project_id, document=baseline.to_document(), replayed=replayed
    )


@router.get("/{project_id}/baseline", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))])
async def get_baseline(request: Request, project_id: str) -> InheritedBaselineResponse:
    """The Project's latest inherited baseline."""
    baseline = await get_project_registry(request).get_inherited_baseline(project_id)
    return InheritedBaselineResponse(project_id=project_id, document=baseline.to_document())


@router.post("/{project_id}/contributions", status_code=201)
async def contribute_change(
    request: Request,
    project_id: str,
    body: ContributionRequest,
    identity: Identity | None = Depends(require_scopes(Scope.ADMIN_WRITE)),
) -> ContributionResponse:
    """Contribute a run's verified, captured change through the Project's own process (SIP-0112
    FR-06, E.4.3), and record it pending. The owner's act: nothing leaves the deploy without
    it. ``review_request`` pushes the branch and opens the pull request; ``patch_export``
    records the run's patch as the contribution."""
    try:
        contribution, replayed = await contribute(
            project_id,
            body.cycle_id,
            body.run_id,
            registry=get_project_registry(request),
            repository=get_source_repository(request),
            forge=get_review_requests(request),
            tokens=(
                {project_id: body.token.get_secret_value()}
                if body.token is not None
                else get_review_request_tokens(request)
            ),
            actor=identity.user_id if identity is not None else "anonymous",
            idempotency_key=body.idempotency_key,
        )
    except ContributionRefused as e:
        raise http_error(409, "CONTRIBUTION_REFUSED", str(e)) from e
    except (SourceUnavailable, ReviewRequestFailed) as e:
        raise http_error(502, "CONTRIBUTION_FAILED", str(e)) from e
    return ContributionResponse(contribution=contribution.to_document(), replayed=replayed)


@router.get(
    "/{project_id}/contributions", dependencies=[Depends(require_scopes(Scope.CYCLES_READ))]
)
async def list_contributions(request: Request, project_id: str) -> list[ContributionResponse]:
    """A Project's contributions, oldest first: pending until the product takes them."""
    contributions = await get_project_registry(request).contributions(project_id)
    return [ContributionResponse(contribution=c.to_document()) for c in contributions]


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
