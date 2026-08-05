"""Inert-check detection — chronic not-executed streaks across cycles (SIP-0096 §9, #684).

A check with stable identity that has reported not-executed for N consecutive
cycles (default 3) in the same project/profile is **inert**: a permanently
skipping check is indistinguishable from no check. Detection is derived on read
from the persisted per-run ``RunVerificationSummary`` rows — no counter table,
no migration; the "counter" is a streak computed by walking the project's
recent cycles newest→oldest, so reset-on-real-execution falls out of the walk.

Identity domain (§6.3): only ``check_registry``'s stable framework vocabulary
participates — plan-authored typed checks have per-cycle identity and pulse
suites are a separate axis whose results do not flow into run summaries today.
Because these ids are the canonical strings producers emit, a rename is a
vocabulary change, not a per-run alias — the §9 rename-survival rule holds by
construction.

Streak semantics (§9): a cycle where the check executed the real subject
resets the streak; a cycle where it reported not-executed increments it; a
cycle where it is absent pauses it — the counter "resets only when the check
evaluates the real subject — not when the check disappears, is renamed, or is
reclassified optional."

Pure functions over summaries — ``cycle_outcome.resolve_cycle_outcome`` owns
the registry reads, series scoping, and failure containment.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from squadops.cycles.check_registry import framework_check_ids
from squadops.cycles.verification_integrity import (
    RunVerificationSummary,
    aggregate_cycle_outcome,
)

#: SIP-0096 §9 default N. Config-addressable via
#: ``SQUADOPS__CYCLES__INERT_CYCLE_THRESHOLD`` (a drift test pins the schema
#: default to this constant).
INERT_CYCLE_THRESHOLD_DEFAULT = 3

#: How many prior same-project/profile cycles the walk may consult. A streak
#: not resolvable within this window is NOT inert — insufficient evidence is
#: never flagged. Bounds the read cost of the derive-on-read detection.
INERT_LOOKBACK_CYCLES = 10


def cycle_check_state(
    summaries: Sequence[RunVerificationSummary],
) -> tuple[frozenset[str], frozenset[str]]:
    """One cycle's reconciled per-check state: ``(executed_ids, not_executed_ids)``.

    Uses the same reconciliation the roll-up uses (``aggregate_cycle_outcome``:
    executed evidence in any run supersedes the check's not-executed rows), so
    detection and disclosure can never disagree about what a cycle proved. A
    cycle with no summaries yields two empty sets — every check is *absent*
    there, which pauses streaks without resetting them.
    """
    outcome = aggregate_cycle_outcome(summaries)
    executed = frozenset(outcome.verified) | frozenset(outcome.failed)
    reported = frozenset(u.check_id for u in outcome.unverified)
    return executed, reported - executed


def detect_inert_checks(
    cycle_states: Sequence[tuple[Collection[str], Collection[str]]],
    *,
    stable_ids: Collection[str] | None = None,
    threshold: int = INERT_CYCLE_THRESHOLD_DEFAULT,
) -> tuple[str, ...]:
    """Stable checks whose not-executed streak has reached ``threshold`` (§9).

    ``cycle_states`` is newest-first — the perspective cycle first, then its
    prior same-project/profile cycles — each a ``(executed_ids,
    not_executed_ids)`` pair (see ``cycle_check_state``). The perspective cycle
    participates like any other: a check it executed is reset (not inert); a
    check absent now but chronic before stays inert until a real execution.

    Only ``stable_ids`` (default: the ``check_registry`` framework vocabulary)
    are tracked; everything else is invisible to the walk.
    """
    if threshold < 1:
        raise ValueError(f"threshold must be >= 1, got {threshold}")
    stable = frozenset(stable_ids if stable_ids is not None else framework_check_ids())
    inert: set[str] = set()
    resolved: set[str] = set()  # reset by execution, or already flagged inert
    streak: dict[str, int] = {}
    for executed, not_executed in cycle_states:
        executed_stable = stable.intersection(executed)
        resolved.update(executed_stable)
        for cid in stable.intersection(not_executed) - executed_stable - resolved:
            streak[cid] = streak.get(cid, 0) + 1
            if streak[cid] >= threshold:
                inert.add(cid)
                resolved.add(cid)
    return tuple(sorted(inert))
