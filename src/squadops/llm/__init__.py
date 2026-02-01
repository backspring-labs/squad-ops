"""LLM domain layer.

Provides domain models and services for LLM operations:
- LLMRequest, LLMResponse: Request/response models for text generation
- ChatMessage: Model for conversational interactions
- LLMRouter: Domain service for routing requests

Part of SIP-0.8.7 Infrastructure Ports Migration.
"""
from squadops.llm.exceptions import (
    LLMConnectionError,
    LLMError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse
from squadops.llm.router import LLMRouter

__all__ = [
    "ChatMessage",
    "LLMConnectionError",
    "LLMError",
    "LLMModelNotFoundError",
    "LLMRateLimitError",
    "LLMRequest",
    "LLMResponse",
    "LLMRouter",
    "LLMTimeoutError",
]
