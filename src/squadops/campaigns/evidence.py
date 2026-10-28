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

from squadops.campaigns.escalation import ANSWERABLE, EscalationState, escalations
from squadops.campaigns.models import CampaignState, ControlOperation, ControlOutcome
from squadops.campaigns.safety_guarantees import GuaranteeStatus, all_intact, safety_guarantees
from squadops.campaigns.scorecard import scorecard_lines

#: Bumped when the package's shape changes; a reader checks it before reading further.
#: 2: each cycle carries its runs' revision forms (#1710).
#: 3: and its runs' lint readings, evidence only (#1937).
#: 5: an increment's outcome section reads the goals its change request named (SIP-0113 §4.5).
#: 6: its quality deltas carry §10y's failing ids, introduced and resolved, where both trees were
#:    read by the evaluator's ``-7`` or later (``failing_moved``); its pages, the finer reading.
PACKAGE_VERSION = 6

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
    #: #1937: per run, the lint reading of the tree its qa task evaluated (``None`` when none).
    lint_findings: tuple = ()


def package(
    campaign: Any,
    log: list,
    launches: list,
    cycles: list[CycleRecords],
    *,
    outcomes: dict | None,
    interventions: dict | None,
) -> dict:
    """The package document, with its identity. ``outcomes`` is SIP-0113's section (version 4,
    #2418): each cycle's scenario results by id, contribution and quality, or ``None`` for a
    campaign with no suite pinned."""
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
                "lint_findings": _plain(c.lint_findings),
                "decision": decisions.get(c.cycle_id),
            }
            for c in cycles
        ],
        "outcomes": outcomes,
        "interventions": interventions,
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
        _work_class_line(c["objective"]),
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
    # #1960: what each increment cost, from the package alone.

    lines += ["", "## Per increment", ""] + scorecard_lines(doc)
    lines += ["", "## Cycles", "", "| cycle | kind | ending | verdict | decided | attribution |"]
    lines.append("|---|---|---|---|---|---|")
    for cyc in doc["cycles"]:
        d = cyc["decision"] or {}
        decided = f"row {d['row']}: {d.get('outcome') or d.get('action')}" if d else "not decided"
        lines.append(
            f"| `{cyc['cycle_id']}` | {cyc['kind']} | {d.get('ending', '—')} | "
            f"{d.get('verdict') or '—'} | {decided} | {_primary(cyc['assessment'])} |"
        )
    lines += ["", "## Outcomes", ""] + _outcome_lines(doc.get("outcomes"))
    lines += ["", "## Safety guarantees", ""] + _guarantee_lines(doc)
    lines += ["", "## Autonomy", ""] + _autonomy_lines(doc)
    lines += ["", "## Escalations", ""] + (
        _escalation_lines(c, rows) or ["- the plan-review tier escalated nothing"]
    )
    asks = _questions(c, rows) + _escalation_asks(c, rows) + _over_bound(doc)
    lines += ["", "## For the owner", ""] + ([f"- {q}" for q in asks] or ["- nothing is waiting"])
    return "\n".join(lines) + "\n"


def _escalations_of(campaign: dict, rows: list[dict]):
    """The plan-review tier's escalations (§24bj, §24bk), read from the package's rows by the same
    projection the gate and the sweep use."""
    from datetime import datetime
    from types import SimpleNamespace

    ops = {
        ControlOperation.ESCALATION_OPENED,
        ControlOperation.ESCALATION_CLOSED,
        ControlOperation.ESCALATION_ANSWERED,
    }
    entries = [
        SimpleNamespace(
            operation=ControlOperation(r["operation"]),
            outcome=ControlOutcome(r["outcome"]),
            binding=r["binding"],
            actor=r["actor"],
            committed_at=datetime.fromisoformat(r["committed_at"]),
        )
        for r in rows
        if r["operation"] in ops
    ]
    return escalations(entries, CampaignState(campaign["state"]))


