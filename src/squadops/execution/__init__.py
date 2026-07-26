"""Execution sandbox domain (SIP-0102 — Ephemeral Application Sandbox)."""

from squadops.execution.evidence import OperationEvidenceJournal, result_to_dict
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
    compute_revision_id,
    is_deliverable_failure,
)
from squadops.execution.noop import NoOpExecutionSandbox
from squadops.execution.service import ExecutionService
from squadops.execution.workspace import (
    AlreadySeededError,
    StaleBaseRevisionError,
    WorkspaceEscapeError,
    WorkspaceStore,
    WorkspaceStoreError,
)

__all__ = [
    "AlreadySeededError",
    "BuildResult",
    "DiagnosticsResult",
    "ExecutionService",
    "InstallResult",
    "NoOpExecutionSandbox",
    "OperationEvidenceJournal",
    "OperationName",
    "OperationResult",
    "OperationStatus",
    "PatchResult",
    "ProbeResult",
    "RevisionOrigin",
    "StaleBaseRevisionError",
    "StartResult",
    "StopResult",
    "TestRunResult",
    "WorkspaceEscapeError",
    "WorkspaceRevision",
    "WorkspaceStore",
    "WorkspaceStoreError",
    "compute_revision_id",
    "is_deliverable_failure",
    "result_to_dict",
]
