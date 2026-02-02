"""
Structured validation errors for configuration system.
"""


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, field: str | None = None, expected: str | None = None):
        """
        Initialize configuration validation error.

        Args:
            message: Human-readable error message
            field: Optional field name that failed validation
            expected: Optional description of expected value/type
        """
        super().__init__(message)
        self.message = message
        self.field = field
        self.expected = expected

    def __str__(self) -> str:
        """Return formatted error message."""
        parts = [self.message]
        if self.field:
            parts.append(f"Field: {self.field}")
        if self.expected:
            parts.append(f"Expected: {self.expected}")
        return " | ".join(parts)
