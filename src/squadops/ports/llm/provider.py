"""LLM port interface.

Abstract base class for LLM provider adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse


class LLMPort(ABC):
    """Port interface for LLM providers.

    Adapters must implement generate, chat, list_models, refresh_models, and health.
    """

    @property
    def default_model(self) -> str:
        """Return the default model name used by this provider."""
        return "unknown"

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text from a prompt.

        Args:
            request: The LLM request specification

        Returns:
            LLM response with generated text

        Raises:
            LLMConnectionError: Failed to connect to provider
            LLMTimeoutError: Request timed out
            LLMModelNotFoundError: Requested model not available
        """
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatMessage:
        """Chat with the LLM using message history.

        Args:
            messages: List of chat messages (conversation history)
            model: Optional model override
            max_tokens: Maximum completion tokens (adapter default if None)
            temperature: Sampling temperature (adapter default if None)
            timeout_seconds: Request timeout (adapter default if None)

        Returns:
            Assistant's response message

        Raises:
            LLMConnectionError: Failed to connect to provider
            LLMTimeoutError: Request timed out
        """
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response as plain text chunks.

        Text-only streaming contract (SIP-0085). Returns an async iterator
        of string chunks. Richer event types (tool calls, usage metadata)
        are not supported in this contract.

        Same parameters as chat(). All default None for adapter fallback.
        """
        ...
        yield  # pragma: no cover — makes this a proper async generator for ABC

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models (sync, returns cached list).

        Returns cached list. May be empty if refresh_models() has not been called.
        Adapters MUST NOT perform network I/O in this method.

        Returns:
            List of available model names (may be empty)
        """
        ...

    @abstractmethod
    async def refresh_models(self) -> list[str]:
        """Refresh and return available models (async, performs HTTP if needed).

        Updates the internal cache. Call periodically or on demand.
        Wiring is responsible for calling this after construction.

        Returns:
            Updated list of available model names
        """
        ...

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Check provider health.

        Returns:
            Health status dictionary with at least {"healthy": bool}
        """
        ...
