"""What a fresh proposal is shown of the proposals its campaign never approved (#2593).

A revision is shown the supervisor's note and the version it revises (SIP-0109 §9.2). A rejection
ends its cycle instead, and the fresh proposal after it (row 6) was shown nothing: the 2.4
window's campaign 4 proposed one rejected change in four of its five proposals, and
``max_rejected_proposals_in_row`` paused it twice. So every proposal the campaign ruled on and
never approved is shown by its last ruling: the reason the supervisor recorded, and what it
proposed, from its own change request.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from squadops.campaigns.change_request import ChangeRequest
from squadops.campaigns.models import ControlLogEntry, ControlOperation, ControlOutcome
from squadops.cycles.models import APPROVING_DECISIONS, GateDecisionValue

#: How many are shown, the most recent: every one rides every later proposal's prompt, and a
#: long campaign's oldest rulings were made on an application long since changed. The same
#: bound as the qa authors' proposed behaviours (#1884).
MOST_RECENT = 10

#: How each ruling a proposal can end on reads to the next proposal.
_RULED = {
    GateDecisionValue.REJECTED.value: "rejected",
    GateDecisionValue.RETURNED_FOR_REVISION.value: "returned for revision and never approved",
}

#: What a returning ruling records of what went wrong (``gate.return_classification``).
_CLASSIFIED = ("classification", "classification_rationale")


def unapproved_rulings(log: Iterable[ControlLogEntry]) -> list[ControlLogEntry]:
    """Each proposal's last applied ruling, for every proposal the campaign never approved, in
    the order those rulings were made, the ``MOST_RECENT`` of them. A proposal approved at any
    version is left out: its change is built, or was, and its earlier returns are spent. A
    refused row rules nothing."""
    last: dict[str, tuple[int, ControlLogEntry]] = {}
    approved: set[str] = set()
    for n, entry in enumerate(log):
        if (
            entry.operation is not ControlOperation.RULE
            or entry.outcome is not ControlOutcome.APPLIED
        ):
            continue
        proposal_id = str(entry.binding.get("proposal_id") or "")
        if entry.binding.get("decision") in APPROVING_DECISIONS:
            approved.add(proposal_id)
        last[proposal_id] = (n, entry)
    ruled = [
        entry
        for pid, (_, entry) in sorted(last.items(), key=lambda kv: kv[1][0])
        if pid not in approved
    ]
    return ruled[-MOST_RECENT:]


def unapproved_proposal(
    entry: ControlLogEntry, request: ChangeRequest | None, *, current_tree: str
) -> dict[str, Any]:
    """One unapproved proposal as the launch block carries it. ``request`` is its change request,
    or ``None`` when its run stored none: the ruling is shown without what it proposed.
    ``current_tree`` is the accepted tree the new proposal builds on: a ruling made on an older
    one was made on an application that has changed since."""
    shown: dict[str, Any] = {
        "proposal_id": entry.binding.get("proposal_id"),
        "version": entry.binding.get("version"),
        "decision": entry.binding.get("decision"),
        "reason": entry.reason,
        "ruled_on_current_application": entry.binding.get("baseline_tree") == current_tree,
        # §24bi: a return names what went wrong, as a class or as unclassified with a rationale.
        **{k: entry.binding[k] for k in _CLASSIFIED if entry.binding.get(k)},
    }
    if request is not None:
        shown["prd_delta"] = [
            {"id": s.id, "op": s.op.value, "text": s.text} for s in request.prd_delta
        ]
        shown["criteria"] = [{"id": c.id, "statement": c.statement} for c in request.criteria]
    return shown


def _one_line(text: Any) -> str:
    """A recorded note on one line, so a reason written in paragraphs stays inside its entry."""
    return " ".join(str(text or "").split())


def unapproved_lines(entries: Sequence[Mapping[str, Any]]) -> str:
    """The section's index: data only, one entry per proposal; the prose is the asset's (#448)."""
    lines = []
    for e in entries:
        ruled = _RULED.get(str(e.get("decision")), str(e.get("decision")))
        when = (
            "on the application as it is now"
            if e.get("ruled_on_current_application")
            else "on an earlier application"
        )
        lines.append(
            f"- `{e.get('proposal_id')}` version {e.get('version')}, {ruled}, ruled {when}. "
            f"The supervisor's reason: {_one_line(e.get('reason')) or 'none recorded'}"
        )
        if e.get("classification"):
            why = _one_line(e.get("classification_rationale"))
            lines.append(f"  - classified `{e['classification']}`" + (f": {why}" if why else ""))
        for s in e.get("prd_delta") or ():
            lines.append(
                f"  - it proposed PRD section `{s['id']}` ({s['op']}): {_one_line(s['text'])}"
            )
        for c in e.get("criteria") or ():
            lines.append(f"  - its criterion {c['id']}: {_one_line(c['statement'])}")
    return "\n".join(lines)
