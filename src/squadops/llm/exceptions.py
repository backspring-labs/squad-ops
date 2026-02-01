"""LLM domain exceptions.

Domain-prefixed exceptions to avoid collision with Python built-ins.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""


class LLMError(Exception):
    """Base exception for LLM operations."""

    pass


class LLMConnectionError(LLMError):
    """Failed to connect to LLM provider."""

    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    pass


class LLMModelNotFoundError(LLMError):
    """Requested model not found or not available."""

    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""

    pass
