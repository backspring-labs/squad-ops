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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from squadops.outcomes.contribution import NotComparable, contribution
from squadops.outcomes.quality_deltas import Against, QualityDeltas, quality_deltas
from squadops.scenarios.evaluation import EvaluationRecord

if TYPE_CHECKING:
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
            if r.suite_digest == pin.suite_digest
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
        return {"reading": None, "not_read": "no record of the tree it built on"}
    try:
        read = contribution(record, previous)
    except NotComparable as e:
        return {"reading": None, "not_read": str(e)}
    return {
        "reading": read.reading,
        "newly_passing": list(read.newly_passing),
        "regressed": list(read.regressed),
        "unverified": list(read.unverified),
    }


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
    }
    if previous is not None:
        section["vs_previous"] = _deltas(quality_deltas(record, previous, against=Against.PREVIOUS))
    if baseline is not None and baseline is not record:
        try:
            section["vs_baseline"] = _deltas(
                quality_deltas(record, baseline, against=Against.BASELINE)
            )
        except NotComparable as e:
            section["vs_baseline"] = {"not_read": str(e)}
    return section
