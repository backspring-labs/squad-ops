"""Reconciliation: bring Cross-Cycle Memory's observations up to the records they project
(SIP-0110 §0.3; slice 3a, #2096).

Each call reads one cycle's or one campaign's authoritative records through the ports and stores
the observations they project. A record already projected adds nothing, so a call can run as
often as wanted: after a crash between a record's commit and its projection, the next call
recovers it. That makes it safe both as a backfill over history and, later, as the hook beside a
run's finalization or a ruling.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from squadops.campaigns.models import ControlOperation
from squadops.cycles.cycle_assessment import RejectionRecord
from squadops.cycles.rejection_baseline import REJECTION_ARTIFACT_TYPE
from squadops.memory.observations import ineligibility, observe_cycle, observe_proposal_rulings

if TYPE_CHECKING:
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort

logger = logging.getLogger(__name__)

_RUN_PAGE = 100


async def _runs(registry: CycleRegistryPort, cycle_id: str) -> list:
    runs: list = []
    while True:
        page = await registry.list_runs(cycle_id, limit=_RUN_PAGE, offset=len(runs))
        runs.extend(page)
        if len(page) < _RUN_PAGE:
            return runs


async def _rejection_records(
    vault: ArtifactVaultPort, project_id: str, cycle_id: str
) -> list[RejectionRecord]:
    records = []
    refs = await vault.list_artifacts(
        project_id=project_id, cycle_id=cycle_id, artifact_type=REJECTION_ARTIFACT_TYPE
    )
    for ref in refs:
        try:
            _, content = await vault.retrieve(ref.artifact_id)
            payload = json.loads(content)
        except Exception:
            # Unreadable evidence leaves the rejection unclassified, never invents a class.
            logger.warning("memory reconcile: rejection record %s unreadable", ref.artifact_id)
            continue
        records.append(
            RejectionRecord(
                artifact_id=ref.artifact_id,
                run_id=str(ref.run_id or ""),
                gate=str(payload.get("gate") or ""),
                classes={str(k): int(v) for k, v in (payload.get("classes") or {}).items()},
                proofs=(
                    {str(k): int(v) for k, v in (payload.get("proofs") or {}).items()}
                    if "proofs" in payload
                    else None
                ),
            )
        )
    return records


async def reconcile_cycle(
    cycle_id: str,
    *,
    registry: CycleRegistryPort,
    vault: ArtifactVaultPort,
    store: CrossCycleMemoryStorePort,
) -> int:
    """Project one cycle's rejected plans and failed correction rounds; return how many were new."""
    cycle = await registry.get_cycle(cycle_id)
    if ineligibility(cycle) is not None:
        return 0
    runs = await _runs(registry, cycle_id)
    summaries = {}
    for run in runs:
        summary = await registry.get_run_loop_summary(run.run_id)
        if summary is not None:
            summaries[run.run_id] = summary
    records = await _rejection_records(vault, cycle.project_id, cycle_id)
    return await store.record_observations(observe_cycle(cycle, runs, summaries, records))


async def reconcile_campaign(
    campaign_id: str,
    *,
    campaigns: CampaignRegistryPort,
    registry: CycleRegistryPort,
    store: CrossCycleMemoryStorePort,
) -> int:
    """Project one campaign's returned proposals; return how many were new. A proposal run whose
    cycle ``ineligibility`` refuses (a fault-injected diagnostic campaign's) is left out."""
    campaign = await campaigns.get_campaign(campaign_id)
    log = await campaigns.control_log(campaign_id)
    ineligible: set[str] = set()
    for entry in log:
        if entry.operation is not ControlOperation.SUBMIT or not entry.target:
            continue
        cycle_id = entry.binding.get("cycle_id")
        if cycle_id and ineligibility(await registry.get_cycle(str(cycle_id))) is not None:
            ineligible.add(entry.target)
    return await store.record_observations(
        observe_proposal_rulings(
            campaign_id, campaign.project_id, log, ineligible_runs=frozenset(ineligible)
        )
    )


#: How far back each periodic pass looks. A cycle finishes well inside a day (a campaign's
#: ``max_elapsed_s`` is 12 hours), so a pass re-reads what could still have changed, and the
#: backfill (``scripts/dev/memory_reconcile.py``) covers anything older.
RECENT_WINDOW = timedelta(hours=48)


async def reconcile_recent(
    *,
    projects: ProjectRegistryPort,
    registry: CycleRegistryPort,
    campaigns: CampaignRegistryPort,
    vault: ArtifactVaultPort,
    store: CrossCycleMemoryStorePort,
    now: datetime,
    window: timedelta = RECENT_WINDOW,
) -> int:
    """One periodic pass beside execution: every cycle created within ``window`` and every
    campaign updated within it, projected again. A source that fails is logged and the pass goes
    on; the next pass recovers it. Returns how many observations were new."""
    since = now - window
    new = 0
    for project in await projects.list_projects():
        offset = 0
        while True:
            page = await registry.list_cycles(project.project_id, limit=_RUN_PAGE, offset=offset)
            recent = [c for c in page if c.created_at >= since]
            for cycle in recent:
                try:
                    new += await reconcile_cycle(
                        cycle.cycle_id, registry=registry, vault=vault, store=store
                    )
                except Exception:
                    logger.warning(
                        "memory_reconcile_cycle_failed cycle=%s", cycle.cycle_id, exc_info=True
                    )
            if len(recent) < len(page) or len(page) < _RUN_PAGE:
                break  # newest first: an older cycle ends the walk
            offset += len(page)
        for campaign in await campaigns.list_campaigns(project.project_id):
            if campaign.updated_at < since:
                continue
            try:
                new += await reconcile_campaign(
                    campaign.campaign_id, campaigns=campaigns, registry=registry, store=store
                )
            except Exception:
                logger.warning(
                    "memory_reconcile_campaign_failed campaign=%s",
                    campaign.campaign_id,
                    exc_info=True,
                )
    return new
