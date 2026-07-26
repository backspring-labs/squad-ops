"""HTTP client adapter for the sandbox service (SIP-0102 — 102.1 slice d).

Implements ``ExecutionSandboxPort`` over the service's narrow API, so callers
(the 102.3 relocations) are transport-blind: same port, whether backed by the
NoOp default, an in-process service, or the remote service. Results are
rehydrated into their concrete semantic types via the journal's
``result_type`` tag.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping

import httpx

from squadops.ports.sandbox import ExecutionSandboxPort
from squadops.sandbox.models import (
    BuildResult,
    DiagnosticsResult,
    InstallResult,
    OperationName,
    OperationResult,
    PatchResult,
    ProbeResult,
    RevisionOrigin,
    StartResult,
    StopResult,
    TestRunResult,
    WorkspaceRevision,
)

_RESULT_TYPES: dict[str, type[OperationResult]] = {
    cls.__name__: cls
    for cls in (
        InstallResult,
        BuildResult,
        TestRunResult,
        StartResult,
        StopResult,
        ProbeResult,
        PatchResult,
        DiagnosticsResult,
    )
}


class SandboxServiceError(Exception):
    """The sandbox service rejected or failed a request."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"sandbox service returned {status_code}: {message}")
        self.status_code = status_code


def _rehydrate(payload: dict) -> OperationResult:
    cls = _RESULT_TYPES.get(payload.get("result_type", ""))
    if cls is None:
        raise SandboxServiceError(200, f"unknown result_type: {payload.get('result_type')!r}")
    kwargs = {}
    for field in dataclasses.fields(cls):
        if field.name in payload:
            value = payload[field.name]
            # JSON turned the frozen models' tuples into lists; restore them.
            kwargs[field.name] = tuple(value) if isinstance(value, list) else value
    return cls(**kwargs)


class HttpExecutionSandbox(ExecutionSandboxPort):
    """Port implementation over the sandbox service HTTP API."""

    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {service_token}"}
        self._http_client_factory = http_client_factory or (lambda: httpx.AsyncClient(timeout=30.0))

    async def _post(self, path: str, payload: dict) -> dict:
        async with self._http_client_factory() as client:
            response = await client.post(
                f"{self._base_url}{path}", json=payload, headers=self._headers
            )
        if response.status_code >= 400:
            try:
                message = response.json()["error"]["message"]
            except (KeyError, ValueError):
                message = response.text
            raise SandboxServiceError(response.status_code, message)
        return response.json()

    async def _operate(self, revision: WorkspaceRevision, operation: str, params: dict) -> dict:
        return await self._post(
            f"/api/v1/workspaces/{revision.cycle_id}/operations",
            {"operation": operation, "revision": revision.to_dict(), "params": params},
        )

    # -- service-level workspace lifecycle -----------------------------------

    async def seed_workspace(
        self,
        cycle_id: str,
        files: Mapping[str, str],
        *,
        origin: str = RevisionOrigin.SCAFFOLD_SEED,
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        payload = await self._post(
            f"/api/v1/workspaces/{cycle_id}/seed",
            {"files": dict(files), "origin": origin, "created_at": created_at},
        )
        return WorkspaceRevision.from_dict(payload)

    # -- typed operations -----------------------------------------------------

    async def install_dependencies(self, *, revision: WorkspaceRevision) -> InstallResult:
        payload = await self._operate(revision, OperationName.INSTALL_DEPENDENCIES, {})
        return _rehydrate(payload)

    async def build_frontend(self, *, revision: WorkspaceRevision) -> BuildResult:
        payload = await self._operate(revision, OperationName.BUILD_FRONTEND, {})
        return _rehydrate(payload)

    async def run_backend_tests(self, *, revision: WorkspaceRevision) -> TestRunResult:
        payload = await self._operate(revision, OperationName.RUN_BACKEND_TESTS, {})
        return _rehydrate(payload)

    async def start_application(self, *, revision: WorkspaceRevision) -> StartResult:
        payload = await self._operate(revision, OperationName.START_APPLICATION, {})
        return _rehydrate(payload)

    async def stop_application(
        self, *, revision: WorkspaceRevision, cleanup_handle: str
    ) -> StopResult:
        payload = await self._operate(
            revision, OperationName.STOP_APPLICATION, {"cleanup_handle": cleanup_handle}
        )
        return _rehydrate(payload)

    async def probe_http_endpoint(
        self,
        *,
        revision: WorkspaceRevision,
        probe_id: str,
        method: str,
        path: str,
        expected_status: int | None = None,
    ) -> ProbeResult:
        payload = await self._operate(
            revision,
            OperationName.PROBE_HTTP_ENDPOINT,
            {
                "probe_id": probe_id,
                "method": method,
                "path": path,
                "expected_status": expected_status,
            },
        )
        return _rehydrate(payload)

    async def read_build_diagnostics(self, *, revision: WorkspaceRevision) -> DiagnosticsResult:
        payload = await self._operate(revision, OperationName.READ_BUILD_DIAGNOSTICS, {})
        return _rehydrate(payload)

    async def apply_workspace_patch(
        self,
        *,
        base: WorkspaceRevision,
        files: Mapping[str, str | None],
        origin: str = RevisionOrigin.AGENT_PATCH,
    ) -> PatchResult:
        payload = await self._operate(
            base,
            OperationName.APPLY_WORKSPACE_PATCH,
            {"files": dict(files), "origin": origin},
        )
        return _rehydrate(payload)
