"""The proposal ledger (SIP-0109 §9.4), read from the control log.

One entry per proposal version: the change request as it was submitted to the increment gate,
the ruling on it with its reason and who ruled, the outcome of the cycle that carried it, and the
supervisor's classification of what went wrong. Every part is a control-log row already — the
``submit``, ``rule``, ``decide`` and ``classify`` rows — so the ledger is a projection of the one
authority, never a second record that could disagree with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from squadops.campaigns.models import ControlLogEntry, ControlOperation, ControlOutcome


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
    #: The decision the carrying cycle's end produced: its row, ending, verdict and action.
    outcome: dict | None = None
    #: The supervisor's latest classification of this version, with its reason and who.
    classification: dict | None = None


def ledger(log: list[ControlLogEntry]) -> list[LedgerEntry]:
    """The ledger, in submission order."""
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
    by_cycle: dict[str, list[tuple[str, int]]] = {}
    for key, entry in entries.items():
        by_cycle.setdefault(entry["cycle_id"], []).append(key)
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
            # The cycle's end decides for the last version it carried.
            versions = by_cycle.get(b["cycle_id"], [])
            if versions:
                entries[max(versions, key=lambda k: k[1])]["outcome"] = {
                    k: b.get(k)
                    for k in ("row", "ending", "verdict", "action", "outcome", "unbuilt")
                    if b.get(k) is not None
                }
        elif e.operation == ControlOperation.CLASSIFY:
            key = (b["proposal_id"], b["version"])
            if key in entries:
                entries[key]["classification"] = {
                    "classification": b["classification"],
                    "reason": e.reason,
                    "actor": e.actor,
                    "at": e.committed_at.isoformat(),
                }
    return [LedgerEntry(**entry) for entry in entries.values()]
