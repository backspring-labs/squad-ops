"""Container-backed execution operations (SIP-0102 — phase 102.1 slice c1).

Renders the one-shot build-runner operations (install / build / tests /
diagnostics) into hardened ``ContainerSpec`` runs against the cycle
workspace bind-mount. Extends the NoOp base so the runtime-unit operations
(``start_application`` / ``probe_http_endpoint`` — slice c2) stay honestly
``not_run`` until implemented, and ``apply_workspace_patch`` remains
service-owned.

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

import time
from collections.abc import Mapping

from squadops.execution.models import (
    BuildResult,
    DiagnosticsResult,
    InstallResult,
    OperationName,
    OperationStatus,
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
