"""LLM domain models.

Frozen dataclasses for LLM requests, responses, and chat messages.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from dataclasses import dataclass


class ReasoningLevel:
    """How much reasoning a generation asks for — the port's vocabulary (#927).

    A level, never a provider's switch. Ollama maps it onto ``think``, an
    OpenAI-compatible surface onto whichever dial the model exposes (a toggle or
    an effort), and a provider with no control accepts it and sends nothing. It
    is a *request*, not a guarantee: an adapter maps down to what its wire can
    express and never fails a call over it.

    ``NONE`` is the level for a transcription — an output the prompt already
    determines (filling scaffold slots, a verdict from evidence, a stored
    report). The graded levels are for an argument — an output that chooses
    (authoring a design, analysing a failure). The capability declares which it
    is; see ``squadops.capabilities.reasoning_policy``.
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


REASONING_LEVELS: frozenset[str] = frozenset(
    {ReasoningLevel.NONE, ReasoningLevel.LOW, ReasoningLevel.MEDIUM, ReasoningLevel.HIGH}
)


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
    reasoning: str | None = None  # a ReasoningLevel; None = the provider's own default


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
    tokens_per_second: float | None = None
    # Reasoning tokens counted separately from content, when the provider reports them
    # (``thinking_tokens: True``). None = not reported; never zero-filled (#410, #1159).
    reasoning_tokens: int | None = None


@dataclass(frozen=True)
class ModelInfo:
    """A model the provider can serve, with whatever metadata it supplies.

    Returned by ``LLMPort.list_available_models()``. The optional fields are
    genuinely optional: a provider that cannot report size or modification time
    leaves them ``None`` rather than fabricating a value, so a caller can tell
    "not reported" from "zero" (#572's honesty rule applied to metadata).
    """

    name: str
    size_bytes: int | None = None
    modified_at: str | None = None


@dataclass(frozen=True)
class ChatMessage:
    """Chat message for conversational LLM interactions.

    Used with LLMPort.chat() for multi-turn conversations.
    """

    role: str  # "system", "user", "assistant"
    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    tokens_per_second: float | None = None
    reasoning_tokens: int | None = None  # see LLMResponse.reasoning_tokens
