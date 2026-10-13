"""The per-call model metrics every handler emits through ``MetricsPort`` (#2204, #2203).

The decode rate lived only in a log line (``LLM throughput: ... t/s``), so nothing kept it over
time. These are the numbers the host panel, the Grafana dashboard and SIP-0111's engine
comparison read: decode rate, prompt and completion tokens, and the prefill and load time that
the decode rate hides on a long prompt.

Labels stay few, and each takes a bounded set of values: the role, the task type, the model, the
engine that served the call, and whether the call was long. A peak decode rate is read over long
calls only, because the rate falls as output grows, and a plain peak reports the shortest call
(#2204: on 2026-10-09 the three fastest calls were 20-token builder calls).

Each instrument carries its own bucket boundaries (#2260). OpenTelemetry's defaults (0, 5, 10, 25 …
10,000) put nearly every decode rate in one bucket and over half the 27B's prompts above the last,
so no percentile or peak could be read. The scales below come from the 27B's held-out run
(2026-10-12, 132 calls on each engine): decode 21–37 tok/s on Ollama and 32–106 on TensorFold;
prompts 4,527–29,055 tokens; completions 20–12,288; calls 7–444 s; Ollama's prefill 1.5–39 s.
"""

from __future__ import annotations

from squadops.ports.telemetry.metrics import MetricsPort

LLM_DECODE_TOKENS_PER_SECOND = "llm_decode_tokens_per_second"
LLM_PROMPT_TOKENS = "llm_prompt_tokens"
LLM_COMPLETION_TOKENS = "llm_completion_tokens"
LLM_PREFILL_SECONDS = "llm_prefill_seconds"
LLM_LOAD_SECONDS = "llm_load_seconds"
LLM_CALL_SECONDS = "llm_call_seconds"

#: Each instrument's bucket upper bounds. Kept beside the names, so a name and its scale are
#: defined once. A bound is a bucket edge, so the edges sit where the readings are dense: every
#: 2 tok/s through the 27B's decode range, and the registry's 8,192 and 12,288-token caps.
LLM_HISTOGRAM_BOUNDARIES: dict[str, tuple[float, ...]] = {
    LLM_DECODE_TOKENS_PER_SECOND: (1, 2, 5, 8, *range(10, 42, 2))
    + (45, 50, 55, 60, 70, 80, 90, 100, 125, 150),
    LLM_PROMPT_TOKENS: (500, *range(1000, 8001, 1000), *range(10_000, 16_001, 2000))
    + (*range(20_000, 32_001, 4000), *range(40_000, 64_001, 8000))
    + (96_000, 128_000, 192_000, 256_000),
    LLM_COMPLETION_TOKENS: (16, 32, 64, 128, 256, 512, 1000, 1500, *range(2000, 7001, 1000))
    + (8192, 10_000, 12_288, 16_384, 32_768),
    LLM_PREFILL_SECONDS: (0.1, 0.25, 0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30, 45, 60, 90, 120, 180),
    LLM_LOAD_SECONDS: (0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120),
    LLM_CALL_SECONDS: (1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300, 420, 600)
    + (900, 1200, 1800, 3600),
}

#: A call is "long" at this many completion tokens or more (#2204's peak rule).
LONG_CALL_TOKENS = 1000


def _number(value: object) -> float | None:
    """A reported count or duration, or ``None``: a provider that reports nothing, or anything
    that isn't a number, emits nothing rather than raising inside a handler."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def record_llm_call(
    metrics: MetricsPort,
    usage: object,
    *,
    role: str,
    task_type: str,
    model: str,
    engine: str,
    duration_ms: float,
) -> None:
    """Emit one model call's metrics. A value the provider did not report is not emitted, never
    zero-filled: a missing decode rate is "not reported", not "zero tokens a second"."""
    completion = _number(getattr(usage, "completion_tokens", None))
    labels = {
        "role": role,
        "task_type": task_type,
        "model": model,
        "engine": engine,
        "long": "true" if (completion or 0) >= LONG_CALL_TOKENS else "false",
    }
    duration = _number(duration_ms)
    observed = (
        (LLM_DECODE_TOKENS_PER_SECOND, _number(getattr(usage, "tokens_per_second", None))),
        (LLM_PROMPT_TOKENS, _number(getattr(usage, "prompt_tokens", None))),
        (LLM_COMPLETION_TOKENS, completion),
        (LLM_PREFILL_SECONDS, _number(getattr(usage, "prompt_eval_seconds", None))),
        (LLM_LOAD_SECONDS, _number(getattr(usage, "load_seconds", None))),
        (LLM_CALL_SECONDS, duration / 1000 if duration is not None else None),
    )
    for name, value in observed:
        if value is not None:
            metrics.histogram(name, value, labels, boundaries=LLM_HISTOGRAM_BOUNDARIES[name])
