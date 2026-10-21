"""Sandbox service HTTP surface (SIP-0102 §4.3 — phase 102.1 slice d).

The narrow authenticated API over the transport-agnostic ``SandboxService``
core. Conforms to the repo API lanes: authenticated resources under
``/api/v1``, ``/health`` as the unauthenticated read-only probe, errors in
the resource-lane envelope ``{"error": {code, message, details}}``.

Typed operations only (§7 item 2): the operations endpoint dispatches an
explicit table keyed by ``OperationName`` — an unknown operation is a 400,
never a shell.

Auth is the interim shared-secret bearer (constant-time compared); the
Keycloak service-identity (#326) upgrade rides 102.3 when runtime-api
becomes the caller.
"""

from __future__ import annotations

import hmac

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from squadops.campaigns.seed_plan import SeedPlan
from squadops.sandbox.evidence import result_to_dict
from squadops.sandbox.models import (
    OperationName,
    RevisionOrigin,
    WorkspaceRevision,
    decode_binary,
    wire_files,
)
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import (
    AlreadySeededError,
    StaleBaseRevisionError,
    WorkspaceEscapeError,
    WorkspaceStoreError,
)
from squadops.scenarios.runner import DeclaredStart


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": None}},
    )


class SeedRequest(BaseModel):
    files: dict[str, str]
    #: X-2 (#2420): each file that isn't UTF-8 text, base64-encoded. A text-only seed
    #: sends none, so its request is what it was before bytes were carried.
    binary_files: dict[str, str] = Field(default_factory=dict)
    #: X-2 (#2420): the files to seed with their executable bit set.
    executable: list[str] = Field(default_factory=list)
    origin: str = RevisionOrigin.SCAFFOLD_SEED
    created_at: str | None = None


class EvaluationRequest(BaseModel):
    """SIP-0113 §4.1 (#2414): an evaluated tree, by its FileTree.identity, and the scenarios to
    run against it. The steps and the evaluation secrets are held for the call, never written."""

    tree: dict[str, str]
    binary_tree: dict[str, str] = Field(default_factory=dict)
    executable: list[str] = Field(default_factory=list)
    tree_identity: str
    stack: str | None = None
    declared: dict | None = None
    scenarios: list[dict]
    environment: dict[str, str] = Field(default_factory=dict)
    #: The declared pages Lighthouse and axe measure (SIP-0113 §4.2, #2416). Required: a client
    #: that names none says so with ``[]``, never by leaving it out.
    pages: list[str]
    #: §10j, §10n (#2562): the seeded reading's plan (``campaigns.seed_plan``), or none.
    seed: dict | None = None


class OperationRequest(BaseModel):
    operation: str
    revision: dict
    params: dict = Field(default_factory=dict)


async def _op_install(service: SandboxService, revision: WorkspaceRevision, params: dict):
    return await service.install_dependencies(revision=revision)


async def _op_build(service: SandboxService, revision: WorkspaceRevision, params: dict):
    return await service.build_frontend(revision=revision)


async def _op_tests(service: SandboxService, revision: WorkspaceRevision, params: dict):
    return await service.run_backend_tests(revision=revision)


async def _op_start(service: SandboxService, revision: WorkspaceRevision, params: dict):
    return await service.start_application(revision=revision)


async def _op_stop(service: SandboxService, revision: WorkspaceRevision, params: dict):
    return await service.stop_application(
        revision=revision, cleanup_handle=params["cleanup_handle"]
    )


async def _op_probe(service: SandboxService, revision: WorkspaceRevision, params: dict):
    return await service.probe_http_endpoint(
        revision=revision,
        probe_id=params["probe_id"],
        method=params.get("method", "GET"),
        path=params["path"],
        expected_status=params.get("expected_status"),
    )


async def _op_patch(service: SandboxService, revision: WorkspaceRevision, params: dict):
    try:
        binary = decode_binary(params.get("binary_files", {}), alongside=params["files"])
        return await service.apply_workspace_patch(
            base=revision,
            files={**params["files"], **binary},
            origin=params.get("origin", RevisionOrigin.AGENT_PATCH),
        )
    except ValueError as e:
        # The caller's error, not the service's: an unknown origin, a patch that changes
        # nothing (a revision can't be its own parent), or bytes that don't decode. Each
        # answered 500 before, where a seed's refusal answers 400.
        raise _error(400, "INVALID_PATCH", str(e)) from e


