"""Execution sandbox port (SIP-0102 §4.4).

The agent-facing surface of the Ephemeral Application Sandbox: typed,
policy-bearing operations with structured semantic results. There is no
generic shell operation and no safelist to extend. Every operation executes
against an explicit workspace revision (§4.6) — never "whatever is in the
directory."

Adapters own container mechanics; callers never see a container runtime. The
NoOp adapter (``squadops.sandbox.noop``) is the unconfigured default: every
operation reports ``ran=False`` and callers keep today's in-process behavior.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection, Mapping

from squadops.sandbox.models import (
    BuildResult,
    CommandResult,
    DiagnosticsResult,
    FileContent,
    InstallResult,
    PatchResult,
    ProbeResult,
    RevisionContent,
    RevisionOrigin,
    StartResult,
    StopResult,
    TestRunResult,
    WorkspaceRevision,
)


class ExecutionSandboxPort(ABC):
    """Port for typed execution operations against a cycle workspace."""

    @abstractmethod
    async def seed_workspace(
        self,
        cycle_id: str,
        files: Mapping[str, FileContent],
        *,
        origin: str = RevisionOrigin.SCAFFOLD_SEED,
        executable: Collection[str] = (),
        created_at: str | None = None,
    ) -> WorkspaceRevision:
        """Provision the cycle's workspace and seed it, cutting revision one: text or bytes per
        file, and the executable bit in a ``git_checkout`` lineage (X-2, #2420). The same content
        again returns the same revision; other content into a seeded cycle is refused. On the
        port since #2451, so the runtime API's one client (``create_sandbox_client``) seeds a
        product's checkout through it (SIP-0112's E.4.2)."""
        ...

    @abstractmethod
    async def release_workspace(self, cycle_id: str) -> None:
        """Remove the workspace seeded for ``cycle_id``, its tree and its revisions, once its
        consumer has recorded what it needs (#2473): the inherited baseline after
        ``record_inherited_baseline``, a source-backed run at its teardown. Idempotent: releasing an
        absent workspace is no error. Stop an application started from it first; the release takes
        the tree away beneath it. The operation evidence already journalled is kept."""

    @abstractmethod
    async def read_workspace_revision(self, revision: WorkspaceRevision) -> RevisionContent:
        """A pinned revision's files and executable bits, read from the live tree only while it
        matches the pin, as a disposable copy is taken (contract 3). SIP-0112's E.4.3 captures a
        change back from it. A tree that no longer matches is refused: nothing is returned."""
        ...

    @abstractmethod
    async def install_dependencies(self, *, revision: WorkspaceRevision) -> InstallResult:
        """Install declared dependencies into the sandbox (never shared
        installed-dependency state; read-through download caches only)."""
        ...

    @abstractmethod
    async def build_frontend(self, *, revision: WorkspaceRevision) -> BuildResult:
        """Run the stack's frontend build against the revision."""
        ...

    @abstractmethod
    async def run_backend_tests(self, *, revision: WorkspaceRevision) -> TestRunResult:
        """Run the stack's backend test suite against the revision."""
        ...

    @abstractmethod
    async def start_application(self, *, revision: WorkspaceRevision) -> StartResult:
        """Start the assembled application in the runtime unit and await
        readiness; the result carries endpoint handles and a cleanup handle."""
        ...

    @abstractmethod
    async def stop_application(
        self, *, revision: WorkspaceRevision, cleanup_handle: str
    ) -> StopResult:
        """Tear down a started application runtime using the cleanup handle
        its ``start_application`` result carried. Converges: stopping an
        already-gone runtime succeeds."""
        ...

    @abstractmethod
    async def probe_http_endpoint(
        self,
        *,
        revision: WorkspaceRevision,
        probe_id: str,
        method: str,
        path: str,
        expected_status: int | None = None,
    ) -> ProbeResult:
        """Probe a declared endpoint of the running application from outside
        the application process boundary."""
        ...

    @abstractmethod
    async def apply_workspace_patch(
        self,
        *,
        base: WorkspaceRevision,
        files: Mapping[str, FileContent | None],
        origin: str = RevisionOrigin.AGENT_PATCH,
    ) -> PatchResult:
        """Apply content changes (path → new content, ``None`` = delete) on top
        of ``base``, cutting a new revision (§4.6 boundary)."""
        ...

    @abstractmethod
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
        """Run a product's own declared command, after its setup commands, against the
        revision, in a disposable copy discarded afterwards (X-3a, #2421; SIP-0102 §11d).
        ``findings_reader``, one of ``squadops.sandbox.findings.READERS``, reads the command's
        whole output into the result's ``findings`` (#2609); an unknown one is refused."""
        ...

    @abstractmethod
    async def read_build_diagnostics(self, *, revision: WorkspaceRevision) -> DiagnosticsResult:
        """Read structured diagnostics from the revision's most recent build
        (the warm-attempt inspect step)."""
        ...
