"""The proposal ledger (SIP-0109 §9.4), read from the control log.

One entry per proposal version: the change request as it was submitted to the increment gate,
the ruling on it with its reason and who ruled, the outcome of the cycles that carried it, and the
supervisor's classification of what went wrong.

#2578 part 4: an increment spans its cycle, then any repair or retry of it, and the entry lists
each one with the row that decided it. A continuation is attached by its own launch's binding (the
proposal and version ``CONTINUED_KEYS`` carry into its block), read from the launch outbox, never
by guessing from cycle order. There is no writable increments table: this view is derived. Every part is a control-log row already — the
``submit``, ``rule``, ``decide`` and ``classify`` rows — so the ledger is a projection of the one
authority, never a second record that could disagree with it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from squadops.campaigns.models import (
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntent,
)


@dataclass(frozen=True)
class LedgerEntry:
    proposal_id: str
    version: int
    content_hash: str
    baseline_tree: str
    cycle_id: str
    run_id: str
    submitted_at: str
    #: The applied ruling on this version, when it was ruled: decision, reason, who, when.
    ruling: dict | None = None
    #: The decision the last carrying cycle's end produced: its row, ending, verdict and action.
    outcome: dict | None = None
    #: #2578 part 4: each cycle that carried this version, in launch order: its id, its kind
    #: (``increment``, then ``repair`` or ``retry``) and, once decided, the deciding row's fields.
    cycles: tuple[dict, ...] = ()
    #: The supervisor's latest classification of this version, with its reason and who.
    classification: dict | None = None


#: The decision fields a cycle's entry shows, in the order the ledger reads them.
_DECISION_FIELDS = ("row", "ending", "verdict", "action", "outcome", "unbuilt")
_CONTINUATIONS = (CycleKind.REPAIR, CycleKind.RETRY)


def ledger(log: list[ControlLogEntry], launches: Iterable[LaunchIntent] = ()) -> list[LedgerEntry]:
    """The ledger, in submission order. ``launches`` is the campaign's launch outbox: with it, a
    repair's or retry's cycle is listed under the version its binding continues, and its end
    decides that version's outcome. Without it, only each version's own cycle is read."""
    applied = [e for e in log if e.outcome == ControlOutcome.APPLIED]
    entries: dict[tuple[str, int], dict] = {}
    for e in applied:
        b = e.binding
        if e.operation == ControlOperation.SUBMIT:
            key = (b["proposal_id"], b["version"])
            entries[key] = {
                "proposal_id": b["proposal_id"],
                "version": b["version"],
                "content_hash": b["content_hash"],
                "baseline_tree": b["baseline_tree"],
                "cycle_id": b["cycle_id"],
                "run_id": e.target,
                "submitted_at": e.committed_at.isoformat(),
            }
    decides_for, cycles = _carrying_cycles(entries, launches)
    for e in applied:
        b = e.binding
        if e.operation == ControlOperation.RULE:
            key = (b["proposal_id"], b["version"])
            if key in entries:
                entries[key]["ruling"] = {
                    "decision": b["decision"],
                    "reason": e.reason,
                    "actor": e.actor,
                    "actor_role": e.actor_role,
                    "at": e.committed_at.isoformat(),
                }
        elif e.operation == ControlOperation.DECIDE and "row" in b:
            # A cycle's end decides for its version, and the last cycle's decision is the
            # version's outcome. A calibration record's decision (§24cc) names no cycle, and no
            # proposal was submitted before it.
            decided = decides_for.get(b.get("cycle_id", ""))
            if decided is not None:
                decision = {k: b.get(k) for k in _DECISION_FIELDS if b.get(k) is not None}
                entries[decided]["outcome"] = decision
                for cycle in cycles[decided]:
                    if cycle["cycle_id"] == b["cycle_id"]:
                        cycle.update(decision)
        elif e.operation == ControlOperation.CLASSIFY:
            key = (b["proposal_id"], b["version"])
            if key in entries:
                entries[key]["classification"] = {
                    "classification": b["classification"],
                    "reason": e.reason,
                    "actor": e.actor,
                    "at": e.committed_at.isoformat(),
                }
    return [
        LedgerEntry(**entry, cycles=tuple(cycles.get(key, ()))) for key, entry in entries.items()
    ]


def _carrying_cycles(
    entries: dict[tuple[str, int], dict], launches: Iterable[LaunchIntent]
) -> tuple[dict[str, tuple[str, int]], dict[tuple[str, int], list[dict]]]:
    """The version each cycle's end decides for, and each version's cycles in launch order. A
    version's own cycle decides for the last version it carried (a revision is submitted in the
    cycle that carried the one before it); a repair or retry, for the version its binding names."""
    by_cycle: dict[str, list[tuple[str, int]]] = {}
    for key, entry in entries.items():
        by_cycle.setdefault(entry["cycle_id"], []).append(key)
    decides_for: dict[str, tuple[str, int]] = {}
    cycles: dict[tuple[str, int], list[dict]] = {}
    for cycle_id, keys in by_cycle.items():
        key = max(keys, key=lambda k: k[1])
        decides_for[cycle_id] = key
        cycles.setdefault(key, []).append({"cycle_id": cycle_id, "kind": str(CycleKind.INCREMENT)})
    for intent in sorted(launches, key=lambda i: i.created_at):
        if intent.cycle_kind not in _CONTINUATIONS or intent.cycle_id is None:
            continue
        block = _block_of(intent)
        bound = (block.get("proposal_id"), block.get("version"))
        if bound in entries and intent.cycle_id not in decides_for:
            decides_for[intent.cycle_id] = bound
            cycles.setdefault(bound, []).append(
                {"cycle_id": intent.cycle_id, "kind": str(intent.cycle_kind)}
            )
    return decides_for, cycles


def _block_of(intent: LaunchIntent) -> dict:
    """The ``campaign_proposal`` block a launch carries, or an empty one."""
    body = intent.cycle_request.get("body") or {}
    block = (body.get("execution_overrides") or {}).get("campaign_proposal")
    return block if isinstance(block, dict) else {}
