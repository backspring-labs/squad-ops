"""Unit tests for SIP-0089 §4.6 — AmbientPolicy irreversibility gate.

Bug classes guarded:
- a reversible action being gated (it must always pass, without even touching the
  ports);
- a duty/cycle agent being blocked from irreversible work (only ambient is gated);
- the gate permitting an ambient irreversible action when only ONE of the
  required {lease, activity} is held — the canonical invariant (§10.4) requires
  BOTH, so either missing must refuse (this distinguishes the spec-faithful rule
  from §4.6's looser "neither" phrasing);
- failing OPEN for an agent with no runtime-state row (must fail closed).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from squadops.runtime import reasons
from squadops.runtime.models import AgentRuntimeState
from squadops.runtime.policy import AmbientActionForbidden, AmbientPolicy

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 6, 28, 1, 0, tzinfo=UTC)


def _state(mode: str) -> AgentRuntimeState:
    return AgentRuntimeState("max", mode, "online", "", None, "high", NOW, None)


def _policy(*, mode: str | None, has_lease: bool, has_activity: bool) -> AmbientPolicy:
    state = AsyncMock()
    state.get_state.return_value = _state(mode) if mode is not None else None
    focus_lease = AsyncMock()
    focus_lease.get_current_lease.return_value = object() if has_lease else None
    activity = AsyncMock()
    activity.get_current_activity.return_value = object() if has_activity else None
    return AmbientPolicy(state, focus_lease, activity)


async def test_reversible_action_is_always_permitted_without_touching_ports():
    """Bug class: a reversible action must never be gated — and the gate should
    short-circuit before any port lookup."""
    policy = _policy(mode="ambient", has_lease=False, has_activity=False)

    await policy.assert_action_permitted("max", "observe", irreversible=False)

    policy._state.get_state.assert_not_awaited()  # short-circuited


@pytest.mark.parametrize("mode", ["duty", "cycle"])
async def test_non_ambient_agent_permitted_for_irreversible_action(mode):
    """Bug class: only ambient is gated. A duty/cycle agent is already doing
    claimed work and must be permitted even with no lease/activity visible here."""
    policy = _policy(mode=mode, has_lease=False, has_activity=False)

    await policy.assert_action_permitted("max", "deploy", irreversible=True)  # no raise


async def test_ambient_with_both_lease_and_activity_is_permitted():
    """Bug class: the legitimate path — ambient holding BOTH a lease and an
    activity may act irreversibly (§10.4)."""
    policy = _policy(mode="ambient", has_lease=True, has_activity=True)

    await policy.assert_action_permitted("max", "deploy", irreversible=True)  # no raise


@pytest.mark.parametrize(
    ("has_lease", "has_activity"),
    [(True, False), (False, True), (False, False)],
)
async def test_ambient_missing_either_requirement_is_forbidden(has_lease, has_activity):
    """Bug class (the load-bearing one): §10.4 requires BOTH a lease and an
    activity. Holding only one (or neither) must refuse — a gate that allowed the
    single-held case would violate the invariant."""
    policy = _policy(mode="ambient", has_lease=has_lease, has_activity=has_activity)

    with pytest.raises(AmbientActionForbidden) as exc:
        await policy.assert_action_permitted("max", "deploy", irreversible=True)

    assert exc.value.reason_code == reasons.AMBIENT_IRREVERSIBLE_ACTION_FORBIDDEN
    assert exc.value.agent_id == "max" and exc.value.action_kind == "deploy"


async def test_missing_state_row_fails_closed():
    """Bug class: an agent that never heartbeated (no state row) must be treated
    as ambient and refused, not permitted by default — fail closed, not open."""
    policy = _policy(mode=None, has_lease=False, has_activity=False)

    with pytest.raises(AmbientActionForbidden):
        await policy.assert_action_permitted("ghost", "deploy", irreversible=True)
