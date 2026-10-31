"""The campaign's safety guarantees, read from its evidence package (SIP-0113 §4.6; #2418).

**Ruled by the owner, 2026-10-19:** AOR's *every safety guarantee intact* means the 2.0 set's seven
(``docs/plans/2-0-0-preregistration.md`` §3), each read from the package's control log and cycle
records. The 2.0 set read them by hand; this reads them from the package alone, as the digest does.

Each reading is ``held``, ``violated`` with the rows that break it, or ``not_read`` with why. A
guarantee that can't be read is never counted as held (§4.6). Reporting-only: nothing that decides a
campaign reads these.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from squadops.campaigns.models import (
    CampaignState,
    ControlOperation,
    ControlOutcome,
    CycleKind,
)
from squadops.cycles.models import GateDecisionValue


class GuaranteeStatus(StrEnum):
    HELD = "held"
    VIOLATED = "violated"
    NOT_READ = "not_read"


@dataclass(frozen=True)
class GuaranteeReading:
    guarantee: str
    status: GuaranteeStatus
    #: What breaks it, or why it couldn't be read, or what it was read from.
    evidence: tuple[str, ...] = field(default_factory=tuple)


#: The seven, in the pre-registration's order, by the name each reading carries.
BUILD_BOUND_TO_RULING = "no build without an approving ruling bound to its version and tree"
NO_STALE_RULING = "no stale or conflicting ruling honoured"
NO_LOST_RULING = "no ruling lost"
NO_DUPLICATE_LAUNCH = "no duplicate launch"
NO_PARTIAL_PROMOTION = "no partial promotion"
NO_LAUNCH_BESIDE_CREW = "no launch beside a crew model"
PACKAGE_COMPLETE = "an evidence package complete at close"

_BOUND_KINDS = {CycleKind.RETRY.value, CycleKind.REPAIR.value}
_IMPLEMENTATION = "implementation"


def _applied(rows: list[dict], operation: ControlOperation) -> list[dict]:
    return [
        r
        for r in rows
        if r["operation"] == operation.value and r["outcome"] == ControlOutcome.APPLIED.value
    ]


def _accepted_tree_at(rows: list[dict], seq: int) -> str | None:
    """The tree the campaign had accepted when row ``seq`` was written: its last promotion, or its
    branch's last rebase (§24bv point 4), before it."""
    moved = _applied(rows, ControlOperation.PROMOTE) + _applied(
        rows, ControlOperation.BRANCH_REBASED
    )
    promoted = sorted((r for r in moved if r["seq"] < seq), key=lambda r: r["seq"])
    return promoted[-1]["binding"]["identity"] if promoted else None


def _block_of(launches: list[dict], cycle_id: str) -> Mapping[str, Any] | None:
    """The ``campaign_proposal`` block the cycle was launched with, if it carries one."""
    for intent in launches:
        if intent.get("cycle_id") == cycle_id:
            body = (intent.get("cycle_request") or {}).get("body") or {}
            block = (body.get("execution_overrides") or {}).get("campaign_proposal")
            return block if isinstance(block, Mapping) else None
    return None


def _built(cycle: dict) -> list[str]:
    """The cycle's implementation runs: where a build happened."""
    runs = {
        r["run_id"]
        for r in [*(cycle.get("revision_forms") or ()), *(cycle.get("lint_findings") or ())]
        if r.get("workload_type") == _IMPLEMENTATION
    }
    return sorted(runs)


def _approvals(rows: list[dict]) -> list[dict]:
    return [
        r
        for r in _applied(rows, ControlOperation.RULE)
        if r["binding"].get("decision") == GateDecisionValue.APPROVED.value
    ]


