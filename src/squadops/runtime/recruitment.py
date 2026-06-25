"""
Cycle recruitment guard — SIP-0089 §2.5 (reserve-buffer protection).

Pure policy. Given the active duty assignments and the agents a cycle run is
about to recruit, decide whether recruitment may proceed or must be deferred
because a participating agent is committed to — or about to start — a hard duty
window (§11.4).

This is the runtime-domain *decision*. Enforcement (pausing the run, emitting
the deferral event) lives in the cycle executor (``adapters/cycles``). The
module depends only on ``runtime.models`` and ``runtime.reasons`` — never on
``adapters.*`` (D26) — so the executor (an adapter) imports *down* into the
domain, never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from squadops.runtime import reasons
from squadops.runtime.models import window_state

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from squadops.runtime.models import Assignment


@dataclass(frozen=True)
class RecruitmentDecision:
    """Outcome of the reserve-buffer guard.

    ``allowed=True`` → the run may dispatch. ``allowed=False`` → defer (pause):
    a participating agent holds a hard duty assignment in its pre-duty reserve
    buffer or active window. ``blocking_agent_id`` / ``reason`` are populated
    only when ``allowed=False``.
    """

    allowed: bool
    blocking_agent_id: str | None = None
    reason: str | None = None


def reserve_buffer_decision(
    assignments: Iterable[Assignment],
    participating_agent_ids: set[str],
    now: datetime,
) -> RecruitmentDecision:
    """Reject cycle recruitment when a participating agent is reserved for duty.

    Rejects iff some ``assignment`` is, at ``now``:

      * held by a participating agent (``agent_id in participating_agent_ids``),
      * a ``duty`` assignment with ``hard`` strictness, and
      * ``in_reserve_before`` or ``active`` per :func:`window_state` (§11.4).

    Soft duties do not gate recruitment in v1.1: a soft window yields to the
    scheduler's recall when it opens (§2.4), so starting cycle work alongside it
    is safe. The trailing ``in_reserve_after`` buffer also does not block — duty
    is winding down, not starting. The earliest-starting blocking assignment is
    reported (deterministic; ties broken by ``assignment_id``).

    Pure and time-injected (``now``) so the executor stays unit-testable without
    a clock.
    """
    blocking = sorted(
        (
            a
            for a in assignments
            if a.assignment_type == "duty"
            and a.strictness == "hard"
            and a.agent_id in participating_agent_ids
            and window_state(a, now) in ("in_reserve_before", "active")
        ),
        key=lambda a: (a.active_window.start, a.assignment_id),
    )
    if blocking:
        first = blocking[0]
        return RecruitmentDecision(
            allowed=False,
            blocking_agent_id=first.agent_id,
            reason=reasons.UPCOMING_HARD_DUTY_WINDOW,
        )
    return RecruitmentDecision(allowed=True)
