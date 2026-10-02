"""The one place a cycle ends — #1507 step 3 (docs/plans/1-9-0-completion-boundary-map.md).

Every way ``execute_cycle`` ends — the single-workload fast path, a failed or cancelled run, the
sequence's last workload, and each way the inter-workload gate stops it — reaches ``end``, which
produces one read-only ``CycleEnd``. It is the seam 2.0's continuation request enters (the Campaign
SIP's Appendix A); in 1.9 nothing enters there.

It reads the last run's terminal decision as its loop summary recorded it, and writes two things:
the cycle's failure records (SIP-0109 §14, #1710), from the one producer, before anything reads
an attribution; and the ending itself (§12a, #1803), before the campaign is told, so a telling
that fails can be repeated from it. It borrows the registry and the vault late (defended-bespoke-decisions §38).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from adapters.cycles.cycle_evidence import record_cycle_failures
from squadops.cycles.cycle_end import CycleEnd, CycleStopReason, RecordedEnd

logger = logging.getLogger(__name__)


class CycleCompletion:
    """Ends a cycle: one ``CycleEnd`` per ending."""

    BORROWED = ("_cycle_registry", "_artifact_vault", "_campaign_progress")

    def __init__(self, *, executor: Callable[[], Any]) -> None:
        self._executor = executor

    def __getattr__(self, name: str) -> Any:
        if name in CycleCompletion.BORROWED:
            return getattr(self._executor(), name)
        raise AttributeError(name)

    async def end(self, cycle_id: str, last_run: Any, stopped_because: CycleStopReason) -> CycleEnd:
        summary = await self._cycle_registry.get_run_loop_summary(last_run.run_id)
        await self._record_failures(cycle_id, last_run.run_id)
        await self._record_end(cycle_id, last_run.run_id, stopped_because)
        await self._hear_campaign(cycle_id, last_run, stopped_because)
        return CycleEnd(
            cycle_id=cycle_id,
            last_run_id=last_run.run_id,
            last_run_status=last_run.status,
            last_run_terminal=getattr(summary, "terminal", None),
            stopped_because=stopped_because,
        )

    async def _hear_campaign(
        self, cycle_id: str, last_run: Any, stopped_because: CycleStopReason
    ) -> None:
        """SIP-0109 §10, Appendix A: a campaign's cycle ends here, and its campaign decides what
        follows. After the failure records, which the decision's assessment reads (§14). A
        failure is logged loudly and does not stop the ending: the campaign is then left where
        it was, and the startup re-entry hears it again from the recorded ending (§12a,
        ``CampaignProgress.rehear_ended``)."""
        cycle = await self._cycle_registry.get_cycle(cycle_id)
        if not cycle.campaign_id:
            return
        if self._campaign_progress is None:
            logger.error(
                "campaign_cycle_ended_unheard",
                extra={"cycle_id": cycle_id, "campaign_id": cycle.campaign_id},
            )
            return
        try:
            await self._campaign_progress.cycle_ended(cycle, last_run, stopped_because)
        except Exception:
            logger.exception(
                "campaign_progress_failed",
                extra={"cycle_id": cycle_id, "campaign_id": cycle.campaign_id},
            )

    async def _record_end(
        self, cycle_id: str, last_run_id: str, stopped_because: CycleStopReason
    ) -> None:
        """Record how the cycle ended before its campaign is told (SIP-0109 §12a, #1803), so a
        campaign the telling did not move is re-heard at startup from this record. A failed write
        is logged loudly and does not stop the ending: that ending then cannot be re-heard."""
        try:
            await self._cycle_registry.record_cycle_end(
                RecordedEnd(cycle_id, last_run_id, stopped_because)
            )
        except Exception:
            logger.exception(
                "cycle_end_not_recorded",
                extra={"cycle_id": cycle_id, "last_run_id": last_run_id},
            )

    async def _record_failures(self, cycle_id: str, last_run_id: str) -> None:
        """Persist the ending's failure records. A failed write is logged loudly and does not
        stop the ending: the cycle then has no record set, and its attribution is read from the
        producer, as for a cycle that ended before the records existed."""
        try:
            await record_cycle_failures(
                self._cycle_registry, self._artifact_vault, cycle_id, last_run_id
            )
        except Exception:
            logger.exception(
                "failure_records_not_written",
                extra={"cycle_id": cycle_id, "last_run_id": last_run_id},
            )