def build_bound_to_ruling(doc: Mapping[str, Any]) -> GuaranteeReading:
    """Every increment, retry or repair that built did so under an applied approving ruling on
    its proposal, whose baseline was the tree the campaign had accepted when it was ruled. A
    retry or a repair builds under the ruling its block carries, at that block's version."""
    rows, launches = doc["control_log"], doc["launches"]
    broken: list[str] = []
    unread: list[str] = []
    for cycle in doc["cycles"]:
        built = _built(cycle)
        if cycle["kind"] == CycleKind.CALIBRATION.value or not built:
            continue
        block = _block_of(launches, cycle["cycle_id"])
        if not block or not block.get("proposal_id"):
            unread.append(f"`{cycle['cycle_id']}` built, and its launch names no proposal")
            continue
        approvals = [
            r
            for r in _approvals(rows)
            if r["binding"].get("proposal_id") == block["proposal_id"]
            and (
                cycle["kind"] not in _BOUND_KINDS
                or r["binding"].get("version") == block.get("version")
            )
        ]
        if not approvals:
            broken.append(
                f"`{cycle['cycle_id']}` built ({', '.join(built)}) with no approving ruling on "
                f"{block['proposal_id']}"
            )
            continue
        ruling = approvals[-1]
        tree = _accepted_tree_at(rows, ruling["seq"])
        if ruling["binding"].get("baseline_tree") != tree:
            broken.append(
                f"`{cycle['cycle_id']}`'s ruling (row {ruling['seq']}) is bound to tree "
                f"{str(ruling['binding'].get('baseline_tree'))[:12]}, and the accepted tree was "
                f"{str(tree)[:12]}"
            )
    if broken:
        return GuaranteeReading(BUILD_BOUND_TO_RULING, GuaranteeStatus.VIOLATED, tuple(broken))
    if unread:
        return GuaranteeReading(BUILD_BOUND_TO_RULING, GuaranteeStatus.NOT_READ, tuple(unread))
    return GuaranteeReading(BUILD_BOUND_TO_RULING, GuaranteeStatus.HELD)


def no_stale_ruling(doc: Mapping[str, Any]) -> GuaranteeReading:
    """Every applied ruling binds the latest version submitted of its proposal when it was
    ruled, by that version's content hash; and no version was ruled two ways."""
    rows = doc["control_log"]
    submits = _applied(rows, ControlOperation.SUBMIT)
    broken: list[str] = []
    decided: dict[tuple, str] = {}
    for rule in _applied(rows, ControlOperation.RULE):
        b = rule["binding"]
        earlier = [
            s
            for s in submits
            if s["seq"] < rule["seq"] and s["binding"].get("proposal_id") == b.get("proposal_id")
        ]
        latest = max(earlier, key=lambda s: s["seq"]) if earlier else None
        if latest is None:
            broken.append(
                f"row {rule['seq']} rules {b.get('proposal_id')}, which was never submitted"
            )
        elif (latest["binding"].get("version"), latest["binding"].get("content_hash")) != (
            b.get("version"),
            b.get("content_hash"),
        ):
            broken.append(
                f"row {rule['seq']} rules {b.get('proposal_id')} v{b.get('version')}, and the "
                f"version submitted then was v{latest['binding'].get('version')}"
            )
        key = (b.get("proposal_id"), b.get("version"))
        if key in decided and decided[key] != b.get("decision"):
            broken.append(f"{key[0]} v{key[1]} was ruled {decided[key]} and {b.get('decision')}")
        decided.setdefault(key, b.get("decision"))
    if broken:
        return GuaranteeReading(NO_STALE_RULING, GuaranteeStatus.VIOLATED, tuple(broken))
    return GuaranteeReading(NO_STALE_RULING, GuaranteeStatus.HELD)


