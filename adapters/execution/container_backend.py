"""Container-backed execution operations (SIP-0102 — phase 102.1 slice c1).

Renders the one-shot build-runner operations (install / build / tests /
diagnostics) into hardened ``ContainerSpec`` runs against the cycle workspace
bind-mount, and owns the runtime unit (slice c2): ``start_application`` boots
the app detached with its declared port published to loopback, awaits HTTP
readiness, and hands back endpoint + cleanup handles;
``probe_http_endpoint`` probes from the host — outside the application
process boundary (§7 item 14) — and ``stop_application`` converges teardown.
Extends the NoOp base so ``apply_workspace_patch`` remains service-owned.

Operation commands and the image are constructor-supplied: the validated
environment contract (102.2) is their source of truth — this adapter never
invents commands, and an operation the environment does not provide is an
explicit ``not_run``, never a guess (the advertised-vs-provided rule).

Hardening is unconditional (§7 items 9–10): caps dropped, no-new-privileges,
resource limits, network denied — except ``install_dependencies``, which gets
the deps-only egress network (102.2 tightens this to a policy-controlled
proxy; "bridge" is the floor).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping

import httpx

from squadops.execution.models import (
    BuildResult,
    DiagnosticsResult,
    InstallResult,
    OperationName,
    OperationStatus,
    ProbeResult,
    StartResult,
    StopResult,
    TestRunResult,
    WorkspaceRevision,
)
from squadops.execution.noop import NoOpExecutionSandbox
from squadops.execution.workspace import WorkspaceStore, WorkspaceStoreError
from squadops.ports.tools.container import ContainerPort
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerResult, ContainerSpec

_WORKSPACE_MOUNT = "/workspace"
_TAIL_CHARS = 4000
_TAIL_LINES = 40


def _tail_lines(text: str) -> tuple[str, ...]:
    return tuple(text.splitlines()[-_TAIL_LINES:])


class ContainerBackend(NoOpExecutionSandbox):
    """One-shot typed operations executed via ``ContainerPort``."""

    def __init__(
        self,
        *,
        container: ContainerPort,
        store: WorkspaceStore,
        image: str,
        operation_commands: Mapping[str, tuple[str, ...]],
        install_network: str = "bridge",
        memory_limit: str = "2g",
        cpu_limit: float = 2.0,
        pids_limit: int = 512,
        timeout_seconds: float = 600.0,
        app_port: int = 8000,
        health_path: str = "/health",
        readiness_timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._container = container
        self._store = store
        self._image = image
        self._operation_commands = dict(operation_commands)
        self._install_network = install_network
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit
        self._pids_limit = pids_limit
        self._timeout_seconds = timeout_seconds
        self._app_port = app_port
        self._health_path = health_path
        self._readiness_timeout = readiness_timeout_seconds
        self._poll_interval = poll_interval_seconds
        self._http_client_factory = http_client_factory or (lambda: httpx.AsyncClient(timeout=5.0))
        # cycle_id → (container_id, host_port). Runtime units are short-lived;
        # a service restart orphans nothing durable (`--rm` containers), and
        # the labeled-container sweep is 102.2+ hardening.
        self._running: dict[str, tuple[str, int]] = {}

    def _spec(self, operation: str, cycle_id: str, command: tuple[str, ...]) -> ContainerSpec:
        network = (
            self._install_network
            if operation == OperationName.INSTALL_DEPENDENCIES
            else "none"  # §7 item 10: deny by default
        )
        return ContainerSpec(
            image=self._image,
            command=list(command),
            volumes=((str(self._store.workspace_dir(cycle_id)), _WORKSPACE_MOUNT),),
            working_dir=_WORKSPACE_MOUNT,
            timeout_seconds=self._timeout_seconds,
            network=network,
            memory_limit=self._memory_limit,
            cpu_limit=self._cpu_limit,
            pids_limit=self._pids_limit,
            cap_drop_all=True,
            no_new_privileges=True,
        )

    async def _one_shot(
        self, operation: str, revision: WorkspaceRevision
    ) -> tuple[dict, ContainerResult | None]:
        """Run one typed operation; returns the common result fields plus the
        raw container result (None when nothing executed)."""
        if not self._store.verify_pinned(revision.cycle_id, revision.revision_id):
            # §7 item 3: executing against undeclared content is a caller
            # error, not an operation outcome.
            raise WorkspaceStoreError(
                f"live tree for {revision.cycle_id} does not match declared "
                f"revision {revision.revision_id}"
            )
        base = {
            "operation": operation,
            "workspace_revision_id": revision.revision_id,
            "image_identity": self._image,  # §7 item 4
        }
        command = self._operation_commands.get(operation)
        if command is None:
            not_run = {
                **base,
                "status": OperationStatus.NOT_RUN,
                "ran": False,
                "unavailable_reason": f"environment provides no command for '{operation}'",
            }
            return not_run, None
        started = time.monotonic()
        try:
            run = await self._container.run(self._spec(operation, revision.cycle_id, command))
        except ToolContainerError as e:
            duration = time.monotonic() - started
            if "timed out" in str(e).lower():
                # The container executed application code until the limit —
                # that is a deliverable failure, never environment-unavailable.
                timeout = {
                    **base,
                    "status": OperationStatus.FAILED,
                    "ran": True,
                    "duration_seconds": duration,
                    "exit_classification": "timeout",
                }
                return timeout, None
            unavailable = {
                **base,
                "status": OperationStatus.NOT_RUN,
                "ran": False,
                "unavailable_reason": str(e),
            }
            return unavailable, None
        duration = time.monotonic() - started
        ok = run.exit_code == 0
        executed = {
            **base,
            "status": OperationStatus.SUCCEEDED if ok else OperationStatus.FAILED,
            "ran": True,
            "duration_seconds": duration,
            "exit_classification": None if ok else "nonzero_exit",
        }
        return executed, run

    async def install_dependencies(self, *, revision: WorkspaceRevision) -> InstallResult:
        common, _run = await self._one_shot(OperationName.INSTALL_DEPENDENCIES, revision)
        return InstallResult(**common)

    async def build_frontend(self, *, revision: WorkspaceRevision) -> BuildResult:
        common, run = await self._one_shot(OperationName.BUILD_FRONTEND, revision)
        return BuildResult(**common, diagnostics=_tail_lines(run.stderr) if run else ())

    async def run_backend_tests(self, *, revision: WorkspaceRevision) -> TestRunResult:
        common, run = await self._one_shot(OperationName.RUN_BACKEND_TESTS, revision)
        return TestRunResult(
            **common,
            exit_code=run.exit_code if run else None,
            output_tail=(run.stdout + run.stderr)[-_TAIL_CHARS:] if run else "",
        )

    async def read_build_diagnostics(self, *, revision: WorkspaceRevision) -> DiagnosticsResult:
        common, run = await self._one_shot(OperationName.READ_BUILD_DIAGNOSTICS, revision)
        return DiagnosticsResult(
            **common, entries=_tail_lines(run.stdout + run.stderr) if run else ()
        )

    # -- runtime unit (slice c2) ---------------------------------------------

    async def _await_ready(self, base_url: str) -> bool:
        deadline = time.monotonic() + self._readiness_timeout
        while True:
            try:
                async with self._http_client_factory() as client:
                    response = await client.request("GET", base_url + self._health_path)
                if 200 <= response.status_code < 300:
                    return True
            except (httpx.HTTPError, OSError):
                pass  # connection refused while the app boots is expected
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(self._poll_interval)

    async def start_application(self, *, revision: WorkspaceRevision) -> StartResult:
        if not self._store.verify_pinned(revision.cycle_id, revision.revision_id):
            raise WorkspaceStoreError(
                f"live tree for {revision.cycle_id} does not match declared "
                f"revision {revision.revision_id}"
            )
        base = {
            "operation": OperationName.START_APPLICATION,
            "workspace_revision_id": revision.revision_id,
            "image_identity": self._image,
        }
        command = self._operation_commands.get(OperationName.START_APPLICATION)
        if command is None:
            return StartResult(
                **base,
                status=OperationStatus.NOT_RUN,
                ran=False,
                unavailable_reason="environment provides no command for 'start_application'",
            )
        spec = ContainerSpec(
            image=self._image,
            command=list(command),
            volumes=((str(self._store.workspace_dir(revision.cycle_id)), _WORKSPACE_MOUNT),),
            working_dir=_WORKSPACE_MOUNT,
            timeout_seconds=self._timeout_seconds,
            # The runtime unit publishes its declared endpoint to loopback, so
            # it keeps the default bridge network for the floor; the 102.2
            # policy network restores deny-by-default with a declared opening.
            memory_limit=self._memory_limit,
            cpu_limit=self._cpu_limit,
            pids_limit=self._pids_limit,
            cap_drop_all=True,
            no_new_privileges=True,
            publish_ports=(self._app_port,),
        )
        started = time.monotonic()
        try:
            container_id = await self._container.run_detached(spec)
            host_port = await self._container.resolve_host_port(container_id, self._app_port)
        except ToolContainerError as e:
            return StartResult(
                **base, status=OperationStatus.NOT_RUN, ran=False, unavailable_reason=str(e)
            )
        base_url = f"http://127.0.0.1:{host_port}"
        ready = await self._await_ready(base_url)
        duration = time.monotonic() - started
        if not ready:
            try:
                diagnostics = _tail_lines(await self._container.logs(container_id))
            except ToolContainerError:
                diagnostics = ()
            try:
                await self._container.stop(container_id)
            except ToolContainerError:
                pass  # teardown converges; the container may already be gone
            return StartResult(
                **base,
                status=OperationStatus.FAILED,
                ran=True,
                duration_seconds=duration,
                exit_classification="startup_timeout",
                process_identity=container_id,
                ready=False,
                startup_diagnostics=diagnostics,
                cleanup_handle=container_id,
            )
        self._running[revision.cycle_id] = (container_id, host_port)
        return StartResult(
            **base,
            status=OperationStatus.SUCCEEDED,
            ran=True,
            duration_seconds=duration,
            process_identity=container_id,
            endpoints=(base_url,),
            ready=True,
            cleanup_handle=container_id,
        )

    async def probe_http_endpoint(
        self,
        *,
        revision: WorkspaceRevision,
        probe_id: str,
        method: str,
        path: str,
        expected_status: int | None = None,
    ) -> ProbeResult:
        if not self._store.verify_pinned(revision.cycle_id, revision.revision_id):
            raise WorkspaceStoreError(
                f"live tree for {revision.cycle_id} does not match declared "
                f"revision {revision.revision_id}"
            )
        base = {
            "operation": OperationName.PROBE_HTTP_ENDPOINT,
            "workspace_revision_id": revision.revision_id,
            "image_identity": self._image,
            "probe_id": probe_id,
        }
        running = self._running.get(revision.cycle_id)
        if running is None:
            return ProbeResult(
                **base,
                status=OperationStatus.NOT_RUN,
                ran=False,
                unavailable_reason="application is not running",
            )
        _container_id, host_port = running
        started = time.monotonic()
        try:
            async with self._http_client_factory() as client:
                response = await client.request(method, f"http://127.0.0.1:{host_port}{path}")
        except (httpx.HTTPError, OSError) as e:
            # The app is up but unreachable/unresponsive on its declared
            # endpoint — that is the application's failure, not the probe's.
            return ProbeResult(
                **base,
                status=OperationStatus.FAILED,
                ran=True,
                duration_seconds=time.monotonic() - started,
                exit_classification="connection_error",
                detail=str(e),
            )
        ok = (
            response.status_code == expected_status
            if expected_status is not None
            else 200 <= response.status_code < 300
        )
        return ProbeResult(
            **base,
            status=OperationStatus.SUCCEEDED if ok else OperationStatus.FAILED,
            ran=True,
            duration_seconds=time.monotonic() - started,
            observed_status_code=response.status_code,
            detail=(
                None
                if ok
                else f"expected {expected_status or '2xx'}, observed {response.status_code}"
            ),
        )

    async def stop_application(
        self, *, revision: WorkspaceRevision, cleanup_handle: str
    ) -> StopResult:
        # Deliberately no pin verification: teardown must converge even over a
        # drifted tree (§7 item 12's spirit — cleanup never gets stuck).
        base = {
            "operation": OperationName.STOP_APPLICATION,
            "workspace_revision_id": revision.revision_id,
            "image_identity": self._image,
        }
        self._running.pop(revision.cycle_id, None)
        try:
            await self._container.stop(cleanup_handle)
        except ToolContainerError as e:
            if "no such container" in str(e).lower():
                return StopResult(
                    **base,
                    status=OperationStatus.SUCCEEDED,
                    ran=True,
                    detail="already stopped",
                )
            return StopResult(
                **base,
                status=OperationStatus.FAILED,
                ran=True,
                exit_classification="teardown_error",
                detail=str(e),
            )
        return StopResult(**base, status=OperationStatus.SUCCEEDED, ran=True)
