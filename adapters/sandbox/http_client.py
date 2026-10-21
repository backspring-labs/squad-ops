"""HTTP client adapter for the sandbox service (SIP-0102 — 102.1 slice d).

Implements ``ExecutionSandboxPort`` over the service's narrow API, so callers
(the 102.3 relocations) are transport-blind: same port, whether backed by the
NoOp default, an in-process service, or the remote service. Results are
rehydrated into their concrete semantic types via the journal's
``result_type`` tag.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any

import httpx

from squadops.ports.sandbox import ExecutionSandboxPort
from squadops.ports.scenarios import ScenarioRunnerPort
from squadops.sandbox.models import (
    BuildResult,
    CommandResult,
    DiagnosticsResult,
    FileContent,
    InstallResult,
    OperationName,
    OperationResult,
    PatchResult,
    ProbeResult,
    RevisionContent,
    RevisionOrigin,
    StartResult,
    StopResult,
    TestRunResult,
    WorkspaceRevision,
    decode_binary,
    wire_files,
)
from squadops.scenarios.runner import DeclaredStart, RunnerUnavailable, TreeEvaluation

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
        CommandResult,
    )
}


#: What a request waits beyond the service's own bounds: the copy, the journal and the answer.
_MARGIN_SECONDS = 60.0


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
        command_timeout_seconds: float = 600.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {service_token}"}
        self._http_client_factory = http_client_factory or (lambda: httpx.AsyncClient(timeout=30.0))
        self._command_timeout = command_timeout_seconds

    async def _post(self, path: str, payload: dict, *, wait: float | None = None) -> dict:
        """``wait`` replaces the client's own bound for a request the service may take longer to
        answer, so the client never gives up before the service's own bound does (#2586)."""
        # As the scenario runner's long call does: a dead service is still found at connect.
        timeout = httpx.USE_CLIENT_DEFAULT if wait is None else httpx.Timeout(wait, connect=10.0)
        async with self._http_client_factory() as client:
            response = await client.post(
                f"{self._base_url}{path}", json=payload, headers=self._headers, timeout=timeout
            )
        return self._answer(response)

    async def _get(self, path: str) -> dict:
        async with self._http_client_factory() as client:
            response = await client.get(f"{self._base_url}{path}", headers=self._headers)
        return self._answer(response)

    async def _delete(self, path: str) -> None:
        async with self._http_client_factory() as client:
            response = await client.delete(f"{self._base_url}{path}", headers=self._headers)
        if response.status_code >= 400:
            self._answer(response)

    @staticmethod
    def _answer(response: httpx.Response) -> dict:
        if response.status_code >= 400:
            try:
                message = response.json()["error"]["message"]
            except (KeyError, ValueError):
                message = response.text
            raise SandboxServiceError(response.status_code, message)
        return response.json()

    async def _operate(
        self,
        revision: WorkspaceRevision,
        operation: str,
        params: dict,
        *,
        wait: float | None = None,
    ) -> dict:
        return await self._post(
            f"/api/v1/workspaces/{revision.cycle_id}/operations",
            {"operation": operation, "revision": revision.to_dict(), "params": params},
            wait=wait,
        )

    # -- service-level workspace lifecycle -----------------------------------

    async def seed_workspace(
        self,
        cycle_id: str,
        files: Mapping[str, FileContent],
        *,
        origin: str = RevisionOrigin.SCAFFOLD_SEED,
        executable: Collection[str] = (),
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        modes = {"executable": sorted(executable)} if executable else {}
        payload = await self._post(
            f"/api/v1/workspaces/{cycle_id}/seed",
            {**wire_files(files), **modes, "origin": origin, "created_at": created_at},
        )
        return WorkspaceRevision.from_dict(payload)

    async def release_workspace(self, cycle_id: str) -> None:
        await self._delete(f"/api/v1/workspaces/{cycle_id}")

    # -- typed operations -----------------------------------------------------

    async def read_workspace_revision(self, revision: WorkspaceRevision) -> RevisionContent:
        payload = await self._get(
            f"/api/v1/workspaces/{revision.cycle_id}/revisions/{revision.revision_id}"
        )
        text = payload.get("files", {})
        return RevisionContent(
            revision=WorkspaceRevision.from_dict(payload["revision"]),
            files={**text, **decode_binary(payload.get("binary_files", {}), alongside=text)},
            executable=frozenset(payload.get("executable", ())),
        )

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

    async def run_declared_command(
        self,
        *,
        revision: WorkspaceRevision,
        command: tuple[str, ...],
        working_dir: str = ".",
        setup: tuple[tuple[str, ...], ...] = (),
        timeout_seconds: float | None = None,
        findings_reader: str | None = None,
    ) -> CommandResult:
        # #2586: the service bounds each setup step and the command apart, so the request waits
        # for all of them, with one bound sent so both sides use the same.
        bound = self._command_timeout if timeout_seconds is None else timeout_seconds
        payload = await self._operate(
            revision,
            OperationName.RUN_DECLARED_COMMAND,
            {
                "command": list(command),
                "working_dir": working_dir,
                "setup": [list(step) for step in setup],
                "timeout_seconds": bound,
                "findings_reader": findings_reader,
            },
            wait=(len(setup) + 1) * bound + _MARGIN_SECONDS,
        )
        result = _rehydrate(payload)
        if not isinstance(result, CommandResult):
            raise SandboxServiceError(200, f"expected a CommandResult, got {type(result).__name__}")
        return result

    async def read_build_diagnostics(self, *, revision: WorkspaceRevision) -> DiagnosticsResult:
        payload = await self._operate(revision, OperationName.READ_BUILD_DIAGNOSTICS, {})
        return _rehydrate(payload)

    async def apply_workspace_patch(
        self,
        *,
        base: WorkspaceRevision,
        files: Mapping[str, FileContent | None],
        origin: str = RevisionOrigin.AGENT_PATCH,
    ) -> PatchResult:
        payload = await self._operate(
            base,
            OperationName.APPLY_WORKSPACE_PATCH,
            {**wire_files(files), "origin": origin},
        )
        return _rehydrate(payload)


class HttpScenarioRunner(ScenarioRunnerPort):
    """SIP-0113's runner over the sandbox service's API (#2414). The runtime API calls it with the
    evaluated tree and the suite's scenarios, so the steps travel in the request, in memory. An
    evaluation installs, builds and starts the tree before any scenario runs, hence the long
    timeout."""

    def __init__(
        self,
        *,
        base_url: str,
        service_token: str,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._sandbox = HttpExecutionSandbox(
            base_url=base_url,
            service_token=service_token,
            http_client_factory=http_client_factory
            or (lambda: httpx.AsyncClient(timeout=httpx.Timeout(1800.0, connect=10.0))),
        )

    async def evaluate_tree(
        self,
        *,
        tree: Mapping[str, bytes | str],
        tree_identity: str,
        executable: Collection[str],
        stack: str | None,
        declared: DeclaredStart | None,
        scenarios: Sequence[Mapping[str, Any]],
        environment: Mapping[str, str],
        pages: Sequence[str],
    ) -> TreeEvaluation:
        wire = wire_files(tree)
        try:
            payload = await self._post_evaluation(
                wire, tree_identity, executable, stack, declared, scenarios, environment, pages
            )
        except SandboxServiceError as e:
            if e.status_code == 503:
                raise RunnerUnavailable(str(e)) from e
            raise
        except httpx.ConnectError as e:
            raise RunnerUnavailable(f"the sandbox service is unreachable: {e}") from e
        return TreeEvaluation.from_dict(payload)

    async def _post_evaluation(
        self, wire, tree_identity, executable, stack, declared, scenarios, environment, pages
    ) -> dict:
        return await self._sandbox._post(
            "/api/v1/evaluations",
            {
                "tree": wire["files"],
                "binary_tree": wire.get("binary_files", {}),
                "executable": sorted(executable),
                "tree_identity": tree_identity,
                "stack": stack,
                "declared": declared.as_dict() if declared else None,
                "scenarios": [dict(s) for s in scenarios],
                "environment": dict(environment),
                "pages": list(pages),
            },
        )
