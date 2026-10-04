"""A campaign's evidence package and its morning digest (SIP-0109 §14; #1710).

The package is a **projection of append-time records**, materialized at the campaign's close and
never re-derived from anything else: the campaign, its control log (every decision with what it
read), its launches, and per cycle the assessment, the persisted failure records and the decision
that followed. Its identity is the hash of its canonical form, so materializing it again from the
same records is idempotent, and a reader without the producing deploy can act on it.

The digest is rendered from the package alone: what each accepted increment shipped (the criteria
its promotion froze), each proposal version's ruling and classification, how each cycle ended, the
package's size against its bound, what escalated or is held and why, and what the owner is asked to
rule.
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
#: 2: each cycle carries its runs' revision forms (#1710).
PACKAGE_VERSION = 2

#: The size bound (#1710: "bounded, so a frontier triage of one night fits a metered model
#: budget"). A package holds records only, never logs or prompts, so it grows only with the cycles
#: the policy allows. Measured on the 2.0 set's two packages (112 KB each, four cycles): about
#: 28 KB a cycle (its assessment, its launch request, its control-log rows) and 2 KB besides. The
#: bound allows over half as much again per cycle. A package past it is named in the digest, never
#: truncated: the records are the evidence.
PACKAGE_BASE_BYTES = 8 * 1024
PACKAGE_BYTES_PER_CYCLE = 48 * 1024


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
    #: #1710: per run, the revision forms its tasks took, read from the run's persisted summary;
    #: a run whose summary predates them reads ``None``.
    revision_forms: tuple = ()


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
                "revision_forms": _plain(c.revision_forms),
                "decision": decisions.get(c.cycle_id),
            }
            for c in cycles
        ],
    }
    return {**body, "identity": package_identity(body)}


def serialized(doc: dict) -> bytes:
    """The package as it is stored and read: the form ``materialize_package`` writes."""
    return json.dumps(doc, sort_keys=True, indent=1).encode("utf-8")


def size_bound(policy: dict) -> int:
    """The bytes a package may take, from the cycles its campaign's policy allows."""
    return PACKAGE_BASE_BYTES + PACKAGE_BYTES_PER_CYCLE * int(policy["max_cycles"])


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
        f"**Measured by:** {c['objective']['measurement']}"
        + (
            f" (met at {c['objective']['target_accepted_increments']} accepted increments)"
            if c["objective"].get("target_accepted_increments")
            else ""
        ),
        f"**Package:** `{doc['identity'][:16]}` (version {doc['package_version']})",
        f"**Size:** {_kb(len(serialized(doc)))} of its {_kb(size_bound(c['policy']))} bound "
        f"({c['policy']['max_cycles']} cycles at most)",
        "",
        "## Accepted",
    ]
    lines += _accepted(doc) or ["- nothing was accepted"]
    lines += ["", "## Proposals", ""] + (
        _proposals(rows) or ["- no proposal reached the increment gate"]
    )
    lines += ["", "## Cycles", "", "| cycle | kind | ending | verdict | decided | attribution |"]
    lines.append("|---|---|---|---|---|---|")
    for cyc in doc["cycles"]:
        d = cyc["decision"] or {}
        decided = f"row {d['row']}: {d.get('outcome') or d.get('action')}" if d else "not decided"
        lines.append(
            f"| `{cyc['cycle_id']}` | {cyc['kind']} | {d.get('ending', '—')} | "
            f"{d.get('verdict') or '—'} | {decided} | {_primary(cyc['assessment'])} |"
        )
    asks = _questions(c, rows) + _over_bound(doc)
    lines += ["", "## For the owner", ""] + ([f"- {q}" for q in asks] or ["- nothing is waiting"])
    return "\n".join(lines) + "\n"


def _kb(size: int) -> str:
    return f"{size / 1024:.0f} KB"


