"""
Domain exceptions for the capability contracts system.

These exceptions represent domain-level violations that occur during
contract validation, workload execution, or acceptance checking.
"""


class CapabilityDomainError(Exception):
    """Base exception for all capability domain errors."""

    pass


class ContractValidationError(CapabilityDomainError):
    """Raised when a capability contract fails validation."""

    def __init__(self, message: str, details: dict | None = None):
        self.details = details or {}
        super().__init__(message)


class ContractNotFoundError(CapabilityDomainError):
    """Raised when a capability contract cannot be found."""

    def __init__(self, capability_id: str):
        self.capability_id = capability_id
        super().__init__(f"Contract not found: {capability_id}")


class WorkloadNotFoundError(CapabilityDomainError):
    """Raised when a workload definition cannot be found."""

    def __init__(self, workload_id: str):
        self.workload_id = workload_id
        super().__init__(f"Workload not found: {workload_id}")


class PathEscapeError(CapabilityDomainError):
    """Raised when a path attempts to escape the chroot boundary."""

    def __init__(self, path: str, chroot: str):
        self.path = path
        self.chroot = chroot
        super().__init__(
            f"Path escape attempt: '{path}' escapes chroot boundary '{chroot}'"
        )


class TemplateResolutionError(CapabilityDomainError):
    """Raised when a template variable cannot be resolved."""

    def __init__(self, template: str, variable: str):
        self.template = template
        self.variable = variable
        super().__init__(f"Cannot resolve template variable '{variable}' in: {template}")
