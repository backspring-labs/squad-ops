"""
Capability Contracts domain layer.

This module implements SIP-0.8.6: Declarative capability contracts enabling
machine-readable delivery expectations, reference workloads composing
capabilities into DAGs, and deterministic acceptance checks.
"""

from squadops.capabilities.exceptions import (
    CapabilityDomainError,
    ContractNotFoundError,
    ContractValidationError,
    PathEscapeError,
    TemplateResolutionError,
    WorkloadNotFoundError,
)
from squadops.capabilities.handlers import (
    CapabilityHandler,
    ExecutionContext,
    HandlerEvidence,
    HandlerResult,
)
from squadops.capabilities.models import (
    AcceptanceCheck,
    # Report models
    AcceptanceContext,
    AcceptanceResult,
    ArtifactSpec,
    CapabilityContract,
    # Enums
    CheckType,
    FailureRecord,
    HeadlineMetrics,
    # Contract models
    InputSpec,
    LifecycleScope,
    OutputSpec,
    TaskRecord,
    TaskStatus,
    Trigger,
    ValidationReport,
    Workload,
    WorkloadRunReport,
    WorkloadStatus,
    # Workload models
    WorkloadTask,
)

__all__ = [
    # Enums
    "CheckType",
    "LifecycleScope",
    "Trigger",
    "TaskStatus",
    "WorkloadStatus",
    # Contract models
    "InputSpec",
    "OutputSpec",
    "ArtifactSpec",
    "AcceptanceCheck",
    "CapabilityContract",
    # Workload models
    "WorkloadTask",
    "Workload",
    # Report models
    "AcceptanceContext",
    "AcceptanceResult",
    "ValidationReport",
    "TaskRecord",
    "FailureRecord",
    "HeadlineMetrics",
    "WorkloadRunReport",
    # Exceptions
    "CapabilityDomainError",
    "ContractValidationError",
    "ContractNotFoundError",
    "WorkloadNotFoundError",
    "PathEscapeError",
    "TemplateResolutionError",
    # Handlers (SIP-0.8.8)
    "CapabilityHandler",
    "HandlerResult",
    "HandlerEvidence",
    "ExecutionContext",
]