def _accepted(doc: dict) -> list[str]:
    """Each promotion, with what it shipped: the criteria it froze (the change request's own
    statements), and any it retired."""
    kinds = {cyc["cycle_id"]: cyc["kind"] for cyc in doc["cycles"]}
    lines = []
    for r in doc["control_log"]:
        if r["operation"] != ControlOperation.PROMOTE or r["outcome"] != ControlOutcome.APPLIED:
            continue
        b = r["binding"]
        lines.append(
            f"- {kinds.get(b['cycle_id'], 'cycle')} `{b['cycle_id']}`: tree `{b['identity'][:12]}`, "
            f"{b.get('files', '?')} files"
        )
        lines += [
            f"  - froze {f['criterion_id']}: {f['statement']}"
            for f in b.get("frozen_criteria") or ()
        ]
        if b.get("retired_criteria"):
            lines.append(f"  - retired {', '.join(b['retired_criteria'])}")
    return lines


def _proposals(rows: list[dict]) -> list[str]:
    """Each version that reached the increment gate, with its ruling and its classification."""
    applied = [r for r in rows if r["outcome"] == ControlOutcome.APPLIED]

    def by_version(operation: ControlOperation, field: str) -> dict:
        return {
            (r["binding"]["proposal_id"], r["binding"]["version"]): r["binding"][field]
            for r in applied
            if r["operation"] == operation
        }

    rulings = by_version(ControlOperation.RULE, "decision")
    classes = by_version(ControlOperation.CLASSIFY, "classification")
    lines = []
    for r in applied:
        if r["operation"] != ControlOperation.SUBMIT:
            continue
        key = (r["binding"]["proposal_id"], r["binding"]["version"])
        line = f"- `{key[0]}` v{key[1]}: {rulings.get(key, 'awaiting a ruling')}"
        if key in classes:
            line += f"; classified `{classes[key]}`"
        lines.append(line)
    return lines


def _over_bound(doc: dict) -> list[str]:
    size, bound = len(serialized(doc)), size_bound(doc["campaign"]["policy"])
    if size <= bound:
        return []
    return [
        f"The evidence package is {_kb(size)}, over its {_kb(bound)} bound. It is kept whole; "
        "say why it grew before the next campaign runs."
    ]


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
    if campaign["state"] == CampaignState.AWAITING_RULING:
        asks.append(_awaiting_ruling(campaign, applied))
    waiting = _plan_gate_waiting(applied)
    if waiting:
        asks.append(waiting)
    refused = [r for r in rows if r["outcome"] == ControlOutcome.REFUSED]
    if refused:
        asks.append(
            f"{len(refused)} refused operation(s) are recorded; the control log names each."
        )
    return asks


def _plan_gate_waiting(applied: list[dict]) -> str | None:
    """A gate after framing still waiting past a ruling bound (#1708): its overdue rows are the
    campaign's latest word, with nothing that moved the campaign since. Once the gate is answered,
    the campaign moves on and the ask goes with it."""
    since: list[dict] = []
    for r in reversed(applied):
        operation = ControlOperation(r["operation"])
        if operation is ControlOperation.RULING_OVERDUE and r["binding"].get("gate"):
            since.append(r)
        elif not operation.records_only:
            break
    if not since:
        return None
    gate, run = since[0]["binding"]["gate"], since[0]["target"]
    return (
        f"The `{gate}` gate on run `{run}` waits on an answer to its design question, past its "
        f"ruling bound. Answer it (the runbook's §4), or abort the campaign."
    )


def _awaiting_ruling(campaign: dict, applied: list[dict]) -> str:
    """The gate's ask, with each ruling bound it has already waited past (§9.2; §24ae)."""
    proposal = campaign.get("proposal") or {}
    binding = proposal.get("binding") or {}
    overdue = any(
        r["operation"] == ControlOperation.RULING_OVERDUE
        and r["target"] == proposal.get("run_id")
        and r["binding"].get("version") == binding.get("version")
        for r in applied
    )
    late = ", past its ruling bound" if overdue else ""
    return (
        f"The increment gate waits on a ruling for `{binding.get('proposal_id')}` "
        f"v{binding.get('version')}{late}. Rule it, or abort the campaign."
    )
