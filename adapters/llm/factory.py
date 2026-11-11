"""LLM adapter factory.

Factory function for creating LLM adapters with secret resolution.
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.llm.atlas import AtlasAdapter
from adapters.llm.ollama import OllamaAdapter
from adapters.llm.scripted import ScriptedLLMAdapter, ScriptedModelRouter
from adapters.llm.tensorfold import TensorFoldAdapter
from adapters.llm.vllm import VLLMAdapter
from squadops.llm.script import ScriptLibrary
from squadops.ports.llm.provider import LLMPort
from squadops.ports.llm.script_positions import ScriptPositionsPort

if TYPE_CHECKING:
    from squadops.core.secret_manager import SecretManager

    from squadops.config.schema import CommsConfig

#: How long a scripted cycle's answer positions are kept after its last scripted call (#3005).
#: Long past any cycle's life, so a cycle resumed after a pause or a reboot finds its place.
SCRIPT_POSITIONS_TTL_SECONDS = 14 * 24 * 3600


def create_llm_provider(
    provider: str,
    secret_manager: SecretManager | None = None,
    base_url: str = "http://localhost:11434",
    default_model: str = "llama3.2",
    timeout_seconds: float = 180.0,
    **config,
) -> LLMPort:
    """Create an LLM provider.

    Args:
        provider: Provider name ("ollama", "vllm", "atlas" or "tensorfold"). Required — no
            default (#1157): the factory's own rule below refuses an unknown name, and a
            *missing* one used to fall back to Ollama the same silent way.
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

    if provider == "atlas":
        return AtlasAdapter(
            base_url=base_url,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            api_key=config.get("api_key"),
        )

    if provider == "tensorfold":
        return TensorFoldAdapter(
            base_url=base_url,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            api_key=config.get("api_key"),
        )

    # No fallback: an unknown provider name must fail loudly at startup rather
    # than silently running the previous one (the standing no-masking-fallbacks
    # rule). A typo in configuration is a misconfiguration, not a default.
    raise ValueError(f"Unknown LLM provider: {provider}")


def with_scripted_model(
    engine: LLMPort, positions: ScriptPositionsPort, library: ScriptLibrary | None = None
) -> LLMPort:
    """The deploy's LLM port: ``engine``, also serving the model ``scripted`` from recorded
    scripts (#2495).

    Every composition root that builds the engine wraps it here, so the runtime (which checks a
    cycle's models at create) and the agents (which answer them) agree that the deploy serves
    ``scripted``. A call naming any other model reaches ``engine`` unchanged; one naming
    ``scripted`` never does. ``positions`` keeps each scripted cycle's answer positions
    (:func:`create_script_positions` on a deploy, #3005), and is required: a store held in one
    process loses a cycle's place when that process restarts. ``library`` is the package's own
    scripts unless a test names another.
    """
    return ScriptedModelRouter(
        engine,
        ScriptedLLMAdapter(library if library is not None else ScriptLibrary.packaged(), positions),
    )


def create_script_positions(comms: CommsConfig) -> ScriptPositionsPort:
    """Each scripted cycle's answer positions, in the stack's Redis (``comms.redis.url``), kept
    for :data:`SCRIPT_POSITIONS_TTL_SECONDS` after a cycle's last scripted call (#3005)."""
    from adapters.llm.script_positions import RedisScriptPositions

    return RedisScriptPositions.from_url(comms.redis.url, SCRIPT_POSITIONS_TTL_SECONDS)
