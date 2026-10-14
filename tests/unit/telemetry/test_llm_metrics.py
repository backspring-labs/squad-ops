"""The per-call model metrics (#2204, #2203): what each handler call emits through MetricsPort."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from squadops.telemetry.llm_metrics import (
    LLM_CALL_SECONDS,
    LLM_COMPLETION_TOKENS,
    LLM_DECODE_TOKENS_PER_SECOND,
    LLM_HISTOGRAM_BOUNDARIES,
    LLM_LOAD_SECONDS,
    LLM_PREFILL_SECONDS,
    LLM_PROMPT_TOKENS,
    record_llm_call,
)


class _Recorder:
    def __init__(self) -> None:
        self.observed: list[tuple[str, float, dict[str, str]]] = []
        self.boundaries: dict[str, tuple[float, ...] | None] = {}

    def histogram(self, name, value, labels=None, *, boundaries=None):
        self.observed.append((name, value, labels or {}))
        self.boundaries[name] = boundaries


def _usage(**overrides):
    base = dict(
        prompt_tokens=9605,
        completion_tokens=4922,
        tokens_per_second=31.0,
        prompt_eval_seconds=4.2,
        load_seconds=0.1,
    )
    return SimpleNamespace(**{**base, **overrides})


def test_a_call_emits_each_number_once_with_its_labels():
    """Bug caught: the decode rate kept only as a log line, so nothing charted it over time."""
    metrics = _Recorder()

    record_llm_call(
        metrics,
        _usage(),
        role="qa",
        task_type="qa.test",
        model="qwen3.8:27b",
        engine="ollama",
        duration_ms=170_000,
    )

    assert {name: value for name, value, _ in metrics.observed} == {
        LLM_DECODE_TOKENS_PER_SECOND: 31.0,
        LLM_PROMPT_TOKENS: 9605.0,
        LLM_COMPLETION_TOKENS: 4922.0,
        LLM_PREFILL_SECONDS: 4.2,
        LLM_LOAD_SECONDS: 0.1,
        LLM_CALL_SECONDS: 170.0,
    }
    assert {frozenset(labels.items()) for _, _, labels in metrics.observed} == {
        frozenset(
            {
                "role": "qa",
                "task_type": "qa.test",
                "model": "qwen3.8:27b",
                "engine": "ollama",
                "long": "true",
            }.items()
        )
    }


def test_each_instrument_is_recorded_on_its_own_ascending_scale():
    """#2260. Bug caught: an instrument recorded with no boundaries, or with boundaries out of
    order, which the SDK drops for its defaults: the decode rate back in one 25–50 bucket."""
    metrics = _Recorder()

    record_llm_call(
        metrics, _usage(), role="qa", task_type="t", model="m", engine="ollama", duration_ms=1
    )

    assert metrics.boundaries == LLM_HISTOGRAM_BOUNDARIES
    for name, bounds in metrics.boundaries.items():
        assert list(bounds) == sorted(set(bounds)), name


@pytest.mark.parametrize(("tokens", "long"), [(999, "false"), (1000, "true"), (None, "false")])
def test_a_call_is_long_at_a_thousand_completion_tokens(tokens, long):
    """#2204's peak rule. Bug caught: the peak decode rate reporting the shortest call, since the
    rate falls as output grows (the 2026-10-09 peak was three 20-token builder calls)."""
    metrics = _Recorder()

    record_llm_call(
        metrics,
        _usage(completion_tokens=tokens),
        role="dev",
        task_type="t",
        model="m",
        engine="ollama",
        duration_ms=1,
    )

    assert {labels["long"] for _, _, labels in metrics.observed} == {long}


def test_a_value_the_provider_did_not_report_is_not_emitted():
    """Bug caught: a provider that reports no prefill time charted as zero seconds of prefill."""
    metrics = _Recorder()

    record_llm_call(
        metrics,
        _usage(prompt_eval_seconds=None, load_seconds=None, tokens_per_second=None),
        role="dev",
        task_type="t",
        model="m",
        engine="ollama",
        duration_ms=1000,
    )

    names = {name for name, _, _ in metrics.observed}
    assert names == {LLM_PROMPT_TOKENS, LLM_COMPLETION_TOKENS, LLM_CALL_SECONDS}


def test_a_value_that_is_not_a_number_is_not_emitted_and_never_raises():
    """Bug caught: a handler failing its task because a provider (or a test double) returned
    something other than a number for a count."""
    metrics = _Recorder()

    record_llm_call(
        metrics,
        _usage(completion_tokens=object(), tokens_per_second="fast", prompt_tokens=True),
        role="dev",
        task_type="t",
        model="m",
        engine="ollama",
        duration_ms=None,
    )

    names = {name for name, _, _ in metrics.observed}
    assert names == {LLM_PREFILL_SECONDS, LLM_LOAD_SECONDS}
    assert {labels["long"] for _, _, labels in metrics.observed} == {"false"}