def no_lost_ruling(doc: Mapping[str, Any]) -> GuaranteeReading:
    """At close, every submitted version was ruled, or superseded by a later version of its
    proposal, or its cycle was decided by a recorded ending, or the campaign was aborted after it
    (read on the Spark's stored packages: an abort while a version awaits its ruling ends it). Read
    only at close: a version awaiting its ruling in a running campaign is pending, not lost."""
    rows = doc["control_log"]
    if doc["campaign"]["state"] != CampaignState.COMPLETED.value:
        return GuaranteeReading(
            NO_LOST_RULING, GuaranteeStatus.NOT_READ, ("the campaign has not closed",)
        )
    submits = _applied(rows, ControlOperation.SUBMIT)
    rulings = _applied(rows, ControlOperation.RULE)
    decided = {r["binding"].get("cycle_id") for r in _applied(rows, ControlOperation.DECIDE)}
    aborts = [r["seq"] for r in _applied(rows, ControlOperation.ABORT)]
    lost: list[str] = []
    for s in submits:
        b = s["binding"]
        ruled = any(
            (r["binding"].get("proposal_id"), r["binding"].get("version"))
            == (b.get("proposal_id"), b.get("version"))
            for r in rulings
        )
        superseded = any(
            o["seq"] > s["seq"] and o["binding"].get("proposal_id") == b.get("proposal_id")
            for o in submits
        )
        aborted = any(seq > s["seq"] for seq in aborts)
        if not (ruled or superseded or aborted or b.get("cycle_id") in decided):
            lost.append(f"{b.get('proposal_id')} v{b.get('version')} (row {s['seq']})")
    overdue = len(_applied(rows, ControlOperation.RULING_OVERDUE))
    if lost:
        return GuaranteeReading(NO_LOST_RULING, GuaranteeStatus.VIOLATED, tuple(lost))
    return GuaranteeReading(
        NO_LOST_RULING, GuaranteeStatus.HELD, (f"{overdue} ruling bound(s) passed",)
    )


def no_duplicate_launch(doc: Mapping[str, Any]) -> GuaranteeReading:
    """One cycle per launch intent: no intent marked launched twice, and no cycle launched by two."""
    marks = _applied(doc["control_log"], ControlOperation.MARK_LAUNCHED)
    by_intent: dict[Any, set] = {}
    by_cycle: dict[Any, set] = {}
    for m in marks:
        intent, cycle = m.get("launch_id"), m["binding"].get("cycle_id")
        by_intent.setdefault(intent, set()).add(cycle)
        by_cycle.setdefault(cycle, set()).add(intent)
    broken = [f"intent {i} launched {sorted(c)}" for i, c in by_intent.items() if len(c) > 1]
    broken += [f"cycle {c} launched by {sorted(i)}" for c, i in by_cycle.items() if len(i) > 1]
    twice = len(marks) - len(by_intent)
    if twice > 0 and not broken:
        broken.append(f"{twice} launch(es) marked more than once")
    if broken:
        return GuaranteeReading(NO_DUPLICATE_LAUNCH, GuaranteeStatus.VIOLATED, tuple(broken))
    return GuaranteeReading(NO_DUPLICATE_LAUNCH, GuaranteeStatus.HELD)


def no_partial_promotion(doc: Mapping[str, Any]) -> GuaranteeReading:
    """Every promotion carries its tree's reference and a bundle for each criterion it froze. A
    promotion stored before #1887 recorded the tree's reference (2026-10-03) has no such key, and
    reads not read, never violated: read on the Spark's three campaigns from 2026-10-02 and -03.
    A tree in the managed clone (a calibration record's, or an increment's on the campaign branch)
    is referenced by its commit."""
    broken: list[str] = []
    unread: list[str] = []
    for p in _applied(doc["control_log"], ControlOperation.PROMOTE):
        b = p["binding"]
        if b.get("calibration_record_id"):
            # §24cc: a calibration record's tree is its commit's in the managed clone, with no
            # vault reference; it is whole when it names that commit, and it freezes nothing.
            if not b.get("commit"):
                broken.append(
                    f"row {p['seq']} promotes {b['calibration_record_id']} with no commit"
                )
            continue
        if "commit" in b:
            # §24bv point 2: a repository-backed increment's tree is its captured commit on the
            # campaign branch, with no vault reference; it is whole when it names that commit.
            if not b["commit"]:
                broken.append(f"row {p['seq']} promotes {b.get('cycle_id')} with no commit")
        elif "tree_ref" not in b:
            unread.append(f"row {p['seq']} was stored before #1887 recorded a tree_ref")
        elif not b["tree_ref"]:
            broken.append(f"row {p['seq']} promotes {b.get('cycle_id')} with no tree_ref")
        broken += [
            f"row {p['seq']} froze {f.get('criterion_id')} with no bundle"
            for f in b.get("frozen_criteria") or ()
            if not f.get("bundle_ref")
        ]
    if broken:
        return GuaranteeReading(NO_PARTIAL_PROMOTION, GuaranteeStatus.VIOLATED, tuple(broken))
    if unread:
        return GuaranteeReading(NO_PARTIAL_PROMOTION, GuaranteeStatus.NOT_READ, tuple(unread))
    return GuaranteeReading(NO_PARTIAL_PROMOTION, GuaranteeStatus.HELD)


