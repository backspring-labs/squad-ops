"""Unit tests for SIP-0090 Phase 1 EmbodimentStatePort surface + vocabulary (slice 3).

Each test answers: what bug would it catch?

Bug classes guarded:
- the state port silently growing an action/intent method (`attach`, `send`,
  `execute_*`, `decide_*`) — the §6 authority-boundary erosion the naming split
  exists to prevent;
- the `budget_exhausted` reason code getting re-hardcoded in `budgets.py` instead
  of single-sourced from `reasons.py` (the constant-duplication drift).
"""

from __future__ import annotations

from squadops.ports.runtime.embodiment import EmbodimentStatePort
from squadops.runtime import budgets, reasons

# The intended record/lifecycle surface (plan §4.3). Adding to this set must be a
# conscious edit here — that is the review gate against scope creep on the port.
_EXPECTED_SURFACE = {
    "create_embodiment",
    "get_embodiment",
    "get_active_embodiment",
    "list_for_agent",
    "transition_state",
    "update_health",
    "update_location",
}

# Verbs that would make this a mini action-surface / brain instead of a record store.
_ACTION_VERBS = ("execute", "send", "listen", "decide", "intent", "attach", "detach", "act_")


def test_state_port_surface_is_record_and_lifecycle_only():
    """Authority boundary (§6 / §14.3): the state port persists records + lifecycle
    state — it must not expose an action or intent-deciding method (that is the
    Phase-2 EmbodimentSurfacePort's job)."""
    assert EmbodimentStatePort.__abstractmethods__ == frozenset(_EXPECTED_SURFACE)


def test_state_port_has_no_action_or_intent_method():
    for name in EmbodimentStatePort.__abstractmethods__:
        assert not any(verb in name for verb in _ACTION_VERBS), (
            f"`{name}` reads like an action/intent verb — it belongs on the "
            f"Phase-2 EmbodimentSurfacePort, not the record store"
        )


def test_budget_exhausted_reason_is_single_sourced_from_reasons():
    """No constant duplication: budgets re-exports the canonical reason, it does not
    redefine the literal (a re-hardcode would drift the two apart)."""
    assert budgets.BUDGET_EXHAUSTED_REASON is reasons.BUDGET_EXHAUSTED
    assert reasons.BUDGET_EXHAUSTED == "budget_exhausted"
