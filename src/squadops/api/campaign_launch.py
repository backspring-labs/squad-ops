"""A campaign's launches, from intent to a running cycle (SIP-0109 §12b).

The launcher turns each pending intent into exactly one cycle record. This service supplies
what it needs and does what follows it:
- **the cycle** is built by the cycle-create path itself (``prepare_cycle``), from the request
  the intent carries, preflighted as an operator's cycle is, and naming its campaign and kind;
- **its first run**: every drain reconciles each live campaign's launched intents, so a launched
  cycle without a run gets its first one, and a first run still queued that this process has not
  started is started. A crash between the mark and the run, or between the run and its start,
  is repaired by the next drain, and a cycle never gets a second first run.

Drains are serialized: two drains on one process would otherwise both see a launched cycle
without a run and start two. A drain runs after every control-log row that writes an intent, and
once at startup, so what a crash left undone is done then.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from squadops.api.cycle_schemas import CycleCreateRequest
from squadops.api.routes.cycles.cycles import CreationPorts, first_run, prepare_cycle
from squadops.campaigns.launcher import BoxVerdict, CampaignLauncher, unblocked
from squadops.campaigns.models import CampaignState, LaunchIntent, LaunchIntentState
from squadops.cycles.models import Cycle, Run, RunInitiator, RunStatus
from squadops.events.types import EventType

logger = logging.getLogger(__name__)

#: The actor on the launcher's own control-log rows.
LAUNCHER_ACTOR = "campaign-launcher"


class CampaignLaunchService:
    def __init__(
        self,
        *,
        campaigns,
        creation: CreationPorts,
        flow_executor,
        event_bus,
        box_verdict: BoxVerdict,
    ) -> None:
        self._campaigns = campaigns
        self._creation = creation
        self._executor = flow_executor
        self._event_bus = event_bus
        self._launcher = CampaignLauncher(
            campaigns,
            creation.cycle_registry,
            self._build_cycle,
            actor=LAUNCHER_ACTOR,
            box_verdict=box_verdict,
        )
        self._lock = asyncio.Lock()
        self._running: set[asyncio.Task] = set()
        #: First runs this process has started: a queued one not in it was never started.
        self._started: set[str] = set()

    async def _build_cycle(self, intent: LaunchIntent) -> Cycle:
        campaign = await self._campaigns.get_campaign(intent.campaign_id)
        prepared = await prepare_cycle(
            self._creation,
            campaign.project_id,
            CycleCreateRequest(**intent.cycle_request["body"]),
            created_by=LAUNCHER_ACTOR,
            initiated_by=RunInitiator.SYSTEM,
            campaign_id=campaign.campaign_id,
            kind=intent.cycle_kind.value,
        )
        return prepared.cycle

    async def drain(self) -> list[Run]:
        """Launch every pending intent, then start every launched cycle's first run that has
        not started. Returns the runs started. A launch that fails stays pending and is logged;
        the next drain repeats it."""
        async with self._lock:
            try:
                await self._launcher.drain()
            except Exception:
                logger.exception("campaign_launch_failed")
            started = []
            for cycle_id in await self.launched_cycles():
                run = await self._start_first_run(cycle_id)
                if run is not None:
                    started.append(run)
            return started

    async def retry_blocked(self) -> list:
        """§9.3 (#1802): each blocked campaign whose attempt is due reads the box again; one
        the box now allows returns to work, and its held intent is launched at once."""
        async with self._lock:
            rows = await self._launcher.retry_blocked(datetime.now(UTC))
        if unblocked(rows):
            await self.drain()
        return rows

    async def reattach(self) -> list[str]:
        """SIP-0109 §12a (#1922), at startup only: each live campaign's launched cycle that the
        process died inside is taken up where it stopped.

        - **A run left ``running``** resumes from its checkpoint, as ``runs resume`` does.
        - **A completed run with a gate after it, and no successor,** is re-entered at its gate:
          the gate is open again, and a decision already recorded on it is not asked again.
        - **A completed last run whose ending was never recorded** is re-entered at the cycle's
          end, so its completion is heard.
        - A cycle whose ending is recorded is left to the startup re-hearing; a failed,
          cancelled or paused run is the campaign's or the owner's to act on.

        Only at startup: a later drain would find successor runs this process is already
        executing. Returns the cycles taken up."""
        from squadops.cycles.models import RunStatus

        cycles = self._creation.cycle_registry
        taken_up = []
        for cycle_id in await self.launched_cycles():
            runs = [r for r in await cycles.list_runs(cycle_id) if r.status != RunStatus.CANCELLED]
            if not runs:
                continue
            latest = max(runs, key=lambda r: r.run_number)
            if latest.run_id in self._started or await cycles.get_cycle_end(cycle_id) is not None:
                continue
            if latest.status not in (RunStatus.RUNNING.value, RunStatus.COMPLETED.value):
                continue
            cycle = await cycles.get_cycle(cycle_id)
            logger.warning(
                "campaign_cycle_reattached cycle=%s run=%s status=%s (#1922)",
                cycle_id,
                latest.run_id,
                latest.status,
            )
            self._execute(cycle, latest, reentry=True)
            taken_up.append(cycle_id)
        return taken_up

    async def launched_cycles(self) -> list[str]:
        """The cycles every live campaign's launched intents created."""
        cycle_ids = []
        for project in await self._creation.project_registry.list_projects():
            for campaign in await self._campaigns.list_campaigns(project.project_id):
                if campaign.state is CampaignState.COMPLETED:
                    continue
                cycle_ids.extend(
                    intent.cycle_id
                    for intent in await self._campaigns.launch_intents(campaign.campaign_id)
                    if intent.state is LaunchIntentState.LAUNCHED and intent.cycle_id
                )
        return cycle_ids

    async def _start_first_run(self, cycle_id: str) -> Run | None:
        """Start the cycle's first run when it has not started: create it if the cycle has
        none, and start it if it is still queued and this process has not started it."""
        cycles = self._creation.cycle_registry
        runs = await cycles.list_runs(cycle_id)
        if runs:
            run = min(runs, key=lambda r: r.run_number)
            if run.status != RunStatus.QUEUED.value or run.run_id in self._started:
                return None
            cycle = await cycles.get_cycle(cycle_id)
            self._execute(cycle, run)
            return run
        cycle = await cycles.get_cycle(cycle_id)
        run = first_run(cycle, initiated_by=RunInitiator.SYSTEM)
        await cycles.create_run(run)
        self._event_bus.emit(
            EventType.CYCLE_CREATED,
            entity_type="cycle",
            entity_id=cycle.cycle_id,
            context={"cycle_id": cycle.cycle_id, "project_id": cycle.project_id},
            payload={
                "project_id": cycle.project_id,
                "created_by": cycle.created_by,
                "squad_profile_id": cycle.squad_profile_id,
                "prd_ref": cycle.prd_ref,
                "campaign_id": cycle.campaign_id,
                "kind": cycle.kind,
            },
        )
        self._execute(cycle, run)
        return run

    def _execute(self, cycle: Cycle, run: Run, *, reentry: bool = False) -> None:
        self._started.add(run.run_id)
        execution = (
            self._executor.execute_cycle(
                cycle.cycle_id, run.run_id, cycle.squad_profile_id, reentry=True
            )
            if reentry
            else self._executor.execute_cycle(cycle.cycle_id, run.run_id, cycle.squad_profile_id)
        )
        task = asyncio.create_task(execution)
        self._running.add(task)
        task.add_done_callback(self._running.discard)
