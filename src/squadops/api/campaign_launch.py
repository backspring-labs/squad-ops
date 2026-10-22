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
from typing import Any

import pydantic

from squadops.api.cycle_schemas import CycleCreateRequest
from squadops.api.routes.cycles.cycles import CreationPorts, first_run, prepare_cycle
from squadops.api.routes.cycles.errors import cycle_error_envelope
from squadops.api.routes.cycles.mapping import cycle_status_of
from squadops.campaigns.launcher import BoxVerdict, CampaignLauncher, LaunchRefused, unblocked
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    ControlOperation,
    CycleKind,
    LaunchIntent,
    LaunchIntentState,
)
from squadops.cycles.models import Cycle, CycleError, CycleStatus, Run, RunInitiator, RunStatus
from squadops.events.types import EventType
from squadops.memory.cycle_bindings import instructions_bound_for, missing_from, names_current
from squadops.memory.lessons import UnitKind
from squadops.memory.pinning import cycle_binding
from squadops.memory.records import RecordRefused
from squadops.memory.reference_binding import bound_for_cycle
from squadops.memory.task_instructions import carried, carrying
from squadops.ports.memory.cross_cycle import RecordIncompatible

logger = logging.getLogger(__name__)

#: A cycle in one of these dispatches nothing more, so it needs no binding filled (§5ad). A paused
#: one can resume, so it isn't one.
_ENDED = frozenset({CycleStatus.COMPLETED, CycleStatus.CANCELLED})

