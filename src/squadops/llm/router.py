"""LLM router domain service.

Pass-through router for 0.8.7. Real routing policy in 0.8.8.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse

if TYPE_CHECKING:
    from squadops.ports.llm.provider import LLMPort


class LLMRouter:
    """Route LLM requests to appropriate provider.

    In 0.8.7, this is a pass-through to a single provider.
    In 0.8.8, this will add model selection based on request metadata / task type.

    Wiring ensures router is always used (bundle returns router, not raw adapter).
    """

    def __init__(self, provider: LLMPort):
        """Initialize router with a provider.

        Args:
            provider: The LLM provider to route requests to
        """
        self._provider = provider

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text from prompt.

        Args:
            request: The LLM request specification

        Returns:
            LLM response with generated text
        """
        # 0.8.7: Pass-through to single provider
        # 0.8.8: Add model selection based on request metadata / task type
        return await self._provider.generate(request)

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatMessage:
        """Chat with the LLM.

        Args:
            messages: List of chat messages
            model: Optional model override
            max_tokens: Maximum completion tokens (adapter default if None)
            temperature: Sampling temperature (adapter default if None)
            timeout_seconds: Request timeout (adapter default if None)

        Returns:
            Assistant's response message
        """
        return await self._provider.chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat response as plain text chunks.

        Pass-through to provider's chat_stream().
        """
        async for chunk in self._provider.chat_stream(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        ):
            yield chunk

    def list_models(self) -> list[str]:
        """List available models (sync, returns cached list).

        Returns:
            List of available model names
        """
        return self._provider.list_models()

    async def refresh_models(self) -> list[str]:
        """Refresh and return available models.

        Returns:
            Updated list of available model names
        """
        return await self._provider.refresh_models()

    async def health(self) -> dict[str, Any]:
        """Check provider health.

        Returns:
            Health status dictionary
        """
        return await self._provider.health()
