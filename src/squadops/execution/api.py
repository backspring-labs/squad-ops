"""Execution service HTTP surface (SIP-0102 §4.3 — phase 102.1 slice d).

The narrow authenticated API over the transport-agnostic ``ExecutionService``
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
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from squadops.execution.evidence import result_to_dict
from squadops.execution.models import (
    OperationName,
    RevisionOrigin,
    WorkspaceRevision,
)
from squadops.execution.service import ExecutionService
from squadops.execution.workspace import (
    AlreadySeededError,
    StaleBaseRevisionError,
    WorkspaceEscapeError,
    WorkspaceStoreError,
)


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": None}},
    )


class SeedRequest(BaseModel):
    files: dict[str, str]
    origin: str = RevisionOrigin.SCAFFOLD_SEED
    created_at: str | None = None


class OperationRequest(BaseModel):
    operation: str
    revision: dict
    params: dict = Field(default_factory=dict)


async def _op_install(service: ExecutionService, revision: WorkspaceRevision, params: dict):
    return await service.install_dependencies(revision=revision)


async def _op_build(service: ExecutionService, revision: WorkspaceRevision, params: dict):
    return await service.build_frontend(revision=revision)


async def _op_tests(service: ExecutionService, revision: WorkspaceRevision, params: dict):
    return await service.run_backend_tests(revision=revision)


async def _op_start(service: ExecutionService, revision: WorkspaceRevision, params: dict):
    return await service.start_application(revision=revision)


async def _op_stop(service: ExecutionService, revision: WorkspaceRevision, params: dict):
    return await service.stop_application(
        revision=revision, cleanup_handle=params["cleanup_handle"]
    )


async def _op_probe(service: ExecutionService, revision: WorkspaceRevision, params: dict):
    return await service.probe_http_endpoint(
        revision=revision,
        probe_id=params["probe_id"],
        method=params.get("method", "GET"),
        path=params["path"],
        expected_status=params.get("expected_status"),
    )


async def _op_patch(service: ExecutionService, revision: WorkspaceRevision, params: dict):
    return await service.apply_workspace_patch(
        base=revision,
        files=params["files"],
        origin=params.get("origin", RevisionOrigin.AGENT_PATCH),
    )


# The typed-operations table (§7 item 2): membership here IS the API surface.
_OPERATIONS = {
    OperationName.INSTALL_DEPENDENCIES: _op_install,
    OperationName.BUILD_FRONTEND: _op_build,
    OperationName.RUN_BACKEND_TESTS: _op_tests,
    OperationName.START_APPLICATION: _op_start,
    OperationName.STOP_APPLICATION: _op_stop,
    OperationName.PROBE_HTTP_ENDPOINT: _op_probe,
    OperationName.APPLY_WORKSPACE_PATCH: _op_patch,
}


async def _handle_seed(service: ExecutionService, cycle_id: str, body: SeedRequest) -> dict:
    try:
        revision = service.seed_workspace(
            cycle_id, body.files, origin=body.origin, created_at=body.created_at
        )
    except AlreadySeededError as e:
        raise _error(409, "ALREADY_SEEDED", str(e)) from e
    except (WorkspaceEscapeError, WorkspaceStoreError, ValueError) as e:
        raise _error(400, "INVALID_SEED", str(e)) from e
    return revision.to_dict()


async def _handle_operate(service: ExecutionService, cycle_id: str, body: OperationRequest) -> dict:
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


def create_app(service: ExecutionService, *, service_token: str) -> FastAPI:
    if not service_token:
        raise ValueError(
            "execution service requires a service token "
            "(SQUADOPS__EXECUTION__SERVICE_TOKEN) — it never runs unauthenticated"
        )

    app = FastAPI(title="SquadOps Execution Service", docs_url=None, redoc_url=None)

    @app.exception_handler(HTTPException)
    async def _envelope_handler(request: Request, exc: HTTPException) -> JSONResponse:
        # Emit the flat resource-lane envelope, not FastAPI's {"detail": ...}.
        detail = exc.detail
        if not (isinstance(detail, dict) and "error" in detail):
            detail = {"error": {"code": "HTTP_ERROR", "message": str(detail), "details": None}}
        return JSONResponse(status_code=exc.status_code, content=detail)

    def require_identity(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = f"Bearer {service_token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise _error(401, "UNAUTHENTICATED", "valid service bearer token required")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "execution"}

    @app.post(
        "/api/v1/workspaces/{cycle_id}/seed",
        dependencies=[Depends(require_identity)],
    )
    async def seed(cycle_id: str, body: SeedRequest) -> dict:
        return await _handle_seed(service, cycle_id, body)

    @app.post(
        "/api/v1/workspaces/{cycle_id}/operations",
        dependencies=[Depends(require_identity)],
    )
    async def operate(cycle_id: str, body: OperationRequest) -> dict:
        return await _handle_operate(service, cycle_id, body)

    return app
