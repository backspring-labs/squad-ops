"""
Resource budget primitives for SIP-0090 (Agent Embodiment Substrate), Phase 1 §7.

Budgets attach to the **agent** (§7.1), not the embodiment, so cross-embodiment
usage sums. Phase 1 models decrement/acquire, release, exhaustion detection, and
the enforcement decision — **not** reset/replenishment (plan §4.2, explicitly
deferred so scheduling policy stays out of the substrate).

Two shapes (SIP §7.1 splits three cumulative counters from one "simultaneously-
open" gauge):

- **Consumable** (``{limit, consumed}``) — attention / compute / action. Remaining
  is derived; storing the limit (not remaining-only) keeps a future reset and
  observability possible without rework.
- **Capacity** (``{allowance, in_use}``) — concurrency. A gauge with symmetric
  ``acquire`` / ``release``; ``release`` is first-class so "acquire without release"
  is a visible bug, not a silent leak.

Exhaustion is never silent (§7.2): :func:`budget_decision` always returns one of
five :data:`ExhaustionOutcome`\\ s plus the ``budget_exhausted`` reason when a
request would exceed a cap. Pure (mirrors ``recruitment.reserve_buffer_decision``)
— no I/O, no adapters (D26).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from squadops.runtime.reasons import BUDGET_EXHAUSTED

BudgetDimension = Literal["attention", "compute", "action", "concurrency"]
CONSUMABLE_DIMENSIONS: frozenset[BudgetDimension] = frozenset({"attention", "compute", "action"})

ExhaustionOutcome = Literal[
    "reject_new_activity",
    "pause_current_activity",
    "detach_embodiment",
    "transition_to_ambient",
    "require_operator_override",
]

# `budget_exhausted` is the single canonical reason code — sourced from
# `runtime.reasons` (not redefined here) so there is one source of truth.
BUDGET_EXHAUSTED_REASON = BUDGET_EXHAUSTED

# Default enforcement policy: which outcome each dimension forces on exhaustion
# (§7.2). Conservative by design — the safe default for an over-budget agent is to
# stop taking on new work, not to detach or force an operator override. Overridable
# per call so a specific caller can escalate.
_DEFAULT_EXHAUSTION_POLICY: Mapping[BudgetDimension, ExhaustionOutcome] = {
    "attention": "reject_new_activity",
    "compute": "reject_new_activity",
    "action": "reject_new_activity",
    "concurrency": "reject_new_activity",
}


@dataclass(frozen=True)
class ConsumableBudget:
    """A cumulative budget: ``{limit, consumed}``. Exhausted when ``consumed >= limit``."""

    limit: int
    consumed: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.consumed)

    @property
    def is_exhausted(self) -> bool:
        return self.consumed >= self.limit

    def spend(self, amount: int) -> ConsumableBudget:
        """Return a new budget with ``amount`` consumed (pure; never mutates)."""
        if amount < 0:
            raise ValueError("spend amount must be non-negative")
        return ConsumableBudget(limit=self.limit, consumed=self.consumed + amount)


@dataclass(frozen=True)
class CapacityBudget:
    """A capacity gauge: ``{allowance, in_use}``. Exhausted when ``in_use >= allowance``.

    ``acquire`` / ``release`` are symmetric. ``release`` below zero is a caller bug
    (acquire/release imbalance) surfaced as ``ValueError``, never silently floored —
    a leaked slot must be observable.
    """

    allowance: int
    in_use: int = 0

    @property
    def available(self) -> int:
        return max(0, self.allowance - self.in_use)

    @property
    def is_exhausted(self) -> bool:
        return self.in_use >= self.allowance

    def acquire(self) -> CapacityBudget:
        return CapacityBudget(allowance=self.allowance, in_use=self.in_use + 1)

    def release(self) -> CapacityBudget:
        if self.in_use <= 0:
            raise ValueError("release without a matching acquire (concurrency underflow)")
        return CapacityBudget(allowance=self.allowance, in_use=self.in_use - 1)


@dataclass(frozen=True)
class AgentBudget:
    """The four §7.1 budget dimensions, attached to the agent."""

    attention: ConsumableBudget
    compute: ConsumableBudget
    action: ConsumableBudget
    concurrency: CapacityBudget


@dataclass(frozen=True)
class BudgetDecision:
    """Verdict for a requested spend/acquire (§7.2). Pure — no event emission here.

    ``allowed`` — whether the request may proceed. ``exhausted`` — whether it would
    exceed the cap. On exhaustion ``outcome`` is one of the five forced
    :data:`ExhaustionOutcome`\\ s and ``reason_code`` is ``budget_exhausted``; both
    are ``None`` otherwise. Silent degradation is unrepresentable: ``exhausted`` is
    true iff ``outcome`` is set (see :meth:`__post_init__`).
    """

    dimension: BudgetDimension
    allowed: bool
    exhausted: bool
    outcome: ExhaustionOutcome | None = None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        # The type-level guard that exhaustion is never silent: an exhausted verdict
        # must carry a forced outcome + reason, and a non-exhausted one must not.
        if self.exhausted != (self.outcome is not None):
            raise ValueError(
                "an exhausted decision must carry an ExhaustionOutcome, and vice versa"
            )
        if self.exhausted and self.reason_code != BUDGET_EXHAUSTED_REASON:
            raise ValueError("an exhausted decision must carry the budget_exhausted reason code")


def _dimension_budget(
    budget: AgentBudget, dimension: BudgetDimension
) -> ConsumableBudget | CapacityBudget:
    return {
        "attention": budget.attention,
        "compute": budget.compute,
        "action": budget.action,
        "concurrency": budget.concurrency,
    }[dimension]


def budget_decision(
    budget: AgentBudget,
    dimension: BudgetDimension,
    amount: int = 1,
    policy: Mapping[BudgetDimension, ExhaustionOutcome] | None = None,
) -> BudgetDecision:
    """Decide whether a spend (consumable) or acquire (capacity) may proceed (§7.2).

    A hard pre-spend gate: the request is **rejected** when it would push the
    dimension past its cap — ``consumed + amount > limit`` for a consumable,
    ``in_use + amount > allowance`` for concurrency (``amount`` defaults to one
    slot). Rejection is never silent: it carries a forced :data:`ExhaustionOutcome`
    (from ``policy``, else the conservative default) and the ``budget_exhausted``
    reason. Pure — it does not mutate ``budget``; the caller applies the
    spend/acquire only when ``allowed``.
    """
    if amount < 0:
        raise ValueError("amount must be non-negative")
    dim = _dimension_budget(budget, dimension)
    if isinstance(dim, CapacityBudget):
        would_exhaust = dim.in_use + amount > dim.allowance
    else:
        would_exhaust = dim.consumed + amount > dim.limit

    if would_exhaust:
        outcome = (policy or _DEFAULT_EXHAUSTION_POLICY)[dimension]
        return BudgetDecision(
            dimension=dimension,
            allowed=False,
            exhausted=True,
            outcome=outcome,
            reason_code=BUDGET_EXHAUSTED_REASON,
        )
    return BudgetDecision(dimension=dimension, allowed=True, exhausted=False)