async def _op_declared_command(service: SandboxService, revision: WorkspaceRevision, params: dict):
    try:
        return await service.run_declared_command(
            revision=revision,
            command=tuple(params["command"]),
            working_dir=params.get("working_dir", "."),
            setup=tuple(tuple(step) for step in params.get("setup", ())),
            timeout_seconds=params.get("timeout_seconds"),
            findings_reader=params.get("findings_reader"),
        )
    except (TypeError, ValueError) as e:
        # A declaration the sandbox can't run as given is the caller's error: an empty argv,
        # a non-string argument, a non-positive timeout or a findings reader it doesn't have.
        raise _error(400, "INVALID_COMMAND", str(e)) from e


# The typed-operations table (§7 item 2): membership here IS the API surface.
_OPERATIONS = {
    OperationName.INSTALL_DEPENDENCIES: _op_install,
    OperationName.BUILD_FRONTEND: _op_build,
    OperationName.RUN_BACKEND_TESTS: _op_tests,
    OperationName.START_APPLICATION: _op_start,
    OperationName.STOP_APPLICATION: _op_stop,
    OperationName.PROBE_HTTP_ENDPOINT: _op_probe,
    OperationName.APPLY_WORKSPACE_PATCH: _op_patch,
    # SIP-0102 §11d: the one operation whose argv the caller supplies, from a product's own
    # declaration (X-3a, #2421), run in a disposable copy, never the live tree.
    OperationName.RUN_DECLARED_COMMAND: _op_declared_command,
}


async def _handle_seed(service: SandboxService, cycle_id: str, body: SeedRequest) -> dict:
    try:
        binary = decode_binary(body.binary_files, alongside=body.files)
        revision = await service.seed_workspace(
            cycle_id,
            {**body.files, **binary},
            origin=body.origin,
            executable=body.executable,
            created_at=body.created_at,
        )
    except AlreadySeededError as e:
        raise _error(409, "ALREADY_SEEDED", str(e)) from e
    except (WorkspaceEscapeError, WorkspaceStoreError, ValueError) as e:
        raise _error(400, "INVALID_SEED", str(e)) from e
    return revision.to_dict()


async def _handle_release(service: SandboxService, cycle_id: str) -> Response:
    """#2473: the consumer releases what it seeded once it has recorded what it needs."""
    try:
        await service.release_workspace(cycle_id)
    except WorkspaceStoreError as e:
        raise _error(400, "INVALID_WORKSPACE", str(e)) from e
    return Response(status_code=204)


