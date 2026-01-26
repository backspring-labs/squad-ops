"""
Domain exceptions for the prompt assembly system.

These exceptions represent domain-level violations that occur during
prompt assembly, validation, or integrity checking.
"""


class PromptDomainError(Exception):
    """Base exception for all prompt domain errors."""

    pass


class FragmentNotFoundError(PromptDomainError):
    """Raised when a required prompt fragment cannot be found."""

    def __init__(self, fragment_id: str, role: str | None = None):
        self.fragment_id = fragment_id
        self.role = role
        msg = f"Fragment not found: {fragment_id}"
        if role:
            msg += f" (role: {role})"
        super().__init__(msg)


class HashMismatchError(PromptDomainError):
    """Raised when a fragment's content hash does not match the manifest."""

    def __init__(self, fragment_id: str, expected: str, actual: str):
        self.fragment_id = fragment_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Hash mismatch for fragment '{fragment_id}': "
            f"expected {expected[:16]}..., got {actual[:16]}..."
        )


class MandatoryLayerMissingError(PromptDomainError):
    """Raised when a mandatory layer cannot be resolved during assembly."""

    def __init__(self, layer: str, role: str):
        self.layer = layer
        self.role = role
        super().__init__(f"Mandatory layer '{layer}' missing for role '{role}'")


class ManifestValidationError(PromptDomainError):
    """Raised when the prompt manifest fails validation."""

    def __init__(self, message: str, details: dict | None = None):
        self.details = details or {}
        super().__init__(message)
