"""LLM domain models.

Frozen dataclasses for LLM requests, responses, and chat messages.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMRequest:
    """Request for LLM text generation.

    Immutable request specification for LLMPort.generate().
    """

    prompt: str
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4000
    format: str | None = None  # "json" for structured output
    timeout_seconds: float = 180.0


@dataclass(frozen=True)
class LLMResponse:
    """Response from LLM text generation.

    Immutable response from LLMPort.generate().
    """

    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ChatMessage:
    """Chat message for conversational LLM interactions.

    Used with LLMPort.chat() for multi-turn conversations.
    """

    role: str  # "system", "user", "assistant"
    content: str