async def _handle_evaluation(service: SandboxService, body: EvaluationRequest) -> dict:
    """SIP-0113 §4.1 (#2414): one evaluated tree, started and evaluated by the scenario runner."""
    runner = service.scenario_runner
    if runner is None:
        raise _error(503, "RUNNER_UNAVAILABLE", "this sandbox runs no scenario runner")
    try:
        binary = decode_binary(body.binary_tree, alongside=body.tree)
        result = await runner.evaluate_tree(
            tree={**body.tree, **binary},
            tree_identity=body.tree_identity,
            executable=body.executable,
            stack=body.stack,
            declared=DeclaredStart.from_dict(body.declared) if body.declared else None,
            scenarios=body.scenarios,
            environment=body.environment,
            pages=body.pages,
            **({"seed": SeedPlan.from_dict(body.seed)} if body.seed else {}),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise _error(400, "INVALID_EVALUATION", str(e)) from e
    return result.as_dict()


async def _handle_read(service: SandboxService, cycle_id: str, revision_id: str) -> dict:
    """A pinned revision's content (contract 3; SIP-0112's E.4.3 captures a change back from it),
    in the seed's wire form: text under ``files``, the rest base64 under ``binary_files``."""
    revision = service.get_revision(cycle_id, revision_id)
    if revision is None:
        raise _error(404, "REVISION_NOT_FOUND", f"cycle {cycle_id} holds no revision {revision_id}")
    try:
        content = await service.read_workspace_revision(revision)
    except StaleBaseRevisionError as e:
        raise _error(409, "STALE_BASE_REVISION", str(e)) from e
    return {
        "revision": content.revision.to_dict(),
        **wire_files(content.files),
        "executable": sorted(content.executable),
    }


async def _handle_operate(service: SandboxService, cycle_id: str, body: OperationRequest) -> dict:
    try:
        revision = WorkspaceRevision.from_dict(body.revision)
    except (KeyError, ValueError) as e:
        raise _error(400, "INVALID_REVISION", str(e)) from e
    if revision.cycle_id != cycle_id:
        raise _error(400, "CYCLE_MISMATCH", "revision does not belong to the addressed cycle")
    handler = _OPERATIONS.get(body.operation)
    if handler is None:
        raise _error(
            400,
            "UNKNOWN_OPERATION",
            f"'{body.operation}' is not a typed operation (typed operations only)",
        )
    try:
        result = await handler(service, revision, body.params)
    except KeyError as e:
        raise _error(400, "MISSING_PARAM", f"missing operation param: {e}") from e
    except StaleBaseRevisionError as e:
        raise _error(409, "STALE_BASE_REVISION", str(e)) from e
    except (WorkspaceEscapeError, WorkspaceStoreError) as e:
        raise _error(400, "WORKSPACE_VIOLATION", str(e)) from e
    return result_to_dict(result)


def create_app(service: SandboxService, *, service_token: str) -> FastAPI:
    if not service_token:
        raise ValueError(
            "sandbox service requires a service token "
            "(SQUADOPS__SANDBOX__SERVICE_TOKEN) — it never runs unauthenticated"
        )

    app = FastAPI(title="SquadOps Sandbox Service", docs_url=None, redoc_url=None)

    @app.exception_handler(HTTPException)
    async def _envelope_handler(request: Request, exc: HTTPException) -> JSONResponse:
        # Emit the flat resource-lane envelope, not FastAPI's {"detail": ...}.
        detail = exc.detail
        if not (isinstance(detail, dict) and "error" in detail):
            detail = {"error": {"code": "HTTP_ERROR", "message": str(detail), "details": None}}
        return JSONResponse(status_code=exc.status_code, content=detail)

    # Header(default=...) not Annotated[..., Header()]: under the LOCKED pair
    # (fastapi 0.104.1 + pydantic 2.12.5, requirements/api.lock) the Annotated
    # form crashes route registration (FieldInfo has no .in_) — the service
    # container could never boot. The dev venv runs a newer fastapi where both
    # forms work, so only the container image manifests it (Spark shakedown
    # finding #3, 2026-07-28; minimal repro in the runtime-api container).
    def require_identity(authorization: str | None = Header(default=None)) -> None:
        expected = f"Bearer {service_token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise _error(401, "UNAUTHENTICATED", "valid service bearer token required")

    @app.get("/health")
    async def health() -> dict:
        # Environment facts ride the probe (102.2c): the cycle-create
        # preflight and doctor reconcile against them.
        return {
            "status": "ok",
            "service": "sandbox",
            "environment": await service.environment_report(),
        }

    @app.post("/api/v1/evaluations", dependencies=[Depends(require_identity)])
    async def evaluate(body: EvaluationRequest) -> dict:
        return await _handle_evaluation(service, body)

    @app.post(
        "/api/v1/workspaces/{cycle_id}/seed",
        dependencies=[Depends(require_identity)],
    )
    async def seed(cycle_id: str, body: SeedRequest) -> dict:
        return await _handle_seed(service, cycle_id, body)

    @app.delete(
        "/api/v1/workspaces/{cycle_id}",
        status_code=204,
        response_class=Response,
        dependencies=[Depends(require_identity)],
    )
    async def release(cycle_id: str) -> Response:
        return await _handle_release(service, cycle_id)

    @app.post(
        "/api/v1/workspaces/{cycle_id}/operations",
        dependencies=[Depends(require_identity)],
    )
    async def operate(cycle_id: str, body: OperationRequest) -> dict:
        return await _handle_operate(service, cycle_id, body)

    @app.get(
        "/api/v1/workspaces/{cycle_id}/revisions/{revision_id}",
        dependencies=[Depends(require_identity)],
    )
    async def read_revision(cycle_id: str, revision_id: str) -> dict:
        return await _handle_read(service, cycle_id, revision_id)

    return app
