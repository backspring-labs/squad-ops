"""The tree an increment builds on (SIP-0109 §7.1, §7.3; #1705).

An increment cycle's implementation starts from the campaign's accepted tree: the files the
accepted cycle delivered (one rule, ``delivered_tree``, #1833), seeded beside the walking
skeleton the candidate manifest expands into. They are produced content, so the workspace's
rule — a scaffold stub never shadows produced content (#881) — hands every existing file its
accepted implementation, and only what the increment adds is a stub to fill.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from squadops.campaigns.models import CycleKind
from squadops.cycles.delivered_tree import StoredArtifact, delivered_files


def accepted_cycle_of(cycle: Any) -> str | None:
    """The accepted cycle an increment cycle builds on, from its launch's ``campaign_proposal``
    block; ``None`` for any other cycle."""
    if getattr(cycle, "kind", None) != CycleKind.INCREMENT:
        return None
    block = cycle.resolved_config().get("campaign_proposal") or {}
    return block.get("accepted_cycle_id") or None


async def accepted_tree_refs(vault: Any, cycle: Any) -> list[str]:
    """The artifact ids of the accepted tree's delivered files, for an increment cycle's
    implementation to seed; empty for any other cycle."""
    accepted_cycle = accepted_cycle_of(cycle)
    if accepted_cycle is None:
        return []
    refs = await vault.list_artifacts(cycle_id=accepted_cycle)
    chosen = delivered_files(StoredArtifact.from_record(dataclasses.asdict(r)) for r in refs)
    return list(chosen.values())
