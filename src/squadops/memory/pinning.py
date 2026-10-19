"""Pinning a unit's snapshot when it is admitted (SIP-0110 §0.7; slice 3c, #2096).

A standalone cycle pins when it is created, and a campaign when it is admitted; a campaign's
proposals and cycles use the campaign's. The pin reads the project's lessons and approvals as they
stand at that moment and stores the whole snapshot, once: a restart asks again and gets the
original, so a unit's guidance never changes while it runs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.memory.declarations import memory_context_none, memory_disabled
from squadops.memory.lessons import RecallPolicy, Snapshot, UnitKind, pin
from squadops.memory.records import PinnedInstruction, in_force

if TYPE_CHECKING:
    from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort
    from squadops.ports.memory.records import MemoryRecordsPort

logger = logging.getLogger(__name__)


async def pin_unit(
    store: CrossCycleMemoryStorePort,
    *,
    unit_kind: UnitKind,
    unit_id: str,
    project_id: str,
    pinned_at: datetime,
    disabled: bool,
    policy: RecallPolicy | None = None,
    records: MemoryRecordsPort | None = None,
    context_withheld: bool = False,
) -> Snapshot:
    """The unit's snapshot: the one it already pinned, or a new pin of what is approved now, with
    the project instructions in force now from ``records`` (#2179). Records that can't be read
    don't cost the unit its lessons: the snapshot pins them and says why it has no instructions,
    so a task never reads an unread pin as one that held none (§3.6). A unit that declares
    ``memory_context: none`` reads neither: it pins nothing, and says so (§3.7)."""
    held = await store.get_snapshot(unit_kind, unit_id)
    if held is not None:
        return held
    instructions: tuple[PinnedInstruction, ...] = ()
    unread = None
    if records is not None and not context_withheld:
        try:
            instructions = in_force(await records.list_project(project_id))
        except Exception as e:  # noqa: BLE001 — the lessons pin; the snapshot records the miss
            unread = f"the project's instructions could not be read at admission ({e})"
            logger.warning(
                "memory_instructions_not_pinned unit=%s:%s", unit_kind, unit_id, exc_info=True
            )
    snapshot = pin(
        unit_kind=unit_kind,
        unit_id=unit_id,
        pinned_at=pinned_at,
        disabled=disabled,
        revisions=await store.list_revisions(project_id),
        approvals=await store.list_approvals(project_id),
        policy=policy,
        instructions=instructions,
        instructions_unread=unread,
        context_withheld=context_withheld,
    )
    return await store.record_snapshot(snapshot)


async def pin_standalone_cycle(
    store: CrossCycleMemoryStorePort,
    cycle: Any,
    *,
    now: datetime,
    records: MemoryRecordsPort | None = None,
) -> Snapshot | None:
    """A standalone cycle's pin at its creation (§0.7), or ``None`` for a campaign's cycle, which
    uses its campaign's snapshot."""

    if getattr(cycle, "campaign_id", None):
        return None
    config = cycle.resolved_config()
    withheld = memory_context_none(config)
    return await pin_unit(
        store,
        unit_kind=UnitKind.CYCLE,
        unit_id=cycle.cycle_id,
        project_id=cycle.project_id,
        pinned_at=now,
        disabled=withheld or memory_disabled(config),
        records=records,
        context_withheld=withheld,
    )


async def pin_campaign(
    store: CrossCycleMemoryStorePort,
    campaign: Any,
    *,
    now: datetime,
    records: MemoryRecordsPort | None = None,
) -> Snapshot:
    """A campaign's pin at its admission (§0.7); its proposals and cycles use it. A campaign-level
    memory-disabled declaration, for a live confirmation's off arm (§0.12), arrives with slice 4."""
    return await pin_unit(
        store,
        unit_kind=UnitKind.CAMPAIGN,
        unit_id=campaign.campaign_id,
        project_id=campaign.project_id,
        pinned_at=now,
        disabled=False,
        records=records,
    )