def _escalation_lines(campaign: dict, rows: list[dict]) -> list[str]:
    """Every escalation and how it ended, kept apart from what was accepted (§24bj): the
    campaign's unresolved work, beside its completed work."""
    lines = []
    for e in _escalations_of(campaign, rows):
        asked = "; ".join(e.questions) or "no question"
        failed = ", ".join(condition for condition, _ in e.failed)
        line = f"- `{e.escalation_id}` on `{e.cycle_id}`: {e.state} ({failed}). Asked: {asked}"
        if e.answers:
            given = "; ".join(f"{d}: {a}" for d, a in e.answers.items())
            # The question carries its own end, often a period: one sentence end, not two (#2305).
            ended = line if line.endswith((".", "?", "!")) else f"{line}."
            line = f"{ended} Answered late by {e.answered_by}: {given}"
        lines.append(line)
    return lines


def _escalation_asks(campaign: dict, rows: list[dict]) -> list[str]:
    """What the owner is asked about the tier's escalations: a pending one is answered at its gate
    before the bound parks it; an expired or cancelled one with no answer can be answered late."""

    asks = []
    for e in _escalations_of(campaign, rows):
        asked = "; ".join(e.questions) or "no question"
        if e.state is EscalationState.PENDING:
            asks.append(
                f"The plan gate on `{e.run_id}` escalated: answer it at the gate before its ruling "
                f"bound parks the cycle. Asked: {asked}"
            )
        elif e.state in ANSWERABLE and not e.answers:
            asks.append(
                f"Escalation `{e.escalation_id}` {e.state} with nobody answering. Answer it late "
                f"with `squadops campaigns answer {campaign['campaign_id']} {e.escalation_id} "
                f'--answer "<decision id>=…" --reason "…"`; a later tier campaign carries it. Asked: {asked}'
            )
    return asks


def _guarantee_lines(doc: dict) -> list[str]:
    """The 2.0 set's seven, read from this package (SIP-0113 §4.6, ruled 2026-10-19; #2418)."""
    readings = safety_guarantees(doc)
    intact = all_intact(readings)
    verdict = {True: "all seven held", False: "**violated**", None: "not all read"}[intact]
    lines = [f"Every safety guarantee intact: {verdict}.", ""]
    for r in readings:
        mark = {
            GuaranteeStatus.HELD: "held",
            GuaranteeStatus.VIOLATED: "**violated**",
            GuaranteeStatus.NOT_READ: "not read",
        }[r.status]
        lines.append(
            f"- {mark}: {r.guarantee}" + (f" ({'; '.join(r.evidence)})" if r.evidence else "")
        )
    return lines


def _autonomy_lines(doc: dict) -> list[str]:
    """AOR's four inputs for this campaign (SIP-0113 §4.6, #2418), each with what it was read
    from. The rate is a reading across campaigns of one work class, never one campaign's."""
    # deferred (pair): squadops.outcomes imports squadops.campaigns at load
    from squadops.outcomes.aor import aor_inputs

    read = aor_inputs(doc)
    counted = {True: "counts as reliable", False: "doesn't count", None: "not yet read"}[
        read.reliable
    ]
    lines = [f"Toward its work class's AOR: {counted}.", ""]
    marks = {True: "yes", False: "**no**", None: "not read"}
    lines += [f"- {name}: {marks[value]} ({why})" for name, value, why in read.inputs]
    return lines


def _work_class_line(objective: dict) -> str:
    """SIP-0113 §4.6 (#2418): the class AOR groups this campaign by, as declared."""
    declared = objective.get("work_class")
    if not declared:
        return "**Work class:** none declared (created before SIP-0113 §4.6)"
    target = objective.get("target_accepted_increments")
    return f"**Work class:** {declared['prd_tier']}, {declared['attendance']}" + (
        f", {target} increments" if target else ""
    )


def _named_goal_lines(cyc: dict) -> list[str]:
    """SIP-0113 §4.5: what became of each goal the increment's request named, by id only."""
    named = cyc.get("named_goals") or {}
    if not named:
        return []
    return ["  - named goals: " + ", ".join(f"{goal} {move}" for goal, move in named.items())]


