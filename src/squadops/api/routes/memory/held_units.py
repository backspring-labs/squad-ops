"""The units a memory revocation or withdrawal names (SIP-0110 §0.7, Appendix A §3.8; #2210, #2179).

A lesson's revocation and a project instruction's emergency withdrawal reach units admitted
afterwards. The units already holding one keep it in their pinned snapshot, so each answer names
them: the running units, whose work is halted or restarted under a new snapshot, apart from the
finished ones, whose measurements are set apart.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import Request

from squadops.api.routes.cycles.mapping import cycle_status_of
from squadops.api.runtime.deps import get_campaign_registry, get_cycle_registry
from squadops.campaigns.models import CampaignState
from squadops.cycles.models import CycleStatus
from squadops.memory.lessons import Snapshot, UnitKind

#: A cycle in these states still runs: an answer names it as work to halt (#2210).
_RUNNING_CYCLE = frozenset({CycleStatus.CREATED, CycleStatus.ACTIVE, CycleStatus.PAUSED})


async def _still_runs(request: Request, s: Snapshot) -> bool:
    """Whether the unit that pinned ``s`` still runs: a campaign not completed, or a cycle whose
    status, read the way the cycle route reads it, has not ended. A unit that can't be read counts
    as running: an emergency revocation names one unit too many rather than miss one (#2210)."""

    try:
        if s.unit_kind is UnitKind.CAMPAIGN:
            campaign = await get_campaign_registry(request).get_campaign(s.unit_id)
            return campaign.state is not CampaignState.COMPLETED
        cycles = get_cycle_registry(request)
        cycle = await cycles.get_cycle(s.unit_id)
        return cycle_status_of(cycle, await cycles.list_runs(s.unit_id)) in _RUNNING_CYCLE
    except Exception:  # noqa: BLE001 — unreadable is named, never dropped
        return True


async def running_and_finished(
    request: Request, snapshots: Iterable[Snapshot]
) -> tuple[list[Snapshot], list[Snapshot]]:
    """The units holding a record, split: those still running, then those that finished."""
    live: list[Snapshot] = []
    finished: list[Snapshot] = []
    for s in snapshots:
        (live if await _still_runs(request, s) else finished).append(s)
    return live, finished


def unit_row(s: Snapshot) -> dict[str, Any]:
    return {
        "unit_kind": s.unit_kind.value,
        "unit_id": s.unit_id,
        "snapshot_id": s.snapshot_id,
        "pinned_at": s.pinned_at.isoformat(),
    }


def next_step(live: list[Snapshot], finished: list[Snapshot], *, rule: str) -> str:
    """What the operator does next, by who holds the record. ``rule`` is the section it follows."""
    if live:
        return (
            "units admitted from now pin without it. Each unit named here keeps it while it runs: "
            "halt or restart its work under a new snapshot, and set its measurements apart "
            f"({rule}). A unit pins once: a new run of a standalone cycle, or a new cycle of a "
            "campaign, reads the same snapshot, so the restart is a new standalone cycle or a new "
            "campaign."
        )
    if finished:
        return (
            "units admitted from now pin without it; no running unit holds it. The finished units "
            f"named here ran with it: set their measurements apart ({rule})."
        )
    return "units admitted from now pin without it; no unit holds it"
