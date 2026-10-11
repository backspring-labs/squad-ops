"""The per-call model metrics every handler emits through ``MetricsPort`` (#2204, #2203).

The decode rate lived only in a log line (``LLM throughput: ... t/s``), so nothing kept it over
time. These are the numbers the host panel, the Grafana dashboard and SIP-0111's engine
comparison read: decode rate, prompt and completion tokens, and the prefill and load time that
the decode rate hides on a long prompt.

Labels stay few, and each takes a bounded set of values: the role, the task type, the model, and
whether the call was long. A peak decode rate is read over long calls only, because the rate falls
as output grows, and a plain peak reports the shortest call (#2204: on 2026-10-09 the three
fastest calls were 20-token builder calls).
"""

from __future__ import annotations

from squadops.ports.telemetry.metrics import MetricsPort

LLM_DECODE_TOKENS_PER_SECOND = "llm_decode_tokens_per_second"
LLM_PROMPT_TOKENS = "llm_prompt_tokens"
LLM_COMPLETION_TOKENS = "llm_completion_tokens"
LLM_PREFILL_SECONDS = "llm_prefill_seconds"
LLM_LOAD_SECONDS = "llm_load_seconds"
LLM_CALL_SECONDS = "llm_call_seconds"

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
    duration_ms: float,
) -> None:
    """Emit one model call's metrics. A value the provider did not report is not emitted, never
    zero-filled: a missing decode rate is "not reported", not "zero tokens a second"."""
    completion = _number(getattr(usage, "completion_tokens", None))
    labels = {
        "role": role,
        "task_type": task_type,
        "model": model,
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
            metrics.histogram(name, value, labels)