def no_launch_beside_crew(doc: Mapping[str, Any]) -> GuaranteeReading:
    """No cycle launched while the supervisor held the box. The box's model check refuses a launch
    beside an undeclared model before it is marked (``launch_blocked`` rows); a run start that
    waited on it shows only in the runtime's log, which the package doesn't carry."""
    held = False
    broken: list[str] = []
    rows = sorted(doc["control_log"], key=lambda r: r["seq"])
    for r in rows:
        if r["outcome"] != ControlOutcome.APPLIED.value:
            continue
        if r["operation"] == ControlOperation.LEASE_ACQUIRE.value:
            held = True
        elif r["operation"] == ControlOperation.LEASE_RELEASE.value:
            held = False
        elif r["operation"] == ControlOperation.MARK_LAUNCHED.value and held:
            broken.append(f"row {r['seq']} launched {r['binding'].get('cycle_id')} under the lease")
    blocked = len(_applied(rows, ControlOperation.LAUNCH_BLOCKED))
    if broken:
        return GuaranteeReading(NO_LAUNCH_BESIDE_CREW, GuaranteeStatus.VIOLATED, tuple(broken))
    return GuaranteeReading(
        NO_LAUNCH_BESIDE_CREW,
        GuaranteeStatus.HELD,
        (f"{blocked} launch(es) the box held back; run starts are read in the runtime's log",),
    )


def package_complete(doc: Mapping[str, Any]) -> GuaranteeReading:
    """At close, the package holds every launched cycle, each readable, and its outcome
    section, if it has one, readable too."""
    if doc["campaign"]["state"] != CampaignState.COMPLETED.value:
        return GuaranteeReading(
            PACKAGE_COMPLETE, GuaranteeStatus.NOT_READ, ("the campaign has not closed",)
        )
    held = {c["cycle_id"] for c in doc["cycles"]}
    broken = [
        f"launched cycle {i['cycle_id']} is missing"
        for i in doc["launches"]
        if i.get("cycle_id") and i["cycle_id"] not in held
    ]
    broken += [
        f"cycle {c['cycle_id']}'s assessment is unreadable"
        for c in doc["cycles"]
        if isinstance(c.get("assessment"), Mapping) and "unreadable" in c["assessment"]
    ]
    if isinstance(doc.get("outcomes"), Mapping) and "unreadable" in doc["outcomes"]:
        broken.append("its outcome section is unreadable")
    if broken:
        return GuaranteeReading(PACKAGE_COMPLETE, GuaranteeStatus.VIOLATED, tuple(broken))
    return GuaranteeReading(PACKAGE_COMPLETE, GuaranteeStatus.HELD)


READERS = (
    build_bound_to_ruling,
    no_stale_ruling,
    no_lost_ruling,
    no_duplicate_launch,
    no_partial_promotion,
    no_launch_beside_crew,
    package_complete,
)


def safety_guarantees(doc: Mapping[str, Any]) -> tuple[GuaranteeReading, ...]:
    """The seven readings, in the pre-registration's order."""
    return tuple(read(doc) for read in READERS)


def all_intact(readings: tuple[GuaranteeReading, ...]) -> bool | None:
    """AOR's *every safety guarantee intact*: ``True`` when all seven held, ``False`` when any was
    violated, ``None`` when any couldn't be read and none was violated (never counted as held)."""
    statuses = {r.status for r in readings}
    if GuaranteeStatus.VIOLATED in statuses:
        return False
    if GuaranteeStatus.NOT_READ in statuses:
        return None
    return True
