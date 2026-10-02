"""A campaign's evidence package and its morning digest (SIP-0109 §14; #1710).

The package is a **projection of append-time records**, materialized at the campaign's close and
never re-derived from anything else: the campaign, its control log (every decision with what it
read), its launches, and per cycle the assessment, the persisted failure records and the decision
that followed. Its identity is the hash of its canonical form, so materializing it again from the
same records is idempotent, and a reader without the producing deploy can act on it.

The digest is rendered from the package alone: what was accepted, how each cycle ended and was
classified, what escalated or is held and why, and what the owner is asked to rule.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from squadops.campaigns.models import CampaignState, ControlOperation, ControlOutcome

#: Bumped when the package's shape changes; a reader checks it before reading further.
PACKAGE_VERSION = 1


def _plain(value: Any) -> Any:
    """Records as plain data: enums by value, dataclasses as dicts, datetimes as ISO text."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _plain(dataclasses.asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class CycleRecords:
    """What the package holds for one of the campaign's cycles."""

    cycle_id: str
    kind: str
    assessment: Any
    #: The latest persisted set; ``None`` when none was ever written.
    failure_records: tuple | None


def package(campaign: Any, log: list, launches: list, cycles: list[CycleRecords]) -> dict:
    """The package document, with its identity."""
    decisions = {
        e.target: e.binding
        for e in log
        if e.operation == ControlOperation.DECIDE and "row" in e.binding
    }
    body = {
        "package_version": PACKAGE_VERSION,
        "campaign": _plain(campaign),
        "control_log": _plain(log),
        "launches": _plain(launches),
        "cycles": [
            {
                "cycle_id": c.cycle_id,
                "kind": c.kind,
                "assessment": _plain(c.assessment),
                "failure_records": _plain(c.failure_records),
                "decision": decisions.get(c.cycle_id),
            }
            for c in cycles
        ],
    }
    return {**body, "identity": package_identity(body)}


def package_identity(body: dict) -> str:
    canonical = json.dumps(
        {k: v for k, v in body.items() if k != "identity"}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def digest(doc: dict) -> str:
    """The morning digest, from the package alone."""
    c = doc["campaign"]
    rows = doc["control_log"]
    lines = [
        f"# Campaign {c['campaign_id']}: {c['state']}"
        + (f" ({c['outcome']})" if c.get("outcome") else ""),
        "",
        f"**Objective:** {c['objective']['statement']}",
        f"**Measured by:** {c['objective']['measurement']}",
        f"**Package:** `{doc['identity'][:16]}` (version {doc['package_version']})",
        "",
        "## Accepted",
    ]
    promotions = [
        r
        for r in rows
        if r["operation"] == ControlOperation.PROMOTE and r["outcome"] == ControlOutcome.APPLIED
    ]
    lines += [
        f"- cycle `{r['binding']['cycle_id']}`: tree `{r['binding']['identity'][:12]}`, "
        f"{r['binding'].get('files', '?')} files"
        for r in promotions
    ] or ["- nothing was accepted"]
    lines += ["", "## Cycles", "", "| cycle | kind | ending | verdict | decided | attribution |"]
    lines.append("|---|---|---|---|---|---|")
    for cyc in doc["cycles"]:
        d = cyc["decision"] or {}
        decided = f"row {d['row']}: {d.get('outcome') or d.get('action')}" if d else "not decided"
        lines.append(
            f"| `{cyc['cycle_id']}` | {cyc['kind']} | {d.get('ending', '—')} | "
            f"{d.get('verdict') or '—'} | {decided} | {_primary(cyc['assessment'])} |"
        )
    asks = _questions(c, rows)
    lines += ["", "## For the owner", ""] + ([f"- {q}" for q in asks] or ["- nothing is waiting"])
    return "\n".join(lines) + "\n"


def _primary(assessment: dict | None) -> str:
    reading = (assessment or {}).get("attribution") or {}
    attribution = reading.get("attribution") or {}
    return attribution.get("primary") or reading.get("state") or "—"


def _questions(campaign: dict, rows: list[dict]) -> list[str]:
    applied = [r for r in rows if r["outcome"] == ControlOutcome.APPLIED]
    last = applied[-1] if applied else None
    asks = []
    if campaign["state"] == CampaignState.ESCALATED and last is not None:
        why = last["binding"].get("unbuilt") or f"§10 row {last['binding'].get('row')}"
        asks.append(f"The campaign is escalated ({why}). Resume it naming an action, or abort it.")
    if (
        campaign["state"] == CampaignState.PAUSED
        and last is not None
        and last["binding"].get("guard")
    ):
        asks.append(
            f"A limit ({last['binding'].get('paused_by')}) holds "
            f"`{last['binding'].get('action')}`. Your resume executes it as recorded."
        )
    refused = [r for r in rows if r["outcome"] == ControlOutcome.REFUSED]
    if refused:
        asks.append(
            f"{len(refused)} refused operation(s) are recorded; the control log names each."
        )
    return asks
