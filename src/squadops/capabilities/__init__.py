"""
Capability Contracts domain layer.

This module implements SIP-0.8.6: Declarative capability contracts enabling
machine-readable delivery expectations, reference workloads composing
capabilities into DAGs, and deterministic acceptance checks.
"""

from squadops.capabilities.models import (
    # Enums
    CheckType,
    LifecycleScope,
    Trigger,
    TaskStatus,
    WorkloadStatus,
    # Contract models
    InputSpec,
    OutputSpec,
    ArtifactSpec,
    AcceptanceCheck,
    CapabilityContract,
    # Workload models
    WorkloadTask,
    Workload,
    # Report models
    AcceptanceContext,
    AcceptanceResult,
    ValidationReport,
    TaskRecord,
    FailureRecord,
    HeadlineMetrics,
    WorkloadRunReport,
)
from squadops.capabilities.exceptions import (
    CapabilityDomainError,
    ContractValidationError,
    ContractNotFoundError,
    WorkloadNotFoundError,
    PathEscapeError,
    TemplateResolutionError,
)
from squadops.capabilities.handlers import (
    CapabilityHandler,
    HandlerResult,
    HandlerEvidence,
    ExecutionContext,
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