def _outcome_lines(outcomes: dict | None) -> list[str]:
    """SIP-0113's readings per cycle (#2418), reporting-only: each contribution, its scenarios
    by result, its quality, and what moved against the tree it built on and the baseline. Never
    a scenario's goal or steps: ids and results only."""
    if not outcomes:
        return ["- no held-out suite is pinned on this campaign"]
    if "unreadable" in outcomes:
        return [f"- the outcome records could not be read: {outcomes['unreadable']}"]
    lines = [
        f"Held-out suite `{outcomes['suite_digest'][:16]}`; reporting-only, no decision reads it.",
        "",
    ]
    for cyc in outcomes["cycles"]:
        if not cyc.get("evaluation"):
            lines.append(f"- `{cyc['cycle_id']}`: not evaluated")
            lines += _named_goal_lines(cyc)
            continue
        read = cyc.get("contribution") or {}
        reading = read.get("reading") or f"not read ({read.get('unread_because', 'no reading')})"
        results: dict[str, int] = {}
        for _id, result, reason in cyc["scenarios"]:
            key = f"{result} ({reason})" if reason else result
            results[key] = results.get(key, 0) + 1
        lines.append(
            f"- `{cyc['cycle_id']}`: **{reading}**; "
            + ", ".join(f"{n} {key}" for key, n in sorted(results.items()))
        )
        for moved in ("newly_passing", "regressed", "unverified"):
            if read.get(moved):
                lines.append(f"  - {moved.replace('_', ' ')}: {', '.join(read[moved])}")
        lines += _named_goal_lines(cyc)
        if controls := cyc.get("page_controls"):
            # SIP-0113 §10p ruling 4: a page scenario whose names matched no control.
            lines.append(
                f"  - page scenarios: {controls['control_absent']} of "
                f"{controls['read_in_a_browser']} found no control by any of their names"
            )
        lines.append(
            f"  - quality: {_measure_line(cyc.get('quality'))}; lint: {_lint_line(cyc.get('lint'))}"
        )
        for label, key in (
            ("against the tree it built on", "vs_previous"),
            ("against the baseline", "vs_baseline"),
        ):
            if cyc.get(key):
                lines.append(f"  - {label}: {_moves_line(cyc[key])}")
    return lines


def _measured() -> str:
    # deferred (pair): squadops.scenarios imports squadops.campaigns at load
    from squadops.scenarios.quality import QualityStatus

    return QualityStatus.MEASURED.value


def _measure_line(quality: dict | None) -> str:
    if not quality:
        return "not recorded"
    if quality["status"] != _measured():
        return f"{quality['status']} ({quality.get('reason') or 'no reason'})"
    scored = [p for p in quality["pages"] if not p.get("error")]
    told = f"measured on {len(scored)} of {len(quality['pages'])} pages"
    finer = [p for p in scored if p.get("axe_nodes") is not None]
    if not finer:
        return told
    # SIP-0113 §10y, reporting-only: Lighthouse's raw best practices, read with the sandbox's
    # plain HTTP, beside the app's own, without the environment's audits.
    raw = [p["lighthouse"].get("best_practices") for p in finer]
    app = [p.get("best_practices_app") for p in finer]
    return (
        f"{told}; best practices raw {_range(raw)}, the app's without the environment's audits "
        f"{_range(app)}"
    )


def _range(values: list) -> str:
    known = [v for v in values if v is not None]
    if not known:
        return "not read"
    low, high = min(known), max(known)
    told = f"{low:g}" if low == high else f"{low:g} to {high:g}"
    return told + (f" ({len(values) - len(known)} not read)" if len(known) < len(values) else "")


def _lint_line(lint: dict | None) -> str:
    if not lint:
        return "not recorded"
    if lint["status"] != _measured():
        return f"{lint['status']} ({lint.get('reason') or 'no reason'})"
    reading = lint["reading"]
    missing = (
        f", {', '.join(reading['unavailable'])} unavailable" if reading.get("unavailable") else ""
    )
    return f"{reading['total']} findings{missing}"


def _moves_line(deltas: dict) -> str:
    if "unread_because" in deltas:
        return f"not read ({deltas['unread_because']})"
    moves = [
        f"{measure}{f' on {page}' if page else ''} {delta:+g}"
        for measure, page, _before, _after, delta in deltas["moved"]
    ]
    # SIP-0113 §10y: each failing-id list that moved, by the ids introduced (+) and resolved (-).
    moves += [
        f"{measure} on {page} "
        + " ".join([*(f"+{i}" for i in introduced), *(f"-{i}" for i in resolved)])
        for measure, page, introduced, resolved in deltas.get("failing_moved", ())
    ]
    gaps = [f"{what}: {why}" for what, why in deltas["not_compared"]]
    told = "; ".join(moves) or f"nothing moved ({deltas['unmoved']} compared)"
    return told + (f"; not compared: {'; '.join(gaps)}" if gaps else "")


