"""The tree an increment builds on (SIP-0109 §7.1, §7.3; #1705).

An increment cycle's implementation starts from the campaign's accepted tree: the files the
accepted cycle delivered (one rule, ``delivered_tree``, #1833), seeded beside the walking
skeleton the candidate manifest expands into. They are produced content, so the workspace's
rule — a scaffold stub never shadows produced content (#881) — hands every existing file its
accepted implementation, and only what the increment adds is a stub to fill.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
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


def increment_footprint(resolved_config: Any, candidate: Any) -> tuple[str, ...] | None:
    """The files an increment may touch (§7.2): derived from the accepted manifest its launch
    carries and the candidate manifest its framing binds to, exactly as the change request's
    footprint was. ``None`` for any cycle that is not an increment."""
    from squadops.campaigns.change_request import derive_footprint_from
    from squadops.capabilities.scaffold import InterfaceManifest

    baseline = increment_baseline(resolved_config)
    if candidate is None or baseline is None:
        return None
    return derive_footprint_from(InterfaceManifest.from_yaml(baseline), candidate)


def increment_baseline(resolved_config: Any) -> str | None:
    """The accepted manifest an increment cycle's launch carries, or ``None`` for any other
    cycle."""
    if not isinstance(resolved_config, Mapping):
        return None
    block = resolved_config.get("campaign_proposal")
    if not isinstance(block, Mapping):
        return None
    baseline = block.get("baseline_manifest")
    return baseline if isinstance(baseline, str) and baseline.strip() else None
