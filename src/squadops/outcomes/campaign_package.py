"""What a campaign's evidence package carries of its outcome evaluations (SIP-0113 §4.4, §4.2; #2418).

Read at the package's materialization, from the scenario store, never written by a model: each
cycle's latest record against the campaign's pinned suite, with
- its scenarios' results, by id;
- its contribution, read against the record of the tree it built on (§4.4);
- its quality readings, and their deltas against that tree and against the calibration's reading,
  the campaign's baseline (§4.2).

Never a scenario's goal, steps or checks: the store keeps those, held out. The package is a
project-level artifact that no squad task's inputs list (``test_held_out_packages.py``).
Reporting-only: nothing that decides the campaign reads this section.

``campaign_interventions`` is the package's intervention section (§4.3): the ledger's entries, each
with its classification's severity, the interventions declared outside the interface, and the two
gaps §7 prediction 5 reads. AOR reads *no intervention above advisory* from it (§4.6).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from squadops.campaigns.models import ControlLogEntry
from squadops.outcomes.contribution import NotComparable, contribution
from squadops.outcomes.ledger import LedgerEntry, ledger
from squadops.outcomes.quality_deltas import Against, QualityDeltas, quality_deltas
from squadops.scenarios.evaluation import BlockedReason, EvaluationRecord

if TYPE_CHECKING:
    from squadops.ports.outcomes import InterventionLedgerPort
    from squadops.ports.scenarios import ScenarioStorePort


async def campaign_outcomes(
    store: ScenarioStorePort, campaign_id: str, cycle_ids: list[str]
) -> dict | None:
    """The campaign's outcome readings for its package, ``None`` when no suite is pinned."""
    pin = await store.get_pin(campaign_id)
    if pin is None:
        return None
    latest: dict[str, EvaluationRecord] = {}
    for cycle_id in cycle_ids:
        held = [
            r
            for r in await store.evaluations_for_cycle(cycle_id)
            # Its own campaign's: a reading of the same suite written with no campaign (§10p
            # ruling 13's tool) never stands in for the campaign's record.
            if r.campaign_id == campaign_id and r.suite_digest == pin.suite_digest
        ]
        if held:
            latest[cycle_id] = max(held, key=lambda r: r.evaluated_at)
    by_tree = {r.evaluated_tree_identity: r for r in latest.values()}
    baseline = next((r for r in latest.values() if r.previous_accepted_tree_identity is None), None)
    return {
        "suite_digest": pin.suite_digest,
        "cycles": [
            _cycle_section(cycle_id, latest.get(cycle_id), by_tree, baseline)
            for cycle_id in cycle_ids
        ],
    }


def _deltas(read: QualityDeltas) -> dict:
    """The measures that moved, and what wasn't compared and why; unmoved ones are counted."""
    moved = [d for d in read.deltas if d.delta]
    return {
        "against_tree": read.against_tree,
        "moved": [[d.measure, d.page, d.before, d.after, d.delta] for d in moved],
        "unmoved": len(read.deltas) - len(moved),
        "not_compared": [list(item) for item in read.not_compared],
    }


def _contribution(record: EvaluationRecord, previous: EvaluationRecord | None) -> dict:
    if record.previous_accepted_tree_identity and previous is None:
        return {"reading": None, "unread_because": "no record of the tree it built on"}
    try:
        read = contribution(record, previous)
    except NotComparable as e:
        return {"reading": None, "unread_because": str(e)}
    return {
        "reading": read.reading,
        "newly_passing": list(read.newly_passing),
        "regressed": list(read.regressed),
        "unverified": list(read.unverified),
    }


def _page_controls(record: EvaluationRecord) -> dict:
    """§10p ruling 4: of the scenarios a browser read (an outcome naming its runner), how many
    found no control by any of their names (``control_absent``). Beside its results so a page
    scenario whose names match no delivery can't hide a job. Only when a browser read one, so a
    package with no page scenario is the package it was."""
    read = [o for o in record.outcomes if o.runner]
    if not read:
        return {}
    absent = [o for o in read if o.blocked_reason is BlockedReason.CONTROL_ABSENT]
    return {"page_controls": {"read_in_a_browser": len(read), "control_absent": len(absent)}}


def _cycle_section(
    cycle_id: str,
    record: EvaluationRecord | None,
    by_tree: dict[str, EvaluationRecord],
    baseline: EvaluationRecord | None,
) -> dict:
    if record is None:
        return {"cycle_id": cycle_id, "evaluation": None}
    built_on = record.previous_accepted_tree_identity
    previous = by_tree.get(built_on) if built_on else None
    section: dict = {
        "cycle_id": cycle_id,
        "evaluation": record.evaluation_id,
        "tree": record.evaluated_tree_identity,
        "built_on": built_on,
        "scenarios": [
            [
                o.scenario_id,
                o.result.value if o.result else o.applicability.value,
                o.blocked_reason.value if o.blocked_reason else None,
            ]
            for o in record.outcomes
        ],
        "quality": record.quality.as_dict() if record.quality else None,
        "lint": record.lint.as_dict() if record.lint else None,
        "contribution": _contribution(record, previous),
        **_page_controls(record),
    }
    if previous is not None:
        section["vs_previous"] = _deltas(quality_deltas(record, previous, against=Against.PREVIOUS))
    if baseline is not None and baseline is not record:
        try:
            section["vs_baseline"] = _deltas(
                quality_deltas(record, baseline, against=Against.BASELINE)
            )
        except NotComparable as e:
            section["vs_baseline"] = {"unread_because": str(e)}
    return section


async def campaign_interventions(
    store: InterventionLedgerPort, campaign_id: str, control_log: Sequence[ControlLogEntry]
) -> dict:
    """The campaign's interventions for its package (§4.3): each row a person or the supervisor
    acted with, and each declared action outside the interface, with its severity once
    classified; and the rows not yet classified, and classifications naming no row of it."""
    read = ledger(
        campaign_id,
        control_log,
        await store.classifications(campaign_id),
        await store.declared(campaign_id),
    )
    return {
        "entries": [_entry(e) for e in read.entries],
        "unclassified": list(read.unclassified),
        "orphaned": list(read.orphaned),
    }


def _entry(entry: LedgerEntry) -> dict:
    """One intervention as the package keeps it: its severity and reason once classified, or as
    declared; ``None`` for both while it awaits its classification."""
    kind = entry.classification or entry.declared
    return {
        "entry_id": entry.entry_id,
        "operation": entry.operation,
        "actor": entry.actor,
        "at": entry.at.isoformat(),
        "severity": kind.severity if kind else None,
        "reason": kind.reason if kind else None,
    }
