"""LLM adapter factory.

Factory function for creating LLM adapters with secret resolution.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.llm.ollama import OllamaAdapter
from adapters.llm.vllm import VLLMAdapter
from squadops.ports.llm.provider import LLMPort

if TYPE_CHECKING:
    from squadops.core.secret_manager import SecretManager


def create_llm_provider(
    provider: str = "ollama",
    secret_manager: SecretManager | None = None,
    base_url: str = "http://localhost:11434",
    default_model: str = "llama3.2",
    timeout_seconds: float = 180.0,
    **config,
) -> LLMPort:
    """Create an LLM provider.

    Args:
        provider: Provider name ("ollama" or "vllm")
        secret_manager: Optional secret manager for resolving secret:// refs
        base_url: Base URL for the LLM server (may be secret:// ref)
        default_model: Default model to use
        timeout_seconds: Request timeout
        **config: Additional provider-specific configuration

    Returns:
        LLMPort implementation

    Raises:
        ValueError: If provider is unknown
    """
    # Resolve secret:// refs via SecretManager (SIP §7.6)
    if secret_manager and base_url.startswith("secret://"):
        base_url = secret_manager.resolve(base_url[9:])

    if provider == "ollama":
        return OllamaAdapter(
            base_url=base_url,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
        )

    if provider == "vllm":
        return VLLMAdapter(
            base_url=base_url,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            api_key=config.get("api_key"),
        )

    # No fallback: an unknown provider name must fail loudly at startup rather
    # than silently running the previous one (the standing no-masking-fallbacks
    # rule). A typo in configuration is a misconfiguration, not a default.
    raise ValueError(f"Unknown LLM provider: {provider}")
