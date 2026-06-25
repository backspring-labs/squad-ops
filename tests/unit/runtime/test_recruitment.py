"""Unit tests for SIP-0089 §2.5 — ``reserve_buffer_decision`` (pure guard).

Bug classes guarded:
- a hard duty in its pre-duty reserve buffer NOT rejecting recruitment (the core
  §11.4 guarantee: an agent about to start duty gets pulled into a cycle anyway);
- a hard duty *active* window not rejecting (agent already serving duty recruited);
- over-rejecting on windows that should be permissive — before the reserve buffer
  opens, the trailing reserve-after buffer, soft duties, and non-duty assignments;
- rejecting on an assignment held by an agent the run does NOT recruit;
- non-deterministic blocking-agent selection when several windows conflict;
- the wrong reason code on rejection.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.runtime import reasons
from squadops.runtime.models import Assignment, DutyWindow
from squadops.runtime.recruitment import reserve_buffer_decision

pytestmark = [pytest.mark.domain_runtime]

NOW = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)


def _assignment(
    *,
    agent_id: str = "neo",
    assignment_type: str = "duty",
    strictness: str = "hard",
    start: datetime,
    end: datetime,
    reserve_before: timedelta = timedelta(minutes=15),
    reserve_after: timedelta = timedelta(minutes=10),
) -> Assignment:
    return Assignment(
        assignment_id=f"a-{agent_id}-{start.hour:02d}{start.minute:02d}",
        agent_id=agent_id,
        assignment_type=assignment_type,  # type: ignore[arg-type]
        assigned_role="support",
        priority=10,
        strictness=strictness,  # type: ignore[arg-type]
        active_window=DutyWindow(start=start, end=end, timezone="UTC"),
        reserve_before_window=reserve_before,
        reserve_after_window=reserve_after,
        recall_policy="graceful",
        graceful_window=timedelta(minutes=5),
        missed_window_policy="skip",
        allowed_off_window_modes=("ambient", "cycle"),
    )


def test_hard_duty_in_reserve_before_rejects():
    """Window opens in 5 min, 15-min reserve → in_reserve_before → defer."""
    a = _assignment(start=NOW + timedelta(minutes=5), end=NOW + timedelta(hours=1))

    decision = reserve_buffer_decision([a], {"neo"}, NOW)

    assert decision.allowed is False
    assert decision.blocking_agent_id == "neo"
    assert decision.reason == reasons.UPCOMING_HARD_DUTY_WINDOW


def test_hard_duty_active_rejects():
    a = _assignment(start=NOW - timedelta(minutes=30), end=NOW + timedelta(minutes=30))

    decision = reserve_buffer_decision([a], {"neo"}, NOW)

    assert decision.allowed is False
    assert decision.blocking_agent_id == "neo"


def test_before_reserve_buffer_allows():
    """Window is 1 h out; the 15-min reserve hasn't opened yet → allow."""
    a = _assignment(start=NOW + timedelta(hours=1), end=NOW + timedelta(hours=2))

    decision = reserve_buffer_decision([a], {"neo"}, NOW)

    assert decision.allowed is True
    assert decision.blocking_agent_id is None
    assert decision.reason is None


def test_trailing_reserve_after_does_not_block():
    """Window ended 5 min ago, inside the 10-min trailing buffer → duty is
    winding down, not starting → recruitment allowed."""
    a = _assignment(start=NOW - timedelta(hours=2), end=NOW - timedelta(minutes=5))

    decision = reserve_buffer_decision([a], {"neo"}, NOW)

    assert decision.allowed is True


def test_soft_duty_active_does_not_block():
    """Soft windows yield to the scheduler's recall (§2.4); they do not gate
    recruitment in v1.1 even while active."""
    a = _assignment(
        strictness="soft",
        start=NOW - timedelta(minutes=30),
        end=NOW + timedelta(minutes=30),
    )

    decision = reserve_buffer_decision([a], {"neo"}, NOW)

    assert decision.allowed is True


def test_non_duty_assignment_does_not_block():
    """Only `duty` assignments claim the agent; a hard, active cycle_eligibility
    row must not defer recruitment."""
    a = _assignment(
        assignment_type="cycle_eligibility",
        start=NOW - timedelta(minutes=30),
        end=NOW + timedelta(minutes=30),
    )

    decision = reserve_buffer_decision([a], {"neo"}, NOW)

    assert decision.allowed is True


def test_assignment_for_non_participating_agent_does_not_block():
    """A blocking hard duty held by an agent the run never recruits is ignored."""
    a = _assignment(
        agent_id="bob",
        start=NOW - timedelta(minutes=30),
        end=NOW + timedelta(minutes=30),
    )

    decision = reserve_buffer_decision([a], {"neo", "max"}, NOW)

    assert decision.allowed is True


def test_empty_assignments_allows():
    assert reserve_buffer_decision([], {"neo"}, NOW).allowed is True


def test_reports_earliest_starting_blocking_assignment():
    """Two participating agents both conflict; the earliest-starting window is
    reported deterministically (so the deferral reason is stable across runs)."""
    later = _assignment(
        agent_id="max",
        start=NOW - timedelta(minutes=10),
        end=NOW + timedelta(hours=1),
    )
    earlier = _assignment(
        agent_id="neo",
        start=NOW - timedelta(minutes=45),
        end=NOW + timedelta(hours=1),
    )

    decision = reserve_buffer_decision([later, earlier], {"neo", "max"}, NOW)

    assert decision.allowed is False
    assert decision.blocking_agent_id == "neo"
