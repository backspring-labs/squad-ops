"""What a campaign's evidence package carries of its outcome evaluations (SIP-0113 §4.4, §4.2; #2418).

Read at the package's materialization, from the scenario store, never written by a model: each
cycle's latest record against the campaign's pinned suite, with
- its scenarios' results, by id;
- its contribution, read against the record of the tree it built on (§4.4);
- its quality readings, and their deltas against that tree and against the calibration's reading,
  the campaign's baseline (§4.2);
- for an increment whose change request named goals in ``moves_goals``, what became of each, by id
  (§4.5, ``named_goals``).

**A repository-backed campaign's baseline** (§10l): its calibration is a record, not a cycle, so
the baseline is the record's reading, its commit evaluated when the record was heard. The section
names it under ``baseline``, and it stands where a calibration cycle's record stands: the tree the
first increment built on, for its contribution, and the baseline each increment's quality is
compared with. Where there is none (a read that failed, or one that ran nothing, as with no start
declaration), the section and each increment's ``vs_baseline`` say "no baseline reading", never a
delta of zero. A sample application's section is as it was.

Never a scenario's goal, steps or checks: the store keeps those, held out. The package is a
project-level artifact that no squad task's inputs list (``test_held_out_packages.py``).
Reporting-only: nothing that decides the campaign reads this section.

``campaign_interventions`` is the package's intervention section (§4.3): the ledger's entries, each
with its classification's severity, the interventions declared outside the interface, and the two
gaps §7 prediction 5 reads. AOR reads *no intervention above advisory* from it (§4.6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from squadops.campaigns.models import ControlLogEntry
from squadops.outcomes.contribution import NotComparable, contribution
from squadops.outcomes.ledger import LedgerEntry, ledger
from squadops.outcomes.named_goals import named_goal_moves
from squadops.outcomes.quality_deltas import Against, QualityDeltas, quality_deltas
from squadops.scenarios.evaluation import (
    Applicability,
    BlockedReason,
    EvaluationRecord,
    ScenarioResult,
)
from squadops.scenarios.quality import QualityStatus

if TYPE_CHECKING:
    from squadops.ports.outcomes import InterventionLedgerPort
    from squadops.ports.scenarios import ScenarioStorePort


#: §10l: what a repository-backed campaign's deltas against its baseline say where there is none.
NO_BASELINE_READING = "no baseline reading"


def _campaigns_own(records: list[EvaluationRecord], campaign_id: str, suite_digest: str):
    """The latest of ``records`` by this campaign against its pinned suite, or ``None``. A reading
    of the same suite written with no campaign (§10p ruling 13's tool) never stands in for the
    campaign's record."""
    held = [r for r in records if r.campaign_id == campaign_id and r.suite_digest == suite_digest]
    return max(held, key=lambda r: r.evaluated_at) if held else None


def _applicable(record: EvaluationRecord) -> list:
    return [o for o in record.outcomes if o.applicability is Applicability.APPLICABLE]


def _blocked_throughout(record: EvaluationRecord) -> tuple[str, ...] | None:
    """The reasons its applicable scenarios were blocked, when none got past
    ``blocked_unverified``; ``None`` when any ran."""
    applicable = _applicable(record)
    if any(o.result is not ScenarioResult.BLOCKED_UNVERIFIED for o in applicable):
        return None
    return tuple(sorted({o.blocked_reason.value for o in applicable if o.blocked_reason}))


def ran_nothing(record: EvaluationRecord) -> str | None:
    """§10l: why a baseline reading read nothing, or ``None`` when it read something. Nothing ran
    when no applicable scenario got past ``blocked_unverified`` and no quality measure was taken:
    no start declaration, a secret nothing releases, or a start that failed with no lint taken.
    Its deltas are then "no baseline reading", never a delta against measures nobody took. A
    measure that was taken (a blueprint's lint, read whatever the start did) is compared, measure
    by measure, as ``quality_deltas`` compares any."""
    readings = (record.quality, record.quality_seeded, record.lint)
    if any(r is not None and r.status is QualityStatus.MEASURED for r in readings):
        return None
    reasons = _blocked_throughout(record)
    if reasons is None:
        return None
    return f"nothing ran on its tree ({', '.join(reasons) or 'no scenario applied'})"


def credited_nothing(record: EvaluationRecord) -> str | None:
    """§10l, the second review of #2788 (P2-B): why a baseline reading can't stand as the tree an
    increment's contribution is read against, or ``None`` when it can. When none of its applicable
    scenarios got past ``blocked_unverified`` it checked none of them, so an increment that passes
    one would be credited with what nobody checked. The contribution is then unread, with why. A
    baseline where no scenario applied is read as any other: nothing applies to the increment
    either, since both start from one declaration."""
    reasons = _blocked_throughout(record)
    if reasons is None or not _applicable(record):
        return None
    return (
        f"its baseline reading ran no scenario ({', '.join(reasons)}): nothing to read it against"
    )


async def campaign_outcomes(
    store: ScenarioStorePort,
    campaign_id: str,
    cycle_ids: list[str],
    *,
    named_goals: Mapping[str, Sequence[str]],
    calibration_record_id: str | None = None,
) -> dict | None:
    """The campaign's outcome readings for its package, ``None`` when no suite is pinned.
    ``named_goals`` is each increment's ``moves_goals``, by cycle, as its approved request names
    them. ``calibration_record_id`` is a repository-backed campaign's calibration record (§10l),
    whose reading is its baseline; ``None`` for a sample application's, whose calibration is a
    cycle."""
    pin = await store.get_pin(campaign_id)
    if pin is None:
        return None
    latest: dict[str, EvaluationRecord] = {}
    for cycle_id in cycle_ids:
        record = _campaigns_own(
            await store.evaluations_for_cycle(cycle_id), campaign_id, pin.suite_digest
        )
        if record is not None:
            latest[cycle_id] = record
    by_tree = {r.evaluated_tree_identity: r for r in latest.values()}
    #: Trees whose record no contribution is read against, with why (P2-B).
    uncredited: dict[str, str] = {}
    section: dict = {"suite_digest": pin.suite_digest}
    if calibration_record_id is None:
        baseline = next(
            (r for r in latest.values() if r.previous_accepted_tree_identity is None), None
        )
        unread = None
    else:
        # §10l: the record's reading stands where the calibration cycle's would. Never a cycle's
        # record that names no previous tree: on such a campaign, that is a cycle pinned at nothing.
        baseline = _campaigns_own(
            await store.evaluations_for_calibration_record(calibration_record_id),
            campaign_id,
            pin.suite_digest,
        )
        if baseline is not None:
            by_tree = {baseline.evaluated_tree_identity: baseline, **by_tree}
        unread = NO_BASELINE_READING if baseline is None else None
        if baseline is not None and (why := ran_nothing(baseline)):
            unread = f"{NO_BASELINE_READING}: {why}"
        if baseline is not None and (why := credited_nothing(baseline)):
            uncredited[baseline.evaluated_tree_identity] = why
        section["baseline"] = _baseline_section(calibration_record_id, baseline, unread)
    section["cycles"] = [
        _cycle_section(
            cycle_id,
            latest.get(cycle_id),
            by_tree,
            baseline,
            named_goals.get(cycle_id, ()),
            baseline_unread=unread,
            uncredited=uncredited,
        )
        for cycle_id in cycle_ids
    ]
    return section


def _readings(record: EvaluationRecord) -> dict:
    """A record's scenario results by id, and its quality and lint, as the package shows them."""
    return {
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
    }


def _baseline_section(
    record_id: str, baseline: EvaluationRecord | None, unread: str | None
) -> dict:
    """§10l: the calibration record's reading, the campaign's baseline, or why there is none."""
    if baseline is None:
        return {"calibration_record_id": record_id, "evaluation": None, "unread_because": unread}
    return {
        "calibration_record_id": record_id,
        "evaluation": baseline.evaluation_id,
        "tree": baseline.evaluated_tree_identity,
        **_readings(baseline),
        **({"unread_because": unread} if unread else {}),
    }


def _deltas(read: QualityDeltas) -> dict:
    """The measures that moved, and what wasn't compared and why; unmoved ones are counted.
    §10y's failing-id lists, where both trees carry them, as the ids each list introduced and
    resolved; a section of two trees without them has no key, as before."""
    moved = [d for d in read.deltas if d.delta]
    section = {
        "against_tree": read.against_tree,
        "moved": [[d.measure, d.page, d.before, d.after, d.delta] for d in moved],
        "unmoved": len(read.deltas) - len(moved),
        "not_compared": [list(item) for item in read.not_compared],
    }
    if read.failing:
        lists = [f for f in read.failing if f.moved]
        section["failing_moved"] = [
            [f.measure, f.page, list(f.introduced), list(f.resolved)] for f in lists
        ]
        section["failing_unmoved"] = len(read.failing) - len(lists)
    return section


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
    named: Sequence[str],
    *,
    baseline_unread: str | None = None,
    uncredited: Mapping[str, str] | None = None,
) -> dict:
    if record is None:
        section: dict = {"cycle_id": cycle_id, "evaluation": None}
        if named:
            section["named_goals"] = {
                k: str(v) for k, v in named_goal_moves(named, None, None).items()
            }
        return section
    built_on = record.previous_accepted_tree_identity
    previous = by_tree.get(built_on) if built_on else None
    # P2-B: an increment built on a baseline that ran no scenario has nothing to be credited
    # against. Its quality measures are still compared, each as ``quality_deltas`` reads it.
    why = (uncredited or {}).get(built_on) if built_on else None
    section = {
        "cycle_id": cycle_id,
        "evaluation": record.evaluation_id,
        "tree": record.evaluated_tree_identity,
        "built_on": built_on,
        **_readings(record),
        "contribution": (
            {"reading": None, "unread_because": why} if why else _contribution(record, previous)
        ),
        **_page_controls(record),
    }
    if named:
        # §4.5: the goals its request named, against the tree its proposal was shown.
        moves = named_goal_moves(named, record, previous)
        section["named_goals"] = {goal: str(move) for goal, move in moves.items()}
    if previous is not None:
        section["vs_previous"] = _deltas(quality_deltas(record, previous, against=Against.PREVIOUS))
    if baseline_unread is not None:
        # §10l: a repository-backed campaign with no baseline reading says so, never a delta.
        section["vs_baseline"] = {"unread_because": baseline_unread}
    elif baseline is not None and baseline is not record:
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
