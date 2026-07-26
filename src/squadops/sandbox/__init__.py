"""Execution sandbox domain (SIP-0102 — Ephemeral Application Sandbox)."""

from squadops.sandbox.evidence import OperationEvidenceJournal, result_to_dict
from squadops.sandbox.models import (
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
from squadops.sandbox.noop import NoOpExecutionSandbox
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import (
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
    "SandboxService",
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
