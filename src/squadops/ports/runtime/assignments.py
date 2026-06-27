"""
AssignmentPort — abstract interface for duty Assignment persistence (SIP-0089 §10.2).

Phase 2 surface (§2.3). The query methods are intentionally specific so the
scheduler (§2.4) and the cycle reserve-buffer guard (§2.5) push time/agent
filtering into SQL rather than fetching all assignments and filtering in memory.

Window semantics referenced below match `runtime.models.window_state`:
"active or in reserve" means `now ∈ [window_start - reserve_before_window,
window_end + reserve_after_window)`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.runtime.models import Assignment


class AssignmentPort(ABC):
    """Port for `Assignment` persistence and the scheduler/guard read queries."""

    @abstractmethod
    async def get_assignment(self, assignment_id: str) -> Assignment | None:
        """Return the assignment by id, or `None` if no row exists."""

    @abstractmethod
    async def list_assignments_for_agent(self, agent_id: str) -> list[Assignment]:
        """Return all assignments held by `agent_id`, ordered by window start.

        Returns active and inactive rows; callers filter on `active` as needed.
        """

    @abstractmethod
    async def list_active_assignments(self, now: datetime) -> list[Assignment]:
        """Return active assignments whose window is active or in reserve at `now`.

        i.e. `now ∈ [window_start - reserve_before_window, window_end +
        reserve_after_window)` and `active = TRUE`. This is the broad
        "currently relevant" set; the §2.5 guard refines it (e.g. to hard duties
        in `in_reserve_before`/`active`) via `window_state`.
        """

    @abstractmethod
    async def list_claimable_windows(self, now: datetime) -> list[Assignment]:
        """Return active duty assignments whose window is currently claimable.

        Claimable = `assignment_type = 'duty'`, `active = TRUE`, and `now ∈
        [window_start - reserve_before_window, window_end)` — from when the
        pre-duty reserve buffer opens until the window closes. The scheduler
        (§2.4) decides per row whether a transition request is still needed.
        """

    @abstractmethod
    async def list_assignments_to_close(self, now: datetime) -> list[Assignment]:
        """Return duty assignments whose serving agent should return to ambient.

        A duty assignment where an agent is currently in `mode = 'duty'` bound to
        it (`current_assignment_ref`) and whose window has fully ended:
        `now >= window_end + reserve_after_window`. This is the close-sweep the
        scheduler (§2.4) uses for windows that leave the active set before a tick
        can observe `in_reserve_after` — notably hard duty with the default
        `reserve_after_window = 0`, where the active-set upper bound and the close
        instant coincide (#226). Disjoint from `list_active_assignments` at the
        `window_end + reserve_after_window` boundary.
        """

    @abstractmethod
    async def upsert_assignment(self, assignment: Assignment) -> Assignment:
        """Insert or update `assignment` by `assignment_id`; return it."""
