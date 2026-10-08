"""Pinning a unit's snapshot when it is admitted (SIP-0110 §0.7; slice 3c, #2096).

A standalone cycle pins when it is created, and a campaign when it is admitted; a campaign's
proposals and cycles use the campaign's. The pin reads the project's lessons and approvals as they
stand at that moment and stores the whole snapshot, once: a restart asks again and gets the
original, so a unit's guidance never changes while it runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from squadops.memory.lessons import RecallPolicy, Snapshot, UnitKind, pin

if TYPE_CHECKING:
    from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort


async def pin_unit(
    store: CrossCycleMemoryStorePort,
    *,
    unit_kind: UnitKind,
    unit_id: str,
    project_id: str,
    pinned_at: datetime,
    disabled: bool,
    policy: RecallPolicy | None = None,
) -> Snapshot:
    """The unit's snapshot: the one it already pinned, or a new pin of what is approved now."""
    held = await store.get_snapshot(unit_kind, unit_id)
    if held is not None:
        return held
    snapshot = pin(
        unit_kind=unit_kind,
        unit_id=unit_id,
        pinned_at=pinned_at,
        disabled=disabled,
        revisions=await store.list_revisions(project_id),
        approvals=await store.list_approvals(project_id),
        policy=policy,
    )
    return await store.record_snapshot(snapshot)
