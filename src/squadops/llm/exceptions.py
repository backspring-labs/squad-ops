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


class LLMContextOverflowError(LLMError):
    """The prompt did not fit the window the server serves (SIP-0111 §5.2).

    Infrastructure, never the work product's failure: the same prompt fails the same way, so it
    is not retried, and no repair can fix it. The prompt-size guard reads the registry's window,
    so an overflow means the registry and the server disagree, which is a deploy defect. The
    task is held (``TaskOutcome.BLOCKED``) with :meth:`evidence`.
    """

    def __init__(
        self, message: str, *, served_window: int | None = None, prompt_tokens: int | None = None
    ):
        super().__init__(message)
        self.served_window = served_window
        self.prompt_tokens = prompt_tokens

    def evidence(self) -> dict[str, int | str | None]:
        return {
            "reason": "context_overflow",
            "served_window": self.served_window,
            "prompt_tokens": self.prompt_tokens,
            "message": str(self),
        }
