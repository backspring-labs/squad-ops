"""Model context registry (SIP-0073).

Code-defined registry mapping model names to context window and default
completion token limits.  V1 uses exact-match lookup with strip() only —
no alias or tag normalization.

Registry keys must exactly match ``LLMConfig.model`` values used in
active profiles (e.g. ``qwen2.5:7b``, not ``qwen2.5-7b``).
"""

from __future__ import annotations

from dataclasses import dataclass


class ReasoningControl:
    """Which reasoning dial a model exposes — a model fact, not a provider one (#927).

    The same weights reach their reasoning channel the same way on every
    server; what differs per provider is only the wire spelling, which the
    adapter owns. Declared per entry, no default: a model whose dial is not
    stated is a registry gap, not a model that reasons silently.
    """

    NONE = "none"  # no reasoning channel to control (qwen2.5, llama3)
    TOGGLE = "toggle"  # on/off only — qwen3-family ``think`` / ``enable_thinking``
    EFFORT = "effort"  # graded low/medium/high — gpt-oss-family ``reasoning_effort``


@dataclass(frozen=True)
class ModelSpec:
    """Context window, completion budget and reasoning dial for a known model."""

    name: str
    context_window: int
    default_max_completion: int
    reasoning_control: str


MODEL_SPECS: dict[str, ModelSpec] = {
    "qwen2.5:7b": ModelSpec(
        name="qwen2.5:7b",
        context_window=32_768,
        default_max_completion=4_096,
        reasoning_control=ReasoningControl.NONE,
    ),
    "qwen2.5:32b": ModelSpec(
        name="qwen2.5:32b",
        context_window=32_768,
        default_max_completion=8_192,
        reasoning_control=ReasoningControl.NONE,
    ),
    "qwen2.5:72b": ModelSpec(
        name="qwen2.5:72b",
        context_window=131_072,
        default_max_completion=16_384,
        reasoning_control=ReasoningControl.NONE,
    ),
    # qwen3.6:27b is the uniform model used by the full
    # profile on DGX Spark. Without a registry entry, get_model_spec()
    # returned None for spark cycles and the per-model completion clamp at
    # cycle_tasks._resolve_model_budget never fired — capability defaults
    # passed through unchecked, so the python_cli fallback (4000 tokens)
    # silently capped React/fullstack work that should have run under
    # higher per-capability budgets. 8192 here intentionally clamps the
    # fullstack_fastapi_react capability (12000) downward: empirically
    # qwen3.6:27b at ~10 t/s on Spark takes ~13 min for 8K tokens, and
    # outputs longer than that drift in coherence. Fullstack work should
    # decompose into smaller per-file dev tasks rather than rely on a
    # higher single-call ceiling.
    "qwen3.6:27b": ModelSpec(
        name="qwen3.6:27b",
        context_window=131_072,
        default_max_completion=8_192,
        # qwen3-family: thinking is on by default and switchable per request.
        # #924 measured the same fill brief at 5,727 completion tokens with it
        # on and 413 with it off — the dial is the budget.
        reasoning_control=ReasoningControl.TOGGLE,
    ),
    # qwen3.8:27b is the V38 comparison arm (full-38 profile). The completion
    # clamp is deliberately IDENTICAL to qwen3.6:27b's: the V38 window compares
    # stacks, and an unclamped 3.8 (capability ceilings pass through when this
    # entry is absent — the exact gap the 3.6 comment above narrates) would hand
    # arm B a 12,000-token dev ceiling arm A never had. Discovered as V38
    # shakedown finding 3; at 3.8's measured ~24 t/s, 8,192 tokens is ~6 min.
    "qwen3.8:27b": ModelSpec(
        name="qwen3.8:27b",
        context_window=262_144,
        default_max_completion=8_192,
        reasoning_control=ReasoningControl.TOGGLE,
    ),
    # Atlas serves models by HuggingFace path, so the same weights carry a second name
    # (SIP-0106 §3.4 — model identity is provider-scoped). The window is the one the
    # local-spark recipe serves (`--max-seq-len 32768`, #1158), not the checkpoint's
    # native 262K: Atlas rejects a prompt past the served window, and the prompt-size
    # guard reads this number. The completion clamp matches the Ollama entry above.
    "Qwen/Qwen3.8-27B-FP8": ModelSpec(
        name="Qwen/Qwen3.8-27B-FP8",
        context_window=32_768,
        default_max_completion=8_192,
        reasoning_control=ReasoningControl.TOGGLE,
    ),
    "llama3:70b": ModelSpec(
        name="llama3:70b",
        context_window=131_072,
        default_max_completion=16_384,
        reasoning_control=ReasoningControl.NONE,
    ),
}


def get_model_spec(name: str) -> ModelSpec | None:
    """Look up model spec by exact name (stripped of whitespace).

    Returns None for unknown models — callers should fall back to
    capability-only budgets.
    """
    return MODEL_SPECS.get(name.strip())
