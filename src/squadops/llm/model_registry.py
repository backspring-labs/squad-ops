"""Model context registry (SIP-0073).

Code-defined registry mapping model names to context window and default
completion token limits.  V1 uses exact-match lookup with strip() only —
no alias or tag normalization.

Registry keys must exactly match ``LLMConfig.model`` values used in
active profiles (e.g. ``qwen2.5:7b``, not ``qwen2.5-7b``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """Context window and completion budget for a known model."""

    name: str
    context_window: int
    default_max_completion: int


MODEL_SPECS: dict[str, ModelSpec] = {
    "qwen2.5:7b": ModelSpec(
        name="qwen2.5:7b",
        context_window=32_768,
        default_max_completion=4_096,
    ),
    "qwen2.5:32b": ModelSpec(
        name="qwen2.5:32b",
        context_window=32_768,
        default_max_completion=8_192,
    ),
    "qwen2.5:72b": ModelSpec(
        name="qwen2.5:72b",
        context_window=131_072,
        default_max_completion=16_384,
    ),
    "llama3:70b": ModelSpec(
        name="llama3:70b",
        context_window=131_072,
        default_max_completion=16_384,
    ),
}


def get_model_spec(name: str) -> ModelSpec | None:
    """Look up model spec by exact name (stripped of whitespace).

    Returns None for unknown models — callers should fall back to
    capability-only budgets.
    """
    return MODEL_SPECS.get(name.strip())