#: The launches that continue an earlier cycle, so carry its instructions given to carry (§3.7).
_CONTINUING = frozenset({CycleKind.REPAIR, CycleKind.RETRY})

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
        """The intent's cycle, built and preflighted by the cycle-create path. What that path
        refuses as a client error (its 4xx: a preflight block, a project or profile that does not
        exist, a request it cannot validate) is ``LaunchRefused``, which escalates the campaign
        (#1971). Anything else is a fault, and propagates for the next drain to repeat."""
        campaign = await self._campaigns.get_campaign(intent.campaign_id)
        try:
            request = CycleCreateRequest(**intent.cycle_request["body"])
        except pydantic.ValidationError as e:
            raise LaunchRefused(f"VALIDATION_ERROR: {e}") from e
        try:
            prepared = await prepare_cycle(
                self._creation,
                campaign.project_id,
                request,
                created_by=LAUNCHER_ACTOR,
                initiated_by=RunInitiator.SYSTEM,
                campaign_id=campaign.campaign_id,
                kind=intent.cycle_kind.value,
            )
        except CycleError as e:
            status, detail = cycle_error_envelope(e)
            if status >= 500:
                raise
            raise LaunchRefused(f"{detail['error']['code']}: {e}") from e
        # #2178: the launch's task instructions are its cycle's admitted inputs, stored before
        # the launcher persists the cycle, so its first run reads them. A launch repeated by its
        # launch id stores the earlier cycle's; these then target an id that was never stored,
        # which nothing matches. No store is a fault the next drain repeats, never a silent drop.
        if prepared.instructions:
            records = self._creation.memory_records
            if records is None:
                raise RuntimeError(
                    f"launch {intent.launch_id} gives task instructions, and no store holds them"
                )
            for record in prepared.instructions:
                await records.create(record)
        await self._carry_instructions(intent, prepared.cycle)
        await self._bind_for_cycle(campaign, prepared.cycle)
        return prepared.cycle

    async def _bind_for_cycle(self, campaign: Campaign, cycle: Cycle) -> None:
        """SIP-0110 §5ad (the owner's ruling of 2026-10-20): the campaign's snapshot fixes which
        instruction revisions are in force, and this cycle binds their ``@current`` references at
        its own pinned source commit, now, as its launch. Every dispatch of the cycle reads what is
        recorded here. A store that can't be read or written is a fault the next drain repeats:
        the cycle never launches reading a binding it doesn't have."""
        store = self._creation.memory_store
        if store is None:
            return  # no snapshot is pinned without a store, so nothing to bind
        try:
            snapshot = await store.get_snapshot(UnitKind.CAMPAIGN, campaign.campaign_id)
        except RecordIncompatible as e:
            # Deterministic: as a fault every drain would repeat it, holding every launch behind
            # it. Refused, so the campaign escalates.
            raise LaunchRefused(
                f"VALIDATION_ERROR: the campaign's snapshot can't be read: {e}"
            ) from e
        if snapshot is None or not names_current(snapshot.instructions):
            return
        instructions = await instructions_bound_for(
            snapshot.instructions, self._creation.reference_resolvers or {}, cycle_binding(cycle)
        )
        await store.record_cycle_bindings(
            cycle.cycle_id,
            UnitKind.CAMPAIGN.value,
            campaign.campaign_id,
            instructions,
            datetime.now(UTC),
        )

    async def _carry_instructions(self, intent: LaunchIntent, cycle: Cycle) -> None:
        """A repair or a retry continues a cycle (§10a), and carries into it each of that cycle's
        task instructions given with ``carries_into: continuations``, as its own admitted record
        linked to the original (SIP-0110 Appendix A §3.7; #2178). A read that fails is a fault the
        next drain repeats: a binding input is never dropped."""
        if intent.cycle_kind not in _CONTINUING:
            return
        records = self._creation.memory_records
        if records is None:
            return  # no store holds instructions, so the continued cycle has none to carry
        continued = await self._continued_cycle(intent)
        originals = carrying(
            await records.list_project(cycle.project_id), from_cycle=str(continued)
        )
        try:
            # T16: the continuation's admission binds each @current reference again, for itself.
            bound = await bound_for_cycle(
                [r for o in originals for r in o.current.references],
                self._creation.reference_resolvers or {},
                cycle_binding(cycle),
            )
            copies = carried(
                originals,
                to_cycle=cycle.cycle_id,
                project_id=cycle.project_id,
                now=datetime.now(UTC),
                bound=bound,
            )
        except RecordRefused as e:
            # The supervisor decides: withdraw the instruction, or revise its reference (§3.6).
            raise LaunchRefused(f"VALIDATION_ERROR: a carried task instruction: {e}") from e
        for copy in copies:
            await records.create(copy)

    async def _continued_cycle(self, intent: LaunchIntent) -> str:
        """The cycle a repair or a retry continues: the one its request names (``continues``). An
        intent written before the request named it is read from its log: the deciding row's cycle,
        or for the owner's word (a ``resume``, which names none) the cycle of the latest decision
        before it, as ``owner_action`` read it. Naming none is refused, so the campaign escalates:
        as a fault, every drain would repeat it, holding every intent queued behind it."""
        overrides = intent.cycle_request.get("body", {}).get("execution_overrides") or {}
        named = (overrides.get("campaign_proposal") or {}).get("continues")
        if named:
            return str(named)
        log = await self._campaigns.control_log(intent.campaign_id)
        at = next((i for i, e in enumerate(log) if e.entry_id == intent.decision_entry_id), None)
        if at is not None:
            named = (log[at].binding or {}).get("cycle_id")
            if not named:
                decided = [
                    e for e in log[:at] if e.operation is ControlOperation.DECIDE and e.target
                ]
                named = decided[-1].target if decided else None
        if not named:
            raise LaunchRefused(
                f"VALIDATION_ERROR: the {intent.cycle_kind.value} names no cycle it continues, so "
                "the task instructions given to carry into it can't be found"
            )
        return str(named)

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

    async def _fill_missing_bindings(self, cycle: Cycle) -> None:
        """§5ad: the cycle that starts is the one stored under its launch id, which a repeated
        launch finds rather than creates. That launch bound the cycle it built and threw away, so
        the stored cycle holds only what its first attempt bound; a re-binding committed between
        the attempts listed no launched cycle to reach it (the sixth read of #2570). So before its
        first run starts, under the launch lock, its missing entries are filled. One that can't be
        filled is logged, and the run starts: a required reference then holds it, loudly, rather
        than the run waiting on a drain nothing schedules. A run held on its bindings fills
        through it too (``fill_held``, #2178)."""
        store = self._creation.memory_store
        if store is None or not cycle.campaign_id:
            return
        try:
            snapshot = await store.get_snapshot(UnitKind.CAMPAIGN, cycle.campaign_id)
            if snapshot is not None and names_current(snapshot.instructions):
                await self._fill_binding(store, snapshot, cycle.cycle_id)
        except Exception:
            logger.warning(
                "cycle_binding_launch_fill_failed cycle=%s", cycle.cycle_id, exc_info=True
            )

    async def fill_held(self, cycle_id: str) -> None:
        """§5ad for a run held on its bindings (SIP-0110 §A.3.6, #2178): its cycle's missing
        entries filled now, by the fill a launch uses and under the launch lock, so the hold's
        release never waits on the sweep and binds exactly as the launch would have. One that
        can't be filled is logged, and the run stays held."""
        async with self._lock:
            await self._fill_missing_bindings(
                await self._creation.cycle_registry.get_cycle(cycle_id)
            )

    def launches_held(self) -> asyncio.Lock:
        """§5ad: what a campaign's re-binding holds from listing its launched cycles until its
        snapshot names the new revision, the lock every drain launches under. No cycle launches in
        between, binding at the revision being replaced where the re-binding can't see it: one
        launched before is listed and bound, and one launched after reads the committed snapshot
        (the fifth read of #2570)."""
        return self._lock

    async def reconcile_bindings(self) -> list[str]:
        """§5ad, the sweep's (every interval, beside the ruling bounds): each running cycle of a live
        campaign holds a binding for every pinned instruction naming ``@current``. One it lacks is
        filled. A launch and a re-binding write their own entries, under the launch lock and before
        the snapshot names them, and a cycle's first run is filled before it starts, so this is the
        safety net: a cycle launched before its campaign's bindings were recorded (the deploy that
        brings them), or an entry a store lost. An entry the
        cycle holds is never rewritten. Until filled, a required reference holds its task. Each
        project, campaign and cycle is apart: one that can't be read is logged, and the rest are
        filled. Returns the cycles filled."""
        store = self._creation.memory_store
        if store is None:
            return []
        filled: list[str] = []
        for project in await self._creation.project_registry.list_projects():
            try:
                campaigns = await self._campaigns.list_campaigns(project.project_id)
            except Exception:
                logger.warning(
                    "cycle_binding_reconcile_unlisted project=%s", project.project_id, exc_info=True
                )
                continue
            for campaign in campaigns:
                if campaign.state is CampaignState.COMPLETED:
                    continue
                try:
                    filled += await self._reconcile_campaign(store, campaign.campaign_id)
                except Exception:
                    logger.warning(
                        "cycle_binding_reconcile_failed campaign=%s",
                        campaign.campaign_id,
                        exc_info=True,
                    )
        return filled

    async def _reconcile_campaign(self, store: Any, campaign_id: str) -> list[str]:
        snapshot = await store.get_snapshot(UnitKind.CAMPAIGN, campaign_id)
        if snapshot is None or not names_current(snapshot.instructions):
            return []
        filled = []
        for intent in await self._campaigns.launch_intents(campaign_id):
            if intent.state is not LaunchIntentState.LAUNCHED or not intent.cycle_id:
                continue
            try:
                if await self._fill_binding(store, snapshot, intent.cycle_id):
                    filled.append(intent.cycle_id)
            except Exception:
                logger.warning("cycle_binding_fill_failed cycle=%s", intent.cycle_id, exc_info=True)
        return filled

    async def _fill_binding(self, store: Any, snapshot: Any, cycle_id: str) -> bool:
        missing = missing_from(await store.get_cycle_binding(cycle_id), snapshot.instructions)
        if not missing:
            return False
        cycles = self._creation.cycle_registry
        cycle = await cycles.get_cycle(cycle_id)
        if cycle_status_of(cycle, await cycles.list_runs(cycle_id)) in _ENDED:
            return False
        bound = await instructions_bound_for(
            missing, self._creation.reference_resolvers or {}, cycle_binding(cycle)
        )
        await store.record_cycle_bindings(
            cycle_id, UnitKind.CAMPAIGN.value, snapshot.unit_id, bound, datetime.now(UTC)
        )
        return True

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
        - **A queued run that follows only completed runs** (#2042): the process died after its
          gate passed and its successor was created, before the successor started. It is
          started, once, as the dying process would have. A first run left queued is the
          drain's (``_start_first_run``).
        - A cycle whose ending is recorded is left to the startup re-hearing; a failed,
          cancelled or paused run is the campaign's or the owner's to act on.

        Only at startup: a later drain would find successor runs this process is already
        executing. Returns the cycles taken up."""

        cycles = self._creation.cycle_registry
        taken_up = []
        for cycle_id in await self.launched_cycles():
            runs = [r for r in await cycles.list_runs(cycle_id) if r.status != RunStatus.CANCELLED]
            if not runs:
                continue
            latest = max(runs, key=lambda r: r.run_number)
            if latest.run_id in self._started or await cycles.get_cycle_end(cycle_id) is not None:
                continue
            queued_successor = (
                latest.status == RunStatus.QUEUED.value
                and len(runs) > 1
                and all(r.status == RunStatus.COMPLETED.value for r in runs if r is not latest)
            )
            if (
                latest.status not in (RunStatus.RUNNING.value, RunStatus.COMPLETED.value)
                and not queued_successor
            ):
                continue
            cycle = await cycles.get_cycle(cycle_id)
            logger.warning(
                "campaign_cycle_reattached cycle=%s run=%s status=%s (#1922, #2042)",
                cycle_id,
                latest.run_id,
                latest.status,
            )
            self._execute(cycle, latest, reentry=not queued_successor)
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
        queued = min(runs, key=lambda r: r.run_number) if runs else None
        if queued is not None and (
            queued.status != RunStatus.QUEUED.value or queued.run_id in self._started
        ):
            return None
        cycle = await cycles.get_cycle(cycle_id)
        await self._fill_missing_bindings(cycle)
        if queued is not None:
            self._execute(cycle, queued)
            return queued
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
        task.add_done_callback(lambda done: self._execution_ended(done, cycle, run))

    def _execution_ended(self, task: asyncio.Task, cycle: Cycle, run: Run) -> None:
        """#2213: the cycle's execution is retrieved when it ends. Nothing awaits it, so an
        exception left here was logged only as asyncio's "Task exception was never retrieved",
        with no cycle or campaign named, and the campaign waited with no row. The cycle's own
        gate failure now ends it through the completion boundary; anything else that escapes is
        named here, loudly."""
        self._running.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "campaign_cycle_execution_raised",
                exc_info=error,
                extra={
                    "campaign_id": cycle.campaign_id,
                    "cycle_id": cycle.cycle_id,
                    "run_id": run.run_id,
                },
            )
