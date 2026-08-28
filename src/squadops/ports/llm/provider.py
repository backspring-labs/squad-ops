"""LLM port interface.

Abstract base class for LLM provider adapters.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse, ModelInfo


class LLMCapability:
    """Capability names declared by :meth:`LLMPort.capabilities`.

    Constants, not bare strings, so a caller cannot ask about a capability that
    does not exist by mistyping it (#559's strings-boundary rule).
    """

    MODEL_LISTING = "model_listing"
    MODEL_MANAGEMENT = "model_management"
    STREAMING_USAGE = "streaming_usage"
    THINKING_TOKENS = "thinking_tokens"
    REASONING_CONTROL = "reasoning_control"


class LLMPort(ABC):
    """Port interface for LLM providers.

    Adapters must implement generate, chat, list_models, refresh_models, and health.

    Optional surfaces — model listing and model management — are declared through
    :meth:`capabilities` and default to unsupported, so callers ask the port what
    it can do rather than inspecting which adapter class they were handed.
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
        reasoning: str | None = None,
    ) -> ChatMessage:
        """Chat with the LLM using message history.

        Args:
            messages: List of chat messages (conversation history)
            model: Optional model override
            max_tokens: Maximum completion tokens (adapter default if None)
            temperature: Sampling temperature (adapter default if None)
            timeout_seconds: Request timeout (adapter default if None)
            reasoning: A :class:`~squadops.llm.models.ReasoningLevel` — how much
                reasoning this generation wants. ``None`` sends nothing and
                leaves the provider's own default in force. A request, not a
                guarantee: the adapter maps it onto whatever dial the wire has
                (Ollama ``think``, a chat-template toggle, an effort) and an
                adapter with no dial accepts it silently — see
                ``capabilities()[REASONING_CONTROL]`` (#927).

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
        reasoning: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response as plain text chunks.

        Text-only streaming contract (SIP-0085). Returns an async iterator
        of string chunks. Richer event types (tool calls, usage metadata)
        are not supported in this contract.

        Same parameters as chat(). All default None for adapter fallback.
        """
        ...
        yield  # pragma: no cover — makes this a proper async generator for ABC

    async def chat_stream_with_usage(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
    ) -> ChatMessage:
        """Stream chat internally for connection liveness, return complete ChatMessage with usage.

        Uses streaming transport to keep the connection alive during long-running
        inference, but returns only the final assembled response — no partial chunks
        are delivered to callers. Usage metadata (token counts, tokens_per_second)
        is best-effort and defaults to None when absent.

        Default implementation falls back to chat(). Providers may override to
        implement true streaming with usage capture.

        Same failure semantics as chat(): raises LLMTimeoutError / LLMConnectionError.
        """
        return await self.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            reasoning=reasoning,
        )

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

    # -------------------------------------------------------------------
    # Optional surfaces — declared, never inferred
    # -------------------------------------------------------------------

    def capabilities(self) -> dict[str, bool]:
        """Return which optional surfaces this provider actually supports.

        Every flag is a contract with future callers: it must describe what the
        provider *does*, not what its backend could be configured to do. A flag
        that overstates the implementation is worse than a missing feature — the
        caller builds on it and fails at runtime instead of at the boundary
        (#572, the same rule the queue port carries).

        Keys are :class:`LLMCapability` constants:

        - ``model_listing``: :meth:`list_available_models` is implemented.
        - ``model_management``: :meth:`pull_model` / :meth:`delete_model` are
          implemented. Hosted providers generally cannot manage local weights.
        - ``streaming_usage``: :meth:`chat_stream_with_usage` reports real token
          counts rather than falling back to :meth:`chat`.
        - ``thinking_tokens``: reasoning tokens are reported separately from
          content. False here does not mean the model does not think — only that
          this adapter cannot distinguish the two (#410).
        - ``reasoning_control``: a ``reasoning`` level passed to the generation
          methods changes what is sent on the wire. False means the level is
          accepted and dropped — the call still succeeds, the model keeps its
          own posture (#927).

        Defaults to all-False: an adapter that declares nothing is treated as
        supporting nothing. Failing closed keeps a silent omission from
        presenting as a working feature.
        """
        return {
            LLMCapability.MODEL_LISTING: False,
            LLMCapability.MODEL_MANAGEMENT: False,
            LLMCapability.STREAMING_USAGE: False,
            LLMCapability.THINKING_TOKENS: False,
            LLMCapability.REASONING_CONTROL: False,
        }

    def supports(self, capability: str) -> bool:
        """Whether ``capability`` is declared. Unknown names are False."""
        return self.capabilities().get(capability, False)

    async def list_available_models(self) -> list[ModelInfo]:
        """List models the provider can serve, with metadata where available.

        Distinct from :meth:`refresh_models`, which maintains the name-only cache
        read by :meth:`list_models`. This is the metadata-bearing listing used by
        operator surfaces that show size and modification time.

        Raises:
            NotImplementedError: when ``model_listing`` is not declared. Raising
                rather than returning ``[]`` keeps "cannot enumerate" distinct
                from "enumerated nothing" — an empty list would read downstream
                as *no models present* and block work that should proceed.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support model listing; "
            f"capabilities()['{LLMCapability.MODEL_LISTING}'] is False."
        )

    async def pull_model(self, model_name: str) -> None:
        """Fetch a model into the provider's local store.

        Raises:
            NotImplementedError: when ``model_management`` is not declared.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support model management; "
            f"capabilities()['{LLMCapability.MODEL_MANAGEMENT}'] is False."
        )

    async def delete_model(self, model_name: str) -> None:
        """Remove a model from the provider's local store.

        Raises:
            NotImplementedError: when ``model_management`` is not declared.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support model management; "
            f"capabilities()['{LLMCapability.MODEL_MANAGEMENT}'] is False."
        )
