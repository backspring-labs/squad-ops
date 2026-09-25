"""LLM usage, accounted at the one LLM seam and carried to the run (SIP-0108 §4.1).

The scorecard's efficiency dimension reads tokens and calls per run and per task type. Nothing
stored them: ``_llm_call`` records every generation to the observability port, and the
production adapter is LangFuse — the drill-down lane, never the ledger. This is the ledger.

**Every invocation contributes exactly once, success or failure.** A handler's success path is
not the source, because undercounting failed or retried calls would make the worse arm of a
comparison look cheaper (SIP-0108 §7, question 2). So:

- the agent side keeps one :class:`UsageLedger` per task on the execution context, and
  ``_llm_call`` adds a generation for every response and a failed-call record for every call
  that raised before usage existed;
- the ledger rides the task result on every exit path — succeeded, failed, raised, timed out;
- the runtime side adds each reply to the run's :class:`RunUsageAccumulator` where every
  dispatch returns, and finalization persists the sum.

A reply that carries no usage — a runtime-side reply timeout, an agent older than this field —
is counted by task id, never read as zero.

Pure data and arithmetic; no I/O.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

#: SIP-0086 §12a change 1: the part of a task's usage its self-evaluation passes spent, carried
#: beside the task's totals under this key, and booked on the run under ``<task_type>`` plus
#: this suffix — so a pass is never mistaken for a correction round and its cost is measured.
SELF_EVAL_KEY = "self_eval_passes"
SELF_EVAL_SUFFIX = ":self_eval"


@dataclass(frozen=True)
class UsageTotals:
    """Calls and tokens over some set of LLM invocations.

    ``unreported_*`` counts successful calls whose provider reported no figure for that token
    kind — a count the reader needs beside the sum, because a sum over calls that reported
    nothing reads as a small number rather than an unknown one.
    """

    calls: int = 0
    failed_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    duration_ms: float = 0.0
    unreported_prompt: int = 0
    unreported_completion: int = 0
    unreported_reasoning: int = 0

    def __add__(self, other: UsageTotals) -> UsageTotals:
        return UsageTotals(
            **{
                f.name: getattr(self, f.name) + getattr(other, f.name)
                for f in dataclasses.fields(self)
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def without(self, part: UsageTotals) -> UsageTotals | None:
        """These totals less ``part``, or ``None`` when ``part`` is not contained in them — a
        subset that exceeds its whole is a malformed report, never a negative count."""
        rest = {
            f.name: getattr(self, f.name) - getattr(part, f.name) for f in dataclasses.fields(self)
        }
        if any(v < 0 for v in rest.values()):
            return None
        return UsageTotals(**rest)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> UsageTotals | None:
        """Read totals off the wire, or ``None`` when they are absent or malformed.

        Unknown keys are dropped (the TaskResult transport rule, SIP-0094 D8). A value that is
        not a non-negative number makes the whole record unreadable rather than silently zero.
        """
        if not isinstance(data, Mapping):
            return None
        values: dict[str, Any] = {}
        for f in dataclasses.fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
                return None
            values[f.name] = float(value) if f.name == "duration_ms" else int(value)
        return cls(**values)


class UsageLedger:
    """The agent side: one task's LLM invocations, added at ``_llm_call``."""

    def __init__(self) -> None:
        self._totals = UsageTotals()
        self._self_eval = UsageTotals()

    @property
    def totals(self) -> UsageTotals:
        return self._totals

    def record_generation(
        self, response: Any, duration_ms: float, *, self_eval_pass: bool = False
    ) -> None:
        """One call that returned. Token figures the provider did not report are counted as
        unreported, never as zero tokens."""
        prompt = getattr(response, "prompt_tokens", None)
        completion = getattr(response, "completion_tokens", None)
        reasoning = getattr(response, "reasoning_tokens", None)
        self._add(
            UsageTotals(
                calls=1,
                prompt_tokens=prompt or 0,
                completion_tokens=completion or 0,
                reasoning_tokens=reasoning or 0,
                duration_ms=max(duration_ms, 0.0),
                unreported_prompt=int(prompt is None),
                unreported_completion=int(completion is None),
                unreported_reasoning=int(reasoning is None),
            ),
            self_eval_pass,
        )

    def record_failed_call(self, duration_ms: float, *, self_eval_pass: bool = False) -> None:
        """One call that raised before usage existed — it cost wall-clock and may have cost
        tokens nobody reported, so it is counted rather than dropped."""
        self._add(
            UsageTotals(calls=1, failed_calls=1, duration_ms=max(duration_ms, 0.0)),
            self_eval_pass,
        )

    def _add(self, call: UsageTotals, self_eval_pass: bool) -> None:
        self._totals = self._totals + call
        if self_eval_pass:
            self._self_eval = self._self_eval + call

    def to_dict(self) -> dict[str, Any]:
        """The task's totals — every call, passes included, as readers before §12a read them —
        and, when a pass ran, what the passes spent under ``SELF_EVAL_KEY``."""
        out = self._totals.to_dict()
        if self._self_eval.calls:
            out[SELF_EVAL_KEY] = self._self_eval.to_dict()
        return out


@dataclass(frozen=True)
class RunUsage:
    """The runtime side's sum for one run: per task type, and the replies that carried none."""

    by_task_type: Mapping[str, UsageTotals]
    tasks_reported: int
    tasks_unreported: tuple[str, ...]

    @property
    def total(self) -> UsageTotals:
        total = UsageTotals()
        for totals in self.by_task_type.values():
            total = total + totals
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "by_task_type": {k: v.to_dict() for k, v in sorted(self.by_task_type.items())},
            "total": self.total.to_dict(),
            "tasks_reported": self.tasks_reported,
            "tasks_unreported": list(self.tasks_unreported),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunUsage:
        by_type: dict[str, UsageTotals] = {}
        for task_type, raw in (data.get("by_task_type") or {}).items():
            totals = UsageTotals.from_dict(raw)
            if totals is not None:
                by_type[str(task_type)] = totals
        return cls(
            by_task_type=by_type,
            tasks_reported=int(data.get("tasks_reported") or 0),
            tasks_unreported=tuple(str(t) for t in data.get("tasks_unreported") or ()),
        )


class RunUsageAccumulator:
    """The runtime side: every reply of one run, added where the dispatch returns."""

    def __init__(self) -> None:
        self._by_type: dict[str, UsageTotals] = {}
        self._reported = 0
        self._unreported: list[str] = []

    def record(self, task_type: str, task_id: str, usage: Mapping[str, Any] | None) -> None:
        totals = UsageTotals.from_dict(usage)
        if totals is None:
            self._unreported.append(task_id)
            return
        self._reported += 1
        # SIP-0086 §12a: the passes under their own key and the rest under the task type, so
        # the run's total is unchanged and a pass is never read as part of the first attempt.
        passes = UsageTotals.from_dict(usage.get(SELF_EVAL_KEY)) if usage else None
        rest = totals.without(passes) if passes is not None else None
        if passes is not None and rest is not None:
            self._book(task_type, rest)
            self._book(f"{task_type}{SELF_EVAL_SUFFIX}", passes)
        else:
            self._book(task_type, totals)

    def _book(self, key: str, totals: UsageTotals) -> None:
        self._by_type[key] = self._by_type.get(key, UsageTotals()) + totals

    def summary(self) -> RunUsage:
        return RunUsage(
            by_task_type=dict(self._by_type),
            tasks_reported=self._reported,
            tasks_unreported=tuple(self._unreported),
        )
