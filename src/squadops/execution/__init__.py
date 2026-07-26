"""Execution sandbox domain (SIP-0102 — Ephemeral Application Sandbox)."""

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
    TestRunResult,
    WorkspaceRevision,
    compute_revision_id,
    is_deliverable_failure,
)
from squadops.execution.noop import NoOpExecutionSandbox

__all__ = [
    "BuildResult",
    "DiagnosticsResult",
    "InstallResult",
    "NoOpExecutionSandbox",
    "OperationName",
    "OperationResult",
    "OperationStatus",
    "PatchResult",
    "ProbeResult",
    "RevisionOrigin",
    "StartResult",
    "TestRunResult",
    "WorkspaceRevision",
    "compute_revision_id",
    "is_deliverable_failure",
]
