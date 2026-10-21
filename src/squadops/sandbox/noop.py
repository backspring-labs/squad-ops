"""NoOp execution sandbox — the always-injectable unconfigured default.

Every operation reports ``ran=False`` / ``not_run`` with a uniform reason: the
sandbox is not configured, so callers keep their current in-process execution
paths (byte-identical parity — the inert-to-merge guarantee). Never raises:
an unconfigured sandbox must be indistinguishable from an absent one.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from squadops.ports.sandbox import ExecutionSandboxPort
from squadops.sandbox.models import (
    BuildResult,
    CommandResult,
    DiagnosticsResult,
    FileContent,
    InstallResult,
    OperationName,
    OperationStatus,
    PatchResult,
    ProbeResult,
    RevisionContent,
    RevisionOrigin,
    StartResult,
    StopResult,
    TestRunResult,
    WorkspaceRevision,
    unread,
)
from squadops.sandbox.workspace import StaleBaseRevisionError

_REASON = "execution sandbox not configured"


class NoOpExecutionSandbox(ExecutionSandboxPort):
    """Default adapter: every typed operation is honestly not-run."""

    def _common(self, operation: str, revision_id: str) -> dict:
        return {
            "operation": operation,
            "workspace_revision_id": revision_id,
            "status": OperationStatus.NOT_RUN,
            "ran": False,
            "unavailable_reason": _REASON,
        }

    async def seed_workspace(
        self,
        cycle_id: str,
        files: Mapping[str, FileContent],
        *,
        origin: str = RevisionOrigin.SCAFFOLD_SEED,
        executable: Collection[str] = (),
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        # Nothing is stored: the revision is the content's own address, as a patch here returns
        # its untouched base, and every operation on it is not-run.
        return WorkspaceRevision.cut(
            cycle_id=cycle_id,
            origin=origin,
            files=files,
            executable=executable,
            created_at=created_at,
        )

    async def release_workspace(self, cycle_id: str) -> None:
        # Nothing was stored, so nothing is held.
        return None

    async def read_workspace_revision(self, revision: WorkspaceRevision) -> RevisionContent:
        # A workspace read isn't a typed operation with a not-run result. The noop's seed stored
        # nothing, so there is nothing to read: it refuses, as a drifted tree is refused.
        raise StaleBaseRevisionError(f"{_REASON}: no revision {revision.revision_id} is held")

    async def install_dependencies(self, *, revision: WorkspaceRevision) -> InstallResult:
        return InstallResult(
            **self._common(OperationName.INSTALL_DEPENDENCIES, revision.revision_id)
        )

    async def build_frontend(self, *, revision: WorkspaceRevision) -> BuildResult:
        return BuildResult(**self._common(OperationName.BUILD_FRONTEND, revision.revision_id))

    async def run_backend_tests(self, *, revision: WorkspaceRevision) -> TestRunResult:
        return TestRunResult(**self._common(OperationName.RUN_BACKEND_TESTS, revision.revision_id))

    async def start_application(self, *, revision: WorkspaceRevision) -> StartResult:
        return StartResult(**self._common(OperationName.START_APPLICATION, revision.revision_id))

    async def stop_application(
        self, *, revision: WorkspaceRevision, cleanup_handle: str
    ) -> StopResult:
        return StopResult(**self._common(OperationName.STOP_APPLICATION, revision.revision_id))

    async def probe_http_endpoint(
        self,
        *,
        revision: WorkspaceRevision,
        probe_id: str,
        method: str,
        path: str,
        expected_status: int | None = None,
    ) -> ProbeResult:
        return ProbeResult(
            probe_id=probe_id,
            **self._common(OperationName.PROBE_HTTP_ENDPOINT, revision.revision_id),
        )

    async def apply_workspace_patch(
        self,
        *,
        base: WorkspaceRevision,
        files: Mapping[str, FileContent | None],
        origin: str = RevisionOrigin.AGENT_PATCH,
    ) -> PatchResult:
        # Nothing is applied: the "new" revision is the untouched base.
        return PatchResult(
            new_revision_id=base.revision_id,
            **self._common(OperationName.APPLY_WORKSPACE_PATCH, base.revision_id),
        )

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
        return CommandResult(
            command=tuple(command),
            findings=unread(findings_reader, "the sandbox runs nothing"),
            **self._common(OperationName.RUN_DECLARED_COMMAND, revision.revision_id),
        )

    async def read_build_diagnostics(self, *, revision: WorkspaceRevision) -> DiagnosticsResult:
        return DiagnosticsResult(
            **self._common(OperationName.READ_BUILD_DIAGNOSTICS, revision.revision_id)
        )
