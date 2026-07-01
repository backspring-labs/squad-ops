"""Unit tests for SIP-0090 Phase 1 budget primitives (slice 1a, §7).

Each test answers: what bug would it catch?

Bug classes guarded:
- a concurrency slot leaked (acquire without release) going undetected (§7.1);
- silent budget degradation — an exhausted decision with no forced outcome (§7.2);
- the off-by-one at the cap boundary (spending *exactly* to the limit wrongly blocked
  or the next spend wrongly allowed);
- a policy override being ignored so every dimension collapses to the default outcome.
"""

from __future__ import annotations

import pytest

from squadops.runtime.budgets import (
    BUDGET_EXHAUSTED_REASON,
    AgentBudget,
    BudgetDecision,
    CapacityBudget,
    ConsumableBudget,
    budget_decision,
)


def _budget(*, attention=100, compute=100, action=100, concurrency=3, in_use=0):
    return AgentBudget(
        attention=ConsumableBudget(limit=attention),
        compute=ConsumableBudget(limit=compute),
        action=ConsumableBudget(limit=action),
        concurrency=CapacityBudget(allowance=concurrency, in_use=in_use),
    )


# ── ConsumableBudget ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("limit", "consumed", "remaining", "exhausted"),
    [
        (10, 3, 7, False),
        (10, 10, 0, True),  # at the cap
        (10, 12, 0, True),  # over the cap → remaining floors at 0
        (10, 0, 10, False),
    ],
)
def test_consumable_remaining_and_exhaustion(limit, consumed, remaining, exhausted):
    b = ConsumableBudget(limit=limit, consumed=consumed)
    assert b.remaining == remaining
    assert b.is_exhausted is exhausted


def test_consumable_spend_is_pure_and_accumulates():
    b = ConsumableBudget(limit=10, consumed=2)
    after = b.spend(5)
    assert (after.consumed, after.remaining) == (7, 3)
    assert b.consumed == 2  # original untouched (pure)


def test_consumable_spend_rejects_negative():
    with pytest.raises(ValueError, match="non-negative"):
        ConsumableBudget(limit=10).spend(-1)


# ── CapacityBudget ───────────────────────────────────────────────────────────


def test_capacity_available_and_exhaustion():
    b = CapacityBudget(allowance=3, in_use=1)
    assert (b.available, b.is_exhausted) == (2, False)
    full = CapacityBudget(allowance=3, in_use=3)
    assert (full.available, full.is_exhausted) == (0, True)


def test_capacity_acquire_then_release_round_trips():
    b = CapacityBudget(allowance=3, in_use=1)
    assert b.acquire().in_use == 2
    assert b.acquire().release().in_use == 1  # symmetric


def test_capacity_release_underflow_raises_not_floors():
    """A release with nothing acquired is an imbalance bug — it must surface, not
    silently floor at 0 (that would hide a leaked-slot accounting error)."""
    with pytest.raises(ValueError, match="underflow"):
        CapacityBudget(allowance=3, in_use=0).release()


# ── budget_decision (§7.2) ───────────────────────────────────────────────────


def test_consumable_with_room_is_allowed_and_not_exhausted():
    d = budget_decision(_budget(compute=100), "compute", amount=10)
    assert (d.allowed, d.exhausted) == (True, False)
    assert d.outcome is None and d.reason_code is None


def test_spend_exactly_to_the_cap_is_allowed_but_over_is_blocked():
    """Boundary: consumed+amount == limit is fine; the amount that crosses it blocks."""
    budget = _budget(action=10)
    assert budget_decision(budget, "action", amount=10).allowed is True  # exactly to cap
    over = budget_decision(budget, "action", amount=11)
    assert over.allowed is False and over.exhausted is True


def test_consumable_exhaustion_carries_default_outcome_and_reason():
    already = AgentBudget(
        attention=ConsumableBudget(limit=10, consumed=10),
        compute=ConsumableBudget(limit=100),
        action=ConsumableBudget(limit=100),
        concurrency=CapacityBudget(allowance=3),
    )
    d = budget_decision(already, "attention", amount=1)
    assert (d.allowed, d.exhausted) == (False, True)
    assert d.outcome == "reject_new_activity"
    assert d.reason_code == BUDGET_EXHAUSTED_REASON


def test_concurrency_free_slot_allowed_full_blocked():
    assert budget_decision(_budget(concurrency=3, in_use=2), "concurrency").allowed is True
    full = budget_decision(_budget(concurrency=3, in_use=3), "concurrency")
    assert (full.allowed, full.exhausted, full.outcome) == (False, True, "reject_new_activity")


def test_policy_override_selects_a_different_outcome():
    full = _budget(concurrency=1, in_use=1)
    d = budget_decision(full, "concurrency", policy={"concurrency": "detach_embodiment"})
    assert d.exhausted is True and d.outcome == "detach_embodiment"


def test_budget_decision_rejects_negative_amount():
    with pytest.raises(ValueError, match="non-negative"):
        budget_decision(_budget(), "compute", amount=-5)


# ── Non-silent-exhaustion invariant (§7.2) ───────────────────────────────────


def test_exhausted_decision_must_carry_outcome():
    """The type itself forbids a silent exhaustion (exhausted with no outcome)."""
    with pytest.raises(ValueError, match="ExhaustionOutcome"):
        BudgetDecision(dimension="compute", allowed=False, exhausted=True, outcome=None)


def test_non_exhausted_decision_must_not_carry_outcome():
    with pytest.raises(ValueError, match="ExhaustionOutcome"):
        BudgetDecision(
            dimension="compute",
            allowed=True,
            exhausted=False,
            outcome="reject_new_activity",
            reason_code=BUDGET_EXHAUSTED_REASON,
        )


def test_exhausted_decision_requires_the_budget_exhausted_reason():
    with pytest.raises(ValueError, match="budget_exhausted"):
        BudgetDecision(
            dimension="compute",
            allowed=False,
            exhausted=True,
            outcome="reject_new_activity",
            reason_code="something_else",
        )