def _kb(size: int) -> str:
    return f"{size / 1024:.0f} KB"


def _accepted(doc: dict) -> list[str]:
    """Each promotion, with what it shipped: the criteria it froze (the change request's own
    statements), and any it retired. A promotion that froze a criterion without its statement
    (an accepted repair's, before #2595) says so: the record is what it is, and a package that
    refuses it is never written."""
    kinds = {cyc["cycle_id"]: cyc["kind"] for cyc in doc["cycles"]}
    lines = []
    for r in doc["control_log"]:
        if r["outcome"] != ControlOutcome.APPLIED:
            continue
        b = r["binding"]
        if r["operation"] == ControlOperation.BRANCH_REBASED:
            lines.append(_rebased(b))
            continue
        if r["operation"] != ControlOperation.PROMOTE:
            continue
        if b.get("calibration_record_id"):
            # §24cc: a repository-backed calibration is a record of the product's own commit.
            lines.append(
                f"- calibration record `{b['calibration_record_id']}`: commit "
                f"`{b['commit'][:12]}`, revision {b['development_configuration_revision']}, "
                f"tree `{b['identity'][:12]}`"
            )
            continue
        # §24bv point 2: an increment on the campaign branch is its captured commit there.
        shipped = (
            f"commit `{b['commit'][:12]}` on the campaign branch"
            if b.get("commit")
            else f"{b.get('files', '?')} files"
        )
        lines.append(
            f"- {kinds.get(b['cycle_id'], 'cycle')} `{b['cycle_id']}`: tree `{b['identity'][:12]}`, "
            f"{shipped}"
        )
        lines += [
            f"  - froze {f['criterion_id']}: {f.get('statement') or 'statement not recorded'}"
            for f in b.get("frozen_criteria") or ()
        ]
        if b.get("retired_criteria"):
            lines.append(f"  - retired {', '.join(b['retired_criteria'])}")
    return lines


def _rebased(b: dict) -> str:
    """§24bv point 4: the campaign branch rebased when upstream moved, with what it superseded
    and the frozen criteria its verification left unrun (§24cm)."""
    line = (
        f"- rebased onto `{b['base'][:12]}` (revision {b['development_configuration_revision']}): "
        f"head `{b['head_before'][:12]}` → `{b['commit'][:12]}`, tree `{b['identity'][:12]}`; "
        f"{b.get('verification_summary') or b.get('verification')}"
    )
    if b.get("superseded_launch_id"):
        line += f"; superseded {b['superseded_launch_id']}, abandoned as upstream_moved"
    if b.get("frozen_criteria_unrun"):
        line += f"; frozen criteria not run: {', '.join(b['frozen_criteria_unrun'])}"
    return line


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


def _escalation_question(last: dict) -> str:
    """What the owner is asked about an escalation, by the row that escalated it. A launch the
    cycle-create path refused (#1971) or the box kept refusing (§9.3) resumes without an action:
    the launch is still pending, and an action would write a second one."""
    binding = last["binding"]
    if last["operation"] == ControlOperation.LAUNCH_REFUSED:
        return (
            f"The campaign is escalated: the cycle-create path refused launch "
            f"`{binding.get('launch_id')}` ({binding.get('refusal')}). Fix what it names and "
            "resume without an action to retry it, or abort."
        )
    if last["operation"] == ControlOperation.LAUNCH_BLOCKED:
        return (
            f"The campaign is escalated: the box refused launch `{binding.get('launch_id')}` "
            f"{binding.get('attempt')} times ({binding.get('refusal')}). Resume without an "
            "action to retry it, or abort."
        )
    why = binding.get("unbuilt") or f"§10 row {binding.get('row')}"
    return f"The campaign is escalated ({why}). Resume it naming an action, or abort it."


def _questions(campaign: dict, rows: list[dict]) -> list[str]:
    applied = [r for r in rows if r["outcome"] == ControlOutcome.APPLIED]
    last = applied[-1] if applied else None
    asks = []
    if campaign["state"] == CampaignState.ESCALATED and last is not None:
        asks.append(_escalation_question(last))
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
