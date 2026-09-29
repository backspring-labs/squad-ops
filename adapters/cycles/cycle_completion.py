"""The one place a cycle ends — #1507 step 3 (docs/plans/1-9-0-completion-boundary-map.md).

Every way ``execute_cycle`` ends — the single-workload fast path, a failed or cancelled run, the
sequence's last workload, and each way the inter-workload gate stops it — reaches ``end``, which
produces one read-only ``CycleEnd``. It is the seam 2.0's continuation request enters (the Campaign
SIP's Appendix A); in 1.9 nothing enters there.

It reads, and changes nothing: the last run's terminal decision as its loop summary recorded it.
It borrows the registry late (defended-bespoke-decisions §38).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from squadops.cycles.cycle_end import CycleEnd, CycleStopReason


class CycleCompletion:
    """Ends a cycle: one ``CycleEnd`` per ending."""

    BORROWED = ("_cycle_registry",)

    def __init__(self, *, executor: Callable[[], Any]) -> None:
        self._executor = executor

    def __getattr__(self, name: str) -> Any:
        if name in CycleCompletion.BORROWED:
            return getattr(self._executor(), name)
        raise AttributeError(name)

    async def end(self, cycle_id: str, last_run: Any, stopped_because: CycleStopReason) -> CycleEnd:
        summary = await self._cycle_registry.get_run_loop_summary(last_run.run_id)
        return CycleEnd(
            cycle_id=cycle_id,
            last_run_id=last_run.run_id,
            last_run_status=last_run.status,
            last_run_terminal=getattr(summary, "terminal", None),
            stopped_because=stopped_because,
        )
