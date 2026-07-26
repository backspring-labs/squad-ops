"""Execution sandbox port (SIP-0102 §4.4).

The agent-facing surface of the Ephemeral Application Sandbox: typed,
policy-bearing operations with structured semantic results. There is no
generic shell operation and no safelist to extend. Every operation executes
against an explicit workspace revision (§4.6) — never "whatever is in the
directory."

Adapters own container mechanics; callers never see a container runtime. The
NoOp adapter (``squadops.execution.noop``) is the unconfigured default: every
operation reports ``ran=False`` and callers keep today's in-process behavior.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from squadops.execution.models import (
    BuildResult,
    DiagnosticsResult,
    InstallResult,
    PatchResult,
    ProbeResult,
    RevisionOrigin,
    StartResult,
    StopResult,
    TestRunResult,
    WorkspaceRevision,
)


class ExecutionSandboxPort(ABC):
    """Port for typed execution operations against a cycle workspace."""

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
        files: Mapping[str, str | None],
        origin: str = RevisionOrigin.AGENT_PATCH,
    ) -> PatchResult:
        """Apply content changes (path → new content, ``None`` = delete) on top
        of ``base``, cutting a new revision (§4.6 boundary)."""
        ...

    @abstractmethod
    async def read_build_diagnostics(self, *, revision: WorkspaceRevision) -> DiagnosticsResult:
        """Read structured diagnostics from the revision's most recent build
        (the warm-attempt inspect step)."""
        ...
