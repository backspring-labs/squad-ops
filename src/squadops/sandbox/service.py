"""Sandbox service core (SIP-0102 §4.3 — phase 102.1 slice b).

Transport-agnostic: this class owns workspace provisioning, revision
bookkeeping, and evidence capture around every typed operation. The confirmed
localhost-HTTP surface (#326 service identity) wraps it once the Docker
backend exists (slice c) — transport never touches these semantics.

The service is itself an ``ExecutionSandboxPort``: execution operations
delegate to an injected backend (the container adapter); workspace mutation
(``apply_workspace_patch``) is handled by the store directly and is never
delegated. With no backend configured, every execution operation is honestly
``not_run`` — same contract as the NoOp adapter, but journaled, because a
request that reached the service is evidence even when the environment cannot
execute it (§4.4).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection, Mapping

from squadops.ports.sandbox import ExecutionSandboxPort
from squadops.ports.scenarios import ScenarioRunnerPort
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.models import (
    BuildResult,
    CommandResult,
    DiagnosticsResult,
    FileContent,
    InstallResult,
    OperationName,
    OperationResult,
    OperationStatus,
    PatchResult,
    ProbeResult,
    RevisionContent,
    RevisionOrigin,
    StartResult,
    StopResult,
    TestRunResult,
    WorkspaceRevision,
    declared_argv,
    declared_reader,
)
from squadops.sandbox.workspace import WorkspaceStore, working_directory

_NO_BACKEND = "no execution backend configured"


class SandboxService(ExecutionSandboxPort):
    """Workspace + evidence bookkeeping around a delegated execution backend."""

    def __init__(
        self,
        *,
        store: WorkspaceStore,
        journal: OperationEvidenceJournal,
        backend: ExecutionSandboxPort | None = None,
        environment_report: Callable[[], Awaitable[dict | None]] | None = None,
        scenario_runner: ScenarioRunnerPort | None = None,
    ) -> None:
        self._store = store
        self._journal = journal
        self._backend = backend
        self._environment_report = environment_report
        self._scenario_runner = scenario_runner

    @property
    def scenario_runner(self) -> ScenarioRunnerPort | None:
        """SIP-0113's runner (A3, #2414), or None where the deploy runs none."""
        return self._scenario_runner

    async def environment_report(self) -> dict | None:
        """The backend's environment facts (contract id, image presence) for
        /health and preflight reconciliation; None when no backend reports."""
        if self._environment_report is None:
            return None
        return await self._environment_report()

    # -- workspace lifecycle -------------------------------------------------

    async def seed_workspace(
        self,
        cycle_id: str,
        files: Mapping[str, FileContent],
        *,
        origin: str = RevisionOrigin.SCAFFOLD_SEED,
        executable: Collection[str] = (),
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        """Provision and seed the cycle workspace, cutting revision one. The
        persisted revision is the seeding's durable record."""
        return self._store.seed(
            cycle_id, files, origin=origin, executable=executable, created_at=created_at
        )

    async def release_workspace(self, cycle_id: str) -> None:
        """Remove the cycle's workspace and its revisions (#2473); its journal stays."""
        self._store.cleanup(cycle_id)

    def verify_pinned(self, cycle_id: str, revision_id: str) -> bool:
        return self._store.verify_pinned(cycle_id, revision_id)

    def get_revision(self, cycle_id: str, revision_id: str) -> WorkspaceRevision | None:
        return self._store.get_revision(cycle_id, revision_id)

    async def read_workspace_revision(self, revision: WorkspaceRevision) -> RevisionContent:
        files, executable = self._store.read_pinned(revision.cycle_id, revision.revision_id)
        stored = self._store.get_revision(revision.cycle_id, revision.revision_id) or revision
        return RevisionContent(revision=stored, files=files, executable=executable)

    # -- delegated execution operations --------------------------------------

    async def _delegate(
        self,
        operation: str,
        result_cls: type[OperationResult],
        revision: WorkspaceRevision,
        call,
        **not_run_fields,
    ) -> OperationResult:
        if self._backend is None:
            result = result_cls(
                operation=operation,
                workspace_revision_id=revision.revision_id,
                status=OperationStatus.NOT_RUN,
                ran=False,
                unavailable_reason=_NO_BACKEND,
                **not_run_fields,
            )
        else:
            result = await call()
        self._journal.record(revision.cycle_id, result)
        return result

    async def install_dependencies(self, *, revision: WorkspaceRevision) -> InstallResult:
        return await self._delegate(
            OperationName.INSTALL_DEPENDENCIES,
            InstallResult,
            revision,
            lambda: self._backend.install_dependencies(revision=revision),
        )

    async def build_frontend(self, *, revision: WorkspaceRevision) -> BuildResult:
        return await self._delegate(
            OperationName.BUILD_FRONTEND,
            BuildResult,
            revision,
            lambda: self._backend.build_frontend(revision=revision),
        )

    async def run_backend_tests(self, *, revision: WorkspaceRevision) -> TestRunResult:
        return await self._delegate(
            OperationName.RUN_BACKEND_TESTS,
            TestRunResult,
            revision,
            lambda: self._backend.run_backend_tests(revision=revision),
        )

    async def start_application(self, *, revision: WorkspaceRevision) -> StartResult:
        return await self._delegate(
            OperationName.START_APPLICATION,
            StartResult,
            revision,
            lambda: self._backend.start_application(revision=revision),
        )

    async def stop_application(
        self, *, revision: WorkspaceRevision, cleanup_handle: str
    ) -> StopResult:
        return await self._delegate(
            OperationName.STOP_APPLICATION,
            StopResult,
            revision,
            lambda: self._backend.stop_application(
                revision=revision, cleanup_handle=cleanup_handle
            ),
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
        return await self._delegate(
            OperationName.PROBE_HTTP_ENDPOINT,
            ProbeResult,
            revision,
            lambda: self._backend.probe_http_endpoint(
                revision=revision,
                probe_id=probe_id,
                method=method,
                path=path,
                expected_status=expected_status,
            ),
            probe_id=probe_id,
        )

    async def read_build_diagnostics(self, *, revision: WorkspaceRevision) -> DiagnosticsResult:
        return await self._delegate(
            OperationName.READ_BUILD_DIAGNOSTICS,
            DiagnosticsResult,
            revision,
            lambda: self._backend.read_build_diagnostics(revision=revision),
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
        # Refused here, whether or not a backend runs it: a malformed declaration is the
        # caller's error, never an environment that could not run it.
        command = declared_argv(command)
        setup = tuple(declared_argv(step) for step in setup)
        working_directory(working_dir)
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {timeout_seconds}")
        declared_reader(findings_reader)
        backend = self._backend

        async def call() -> CommandResult:
            assert backend is not None  # _delegate answers not_run without calling, when None
            return await backend.run_declared_command(
                revision=revision,
                command=command,
                working_dir=working_dir,
                setup=setup,
                timeout_seconds=timeout_seconds,
                findings_reader=findings_reader,
            )

        result = await self._delegate(
            OperationName.RUN_DECLARED_COMMAND, CommandResult, revision, call, command=command
        )
        assert isinstance(result, CommandResult)
        return result

    # -- workspace mutation (never delegated) --------------------------------

    async def apply_workspace_patch(
        self,
        *,
        base: WorkspaceRevision,
        files: Mapping[str, FileContent | None],
        origin: str = RevisionOrigin.AGENT_PATCH,
    ) -> PatchResult:
        """Apply the patch through the store (stale-base guarded, §4.6
        boundary) and journal the cut. Store violations raise — a stale or
        escaping patch is a caller error, not an operation outcome."""
        revision, changed = self._store.apply_patch(
            base.cycle_id,
            base_revision_id=base.revision_id,
            files=files,
            origin=origin,
        )
        result = PatchResult(
            operation=OperationName.APPLY_WORKSPACE_PATCH,
            workspace_revision_id=base.revision_id,
            status=OperationStatus.SUCCEEDED,
            ran=True,
            new_revision_id=revision.revision_id,
            files_changed=changed,
        )
        self._journal.record(base.cycle_id, result)
        return result
