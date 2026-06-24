"""Unit tests for SIP-0089 Phase 2 §2.1 — Assignment / DutyWindow / window_state.

These exercise `window_state()`, the pure time classifier the scheduler (§2.4)
and the cycle reserve-buffer guard (§2.5) both depend on. The bug class they
guard against is off-by-one / boundary errors in the reserve-buffer geometry —
the kind that would let a cycle be recruited one second inside a hard duty's
reserve window, or mark a window `closed` while it is still `active`.

Each test answers: what bug would it catch?
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.runtime.models import Assignment, DutyWindow, window_state

pytestmark = [pytest.mark.domain_runtime]

# Window: 01:00–06:00 UTC, 15m pre-buffer (→ opens 00:45), 10m post-buffer (→ closes 06:10).
WIN_START = datetime(2026, 6, 24, 1, 0, tzinfo=UTC)
WIN_END = datetime(2026, 6, 24, 6, 0, tzinfo=UTC)


def _assignment(
    *,
    reserve_before: timedelta = timedelta(minutes=15),
    reserve_after: timedelta = timedelta(minutes=10),
    strictness: str = "hard",
) -> Assignment:
    return Assignment(
        assignment_id="a-1",
        assignment_type="duty",
        assigned_role="support",
        priority=10,
        strictness=strictness,  # type: ignore[arg-type]
        active_window=DutyWindow(start=WIN_START, end=WIN_END, timezone="UTC"),
        reserve_before_window=reserve_before,
        reserve_after_window=reserve_after,
        recall_policy="graceful",
        graceful_window=timedelta(minutes=5),
        missed_window_policy="require_operator_review",
        allowed_off_window_modes=("ambient", "cycle"),
    )


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 24, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (_at(0, 30), "before_window"),  # before the 00:45 reserve opens
        (_at(0, 45), "in_reserve_before"),  # reserve-start instant is inside the buffer
        (_at(0, 55), "in_reserve_before"),
        (_at(1, 0), "active"),  # window-start instant is active (inclusive)
        (_at(3, 0), "active"),
        (_at(6, 0), "in_reserve_after"),  # window-end instant is already past (exclusive)
        (_at(6, 5), "in_reserve_after"),
        (_at(6, 10), "closed"),  # reserve-after-end instant is closed (exclusive)
        (_at(7, 0), "closed"),
    ],
)
def test_window_state_time_geometry(now, expected):
    """Bug class: a boundary off-by-one would misclassify the reserve buffer — e.g.
    treating 00:45 as `before_window` would let a cycle in during a hard duty's
    reserve, the exact conflict §11.4 exists to prevent."""
    assert window_state(_assignment(), now) == expected


def test_window_state_default_never_returns_missed_after_close():
    """Bug class: the default call must be a pure time classifier. If `missed`
    leaked into the default path, a normally-completed window would be mislabeled
    long after the fact."""
    assert window_state(_assignment(), _at(7, 0)) == "closed"


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (_at(0, 55), "in_reserve_before"),  # not missed yet — window hasn't opened
        (_at(3, 0), "active"),  # still open: the agent can still enter, so not missed
        (_at(6, 0), "missed"),  # window just ended and was never entered
        (_at(7, 0), "missed"),  # missed supersedes closed when never entered
    ],
)
def test_window_state_missed_requires_window_ended_without_entry(now, expected):
    """Bug class: `missed` must not pre-empt `active` (an agent entering late is
    not a miss), and must override the post-window states once the window closes
    unentered — otherwise the scheduler can't tell a no-show from a clean finish."""
    assert window_state(_assignment(), now, entered_active=False) == expected


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (_at(0, 59), "before_window"),  # no pre-buffer → straight from before to active
        (_at(1, 0), "active"),
        (_at(5, 59), "active"),
        (_at(6, 0), "closed"),  # no post-buffer → no in_reserve_after state at all
    ],
)
def test_window_state_zero_buffers_collapse_reserve_states(now, expected):
    """Bug class (soft-duty default = 0m buffers, §11.4): with zero reserve, the
    `in_reserve_before`/`in_reserve_after` states must vanish rather than swallow
    a zero-width interval and momentarily report a reserve state."""
    a = _assignment(reserve_before=timedelta(0), reserve_after=timedelta(0), strictness="soft")
    assert window_state(a, now) == expected


def test_window_state_rejects_naive_now():
    """Bug class: comparing a naive `now` against tz-aware window bounds silently
    'works' in some Python versions and raises in others. We want fail-fast, not a
    timezone-blind classification, so a naive datetime must raise."""
    with pytest.raises(TypeError):
        window_state(_assignment(), datetime(2026, 6, 24, 3, 0))  # noqa: DTZ001 — intentional
