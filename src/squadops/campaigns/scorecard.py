"""The per-increment scorecard (#1960): what an increment cost, from the evidence package alone.

An increment is not one cycle. It is its proposal run and any revision rounds, its framing and
implementation, and any repair or retry cycles, up to its promotion or abandonment. The Nostromo
IDEA's product and framework measures are read at that unit, and so is the comparison of a replay
with its original (#1959): the same arithmetic on both sides.

Reporting only: it changes no verdict, decision or prompt, and no model writes it. Every number is
derived from records the package already holds, the control log's ``committed_at`` and bindings,
the launches, and each cycle's assessment (its efficiency and coordination indicators).

**What the first version does not split.** Waiting is elapsed time minus the cycles' run wall
clock: the ruling, the plan gate, the box and dispatch together. Naming the box's share needs the
run to persist its ``waited_s`` (``run_admission.py``), and per-run starts are not in the package.
Test-file churn and the correction rounds failed by test checks need the vault and the correction
ledger, not the package, so they are not here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from squadops.campaigns.continuation import PendingAction
from squadops.campaigns.models import ControlOperation, CycleKind
from squadops.cycles.cycle_assessment import IndicatorState

#: Task types whose tokens are verification's cost (SIP-Verification-Yield §17).
_VERIFICATION_PREFIX = "qa."


def _indicator(assessment: Mapping | None, section: str, name: str) -> Any:
    for ind in (assessment or {}).get(section) or ():
        if ind.get("name") == name and ind.get("state") == IndicatorState.OBSERVED:
            return ind.get("value")
    return None


def _tokens(entry: Mapping) -> int:
    return (
        int(entry.get("prompt", 0))
        + int(entry.get("completion", 0))
        + int(entry.get("reasoning", 0))
    )


def cycle_scorecard(assessment: Mapping | None) -> dict[str, Any]:
    """One cycle's share: run wall clock, tokens by task type, LLM calls and correction rounds.
    A replay outside any campaign (#1959) is read with this alone."""
    by_type = _indicator(assessment, "efficiency", "tokens_by_task_type") or {}
    calls = _indicator(assessment, "efficiency", "llm_calls") or {}
    return {
        "executing_s": float(_indicator(assessment, "efficiency", "wall_clock_seconds") or 0.0),
        "tokens_by_task_type": {t: _tokens(v) for t, v in by_type.items()},
        "llm_calls": int(calls.get("calls", 0)),
        "correction_rounds": int(
            next(
                (
                    i.get("value") or 0
                    for i in (assessment or {}).get("coordination") or ()
                    if i.get("name") == "correction_rounds"
                ),
                0,
            )
        ),
    }


def _at(row: Mapping) -> datetime:
    return datetime.fromisoformat(str(row["committed_at"]).replace("Z", "+00:00"))


def _merge(cards: Iterable[Mapping]) -> dict[str, Any]:
    total: dict[str, Any] = {
        "executing_s": 0.0,
        "tokens_by_task_type": {},
        "llm_calls": 0,
        "correction_rounds": 0,
    }
    for c in cards:
        total["executing_s"] += c["executing_s"]
        total["llm_calls"] += c["llm_calls"]
        total["correction_rounds"] += c["correction_rounds"]
        for t, n in c["tokens_by_task_type"].items():
            total["tokens_by_task_type"][t] = total["tokens_by_task_type"].get(t, 0) + n
    return total


def brief_recurrence(doc: Mapping, cycle_ids: Iterable[str]) -> list[dict[str, Any]]:
    """#1692's recurrence measure: for each recovery cycle shown a prior-cycle brief, which of
    the checks the brief listed as failed failed again, and which cleared. ``unread`` when the
    recovery cycle's own failed checks were not observed: an absence is never read as cleared."""
    launches = {la["cycle_id"]: la for la in doc["launches"]}
    assessments = {c["cycle_id"]: c.get("assessment") for c in doc["cycles"]}
    out = []
    for cycle_id in cycle_ids:
        block = (
            (((launches.get(cycle_id) or {}).get("cycle_request") or {}).get("body") or {})
            .get("execution_overrides", {})
            .get("campaign_proposal", {})
        )
        shown = (block.get("prior_cycle") or {}).get("failed_checks")
        if not isinstance(shown, list) or not shown:
            continue
        own = _indicator(assessments.get(cycle_id), "quality", "failed_checks")
        if not isinstance(own, list):
            out.append({"cycle_id": cycle_id, "shown": shown, "unread": True})
            continue
        out.append(
            {
                "cycle_id": cycle_id,
                "shown": shown,
                "recurred": [c for c in shown if c in own],
                "cleared": [c for c in shown if c not in own],
            }
        )
    return out


def increment_scorecards(doc: Mapping) -> list[dict[str, Any]]:
    """One row per increment launch, in launch order, from the package document."""
    log = list(doc["control_log"])
    launches = sorted(doc["launches"], key=lambda launch: str(launch.get("created_at")))
    assessments = {c["cycle_id"]: c.get("assessment") for c in doc["cycles"]}
    launched_at = {
        r["target"]: _at(r) for r in log if r["operation"] == ControlOperation.MARK_LAUNCHED
    }
    rows = []
    increments = [la for la in launches if la.get("cycle_kind") == CycleKind.INCREMENT]
    for n, launch in enumerate(increments, start=1):
        later = increments[n] if n < len(increments) else None
        # The increment's own cycle, then any repair or retry it launched before the next one.
        cycles = [launch["cycle_id"]] + [
            la["cycle_id"]
            for la in launches
            if la.get("cycle_kind") in (CycleKind.REPAIR, CycleKind.RETRY)
            and str(la.get("created_at")) > str(launch.get("created_at"))
            and (later is None or str(la.get("created_at")) < str(later.get("created_at")))
        ]
        proposal_id = (
            (
                ((launch.get("cycle_request") or {}).get("body") or {}).get("execution_overrides")
                or {}
            )
            .get("campaign_proposal", {})
            .get("proposal_id")
        )
        rulings = [
            (r["binding"].get("version"), r["binding"].get("decision"))
            for r in log
            if r["operation"] == ControlOperation.RULE
            and r["binding"].get("proposal_id") == proposal_id
        ]
        promote = next(
            (
                r
                for r in log
                if r["operation"] == ControlOperation.PROMOTE and r.get("target") in cycles
            ),
            None,
        )
        decided = [
            r
            for r in log
            if r["operation"] in (ControlOperation.DECIDE, ControlOperation.PROMOTE)
            and r.get("target") in cycles
        ]
        abandoned = any(
            r["binding"].get("action") == PendingAction.ABANDON_AND_PROPOSE for r in decided
        )
        start = launched_at.get(launch["launch_id"])
        end = max((_at(r) for r in decided), default=None)
        card = _merge(cycle_scorecard(assessments.get(c)) for c in cycles)
        tokens = sum(card["tokens_by_task_type"].values())
        verification = sum(
            v for t, v in card["tokens_by_task_type"].items() if t.startswith(_VERIFICATION_PREFIX)
        )
        by_role: dict[str, int] = {}
        for t, v in card["tokens_by_task_type"].items():
            by_role[t.split(".")[0]] = by_role.get(t.split(".")[0], 0) + v
        elapsed = (end - start).total_seconds() if start and end else None
        rows.append(
            {
                "increment": n,
                "cycle_id": launch["cycle_id"],
                "proposal_id": proposal_id,
                "outcome": "accepted"
                if promote
                else ("abandoned" if abandoned else ("rejected" if decided else "open")),
                "elapsed_s": elapsed,
                "executing_s": card["executing_s"],
                "waiting_s": max(0.0, elapsed - card["executing_s"])
                if elapsed is not None
                else None,
                "tokens": tokens,
                "tokens_by_role": by_role,
                "verification_tokens": verification,
                "llm_calls": card["llm_calls"],
                "correction_rounds": card["correction_rounds"],
                "proposal_rounds": len(rulings),
                "rulings": rulings,
                "repair_retry_cycles": len(cycles) - 1,
                "brief_recurrence": brief_recurrence(doc, cycles[1:]),
                "criteria_added": len(
                    (promote or {}).get("binding", {}).get("frozen_criteria") or []
                ),
            }
        )
    return rows


def _min(seconds: float | None) -> str:
    return "—" if seconds is None else f"{seconds / 60:.0f} min"


def scorecard_lines(doc: Mapping) -> list[str]:
    """The digest's table: one row per increment."""
    rows = increment_scorecards(doc)
    if not rows:
        return ["- no increment was launched"]
    out = [
        "| # | cycle | outcome | elapsed | executing | waiting | tokens | qa share | LLM calls "
        "| proposal rounds | repair/retry | criteria added |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        share = f"{100 * r['verification_tokens'] / r['tokens']:.0f}%" if r["tokens"] else "—"
        out.append(
            f"| {r['increment']} | `{r['cycle_id']}` | {r['outcome']} | {_min(r['elapsed_s'])} | "
            f"{_min(r['executing_s'])} | {_min(r['waiting_s'])} | {r['tokens']:,} | {share} | "
            f"{r['llm_calls']} | {r['proposal_rounds']} | {r['repair_retry_cycles']} | "
            f"{r['criteria_added']} |"
        )
    out.append("")
    out.append(
        "Waiting is elapsed time minus the cycles' run wall clock (the ruling, the plan gate, "
        "the box and dispatch together)."
    )
    shown = [(r["increment"], b) for r in rows for b in r["brief_recurrence"]]
    if shown:
        out.append("")
        out.append(
            "A recovery cycle's brief (#1692): the checks it was shown failed, and after it:"
        )
        for n, b in shown:
            if b.get("unread"):
                out.append(
                    f"- increment {n}, `{b['cycle_id']}`: its own failed checks were not recorded"
                )
            else:
                out.append(
                    f"- increment {n}, `{b['cycle_id']}`: recurred {len(b['recurred'])} "
                    f"({', '.join(b['recurred']) or 'none'}), cleared {len(b['cleared'])} of "
                    f"{len(b['shown'])}"
                )
    return out
