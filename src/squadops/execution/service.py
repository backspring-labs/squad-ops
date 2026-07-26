"""Execution service core (SIP-0102 §4.3 — phase 102.1 slice b).

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

from collections.abc import Mapping

from squadops.execution.evidence import OperationEvidenceJournal
from squadops.execution.models import (
    BuildResult,
    DiagnosticsResult,
    InstallResult,
    OperationName,
    OperationResult,
    OperationStatus,
    PatchResult,
    ProbeResult,
    RevisionOrigin,
    StartResult,
    StopResult,
    TestRunResult,
    WorkspaceRevision,
)
from squadops.execution.workspace import WorkspaceStore
from squadops.ports.execution import ExecutionSandboxPort

_NO_BACKEND = "no execution backend configured"


class ExecutionService(ExecutionSandboxPort):
    """Workspace + evidence bookkeeping around a delegated execution backend."""

    def __init__(
        self,
        *,
        store: WorkspaceStore,
        journal: OperationEvidenceJournal,
        backend: ExecutionSandboxPort | None = None,
    ) -> None:
        self._store = store
        self._journal = journal
        self._backend = backend

    # -- workspace lifecycle (service-level, not port operations) ------------

    def seed_workspace(
        self,
        cycle_id: str,
        files: Mapping[str, str],
        *,
        origin: str = RevisionOrigin.SCAFFOLD_SEED,
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        """Provision and seed the cycle workspace, cutting revision one. The
        persisted revision is the seeding's durable record."""
        return self._store.seed(cycle_id, files, origin=origin, created_at=created_at)

    def verify_pinned(self, cycle_id: str, revision_id: str) -> bool:
        return self._store.verify_pinned(cycle_id, revision_id)

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

    # -- workspace mutation (never delegated) --------------------------------

    async def apply_workspace_patch(
        self,
        *,
        base: WorkspaceRevision,
        files: Mapping[str, str | None],
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
