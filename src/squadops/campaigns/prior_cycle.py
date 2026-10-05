"""The prior-cycle brief (#1692; SIP-0109 §10a).

A retry or a repair is launched to recover from a failed cycle of the same increment. Without
this, it starts as blind as the cycle that failed. The brief is that cycle's own record, carried
to the next: derived from its typed assessment only (SIP-0096's integrity rule applied to what the
next cycle reads) — never an LLM's narrative of what went wrong — and rendered through a managed
prompt asset. It is an input to the next cycle's authoring, never to the continuation decision.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from squadops.capabilities.anchored_edits import verbatim_block
from squadops.cycles.cycle_assessment import CycleAssessment, IndicatorState
from squadops.cycles.run_loop_summary import RunLoopSummary
from squadops.cycles.verification_integrity import FailedCheck

_UNASKABLE = "unaskable: "

#: A failure's reason is shown up to this many characters, and says when it was cut: a test
#: runner's output can be the whole log.
REASON_LIMIT = 1500

#: What the next cycle is told, by indicator, in this order.
BRIEF_INDICATORS = (
    "verdict",
    "failed_checks",
    "unverified_by_reason",
    "criteria_coverage",
    "correction_movements",
    "refunded_rounds",
)


#: A run's task id carries its task type after the step index (``task-run_x-m007-qa.test``); a
#: correction task's carries the round index right after the run id (``adapters/cycles/
#: correction_ids.py``: ``repair-run_x-00-s00-qa.test_repair``, older ids without ``-sNN``).
_TASK_TYPE = re.compile(r"^task-run_[0-9a-f]+-m?\d+-(?P<type>.+)$")
_ROUND = re.compile(r"^[a-z]+-run_[0-9a-f]+-(?P<round>\d{2})(?:-s\d{2})?-")


def correction_rounds(summaries: Iterable[RunLoopSummary]) -> list[dict[str, Any]]:
    """The failed cycle's correction chain, round by round (#1692's remainder: "what each round
    tried, and the patches it refused"). From each run's loop summary (SIP-0108 §4.1), never a
    narrative: the task that failed and the checks that failed it; each repair of that round,
    whether it was kept, what it edited and, when refused, why; how the task moved after."""
    rounds: list[dict[str, Any]] = []
    for summary in summaries:
        repairs: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for form in summary.revision_forms or ():
            found = _ROUND.match(str(form.get("task_id") or ""))
            if found is None:
                continue
            repairs[int(found["round"])].append(
                {
                    "task_type": form.get("task_type"),
                    "kept": bool(form.get("accepted")),
                    "edited": list(form.get("edited") or ()) + list(form.get("new_files") or ()),
                    "refused_because": form.get("failure_reason") or None,
                }
            )
        moved = {(m.task_id, m.round_index): m.movement for m in summary.movements}
        for failure in summary.round_failures or ():
            typed = _TASK_TYPE.match(failure.task_id)
            rounds.append(
                {
                    "round": failure.round_index,
                    "task_type": typed["type"] if typed else failure.task_id,
                    "failed_checks": list(failure.failed_checks),
                    "category": failure.category,
                    "repairs": repairs.get(failure.round_index, []),
                    "movement": moved.get((failure.task_id, failure.round_index)),
                }
            )
    return rounds


def prior_cycle_brief(
    assessment: CycleAssessment,
    failures: Iterable[FailedCheck] = (),
    loop_summaries: Iterable[RunLoopSummary] = (),
) -> dict[str, Any]:
    """The failed cycle's brief, as plain data for its successor's launch: each indicator it
    observed; ``unaskable: <reason>`` for one it could not ask, so an absence is never read as
    "nothing failed"; the cause its attribution names; and why each failed check failed, from
    the runs' stored verification summaries (``failed_detail``, #500) — the latest run's reason
    for a check, and only for a check the assessment counts as failed; and the correction chain
    round by round, from the runs' loop summaries (``correction_rounds``)."""
    brief: dict[str, Any] = {"cycle_id": assessment.cycle_id}
    for name in BRIEF_INDICATORS:
        try:
            indicator = assessment.indicator(name)
        except KeyError:
            continue
        if indicator.state is IndicatorState.OBSERVED:
            brief[name] = indicator.value
        elif indicator.state is IndicatorState.ASKED_NONE:
            brief[name] = []  # asked, and there were none: shown as "none", never dropped
        elif indicator.state is IndicatorState.UNASKABLE:
            brief[name] = f"{_UNASKABLE}{indicator.reason}"
    reading = assessment.attribution
    if reading.state is IndicatorState.OBSERVED and reading.attribution is not None:
        brief["primary_cause"] = str(reading.attribution.primary)
    failed = set(brief.get("failed_checks") or ())
    why = {f.check_id: f for f in failures if f.check_id in failed}
    if why:
        brief["why_failed"] = [
            {
                "check_id": f.check_id,
                "reason": _bounded(f.reason),
                "contested": f.contested is not None,
            }
            for f in why.values()
        ]
    summaries = list(loop_summaries)
    rounds = correction_rounds(summaries)
    if rounds:
        brief["correction_rounds"] = rounds
    ended = [s.terminal.termination_reason for s in summaries if s.terminal is not None]
    if any(ended):
        brief["correction_ended"] = next(r for r in reversed(ended) if r)
    return brief


def _bounded(reason: str) -> str:
    reason = str(reason or "").strip()
    if len(reason) <= REASON_LIMIT:
        return reason
    return f"{reason[:REASON_LIMIT]}\n… (cut at {REASON_LIMIT} of {len(reason)} characters)"


def brief_lines(brief: Any) -> str:
    """The brief as the lines its appendix shows, or ``""`` when there is none."""
    if not isinstance(brief, dict) or not brief.get("cycle_id"):
        return ""
    lines = [f"- the cycle: `{brief['cycle_id']}`"]
    for name in (*BRIEF_INDICATORS, "primary_cause"):
        if name in brief:
            lines.append(f"- {name.replace('_', ' ')}: {_value(brief[name])}")
    why = brief.get("why_failed") or ()
    if why:
        lines.append("\nWhy each failed, as its run recorded it:")
    for failure in why:
        lines.append("")
        lines.append(verbatim_block(failure["check_id"], failure.get("reason") or "(no reason)"))
        if failure.get("contested"):
            lines.append(f"Its producer disputed `{failure['check_id']}`.")
    rounds = brief.get("correction_rounds") or ()
    if rounds:
        lines.append("\nWhat each correction round tried:")
    for r in rounds:
        lines.append(_round_line(r))
    if brief.get("correction_ended"):
        lines.append(f"- the chain ended: `{brief['correction_ended']}`")
    return "\n".join(lines)


def _round_line(r: dict[str, Any]) -> str:
    checks = _value(r.get("failed_checks") or [])
    line = f"- round {r['round']}: `{r['task_type']}` failed {checks}"
    for repair in r.get("repairs") or ():
        edited = _value(repair.get("edited") or [])
        if repair.get("kept"):
            line += f"; `{repair['task_type']}` edited {edited}, and it was kept"
        else:
            why = repair.get("refused_because") or "no reason recorded"
            line += f"; `{repair['task_type']}` edited {edited}, and it was refused ({why})"
    if r.get("movement"):
        line += f"; afterwards: `{r['movement']}`"
    return line


def _value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(f"`{v}`" for v in value) if value else "none"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_value(v)}" for k, v in value.items()) if value else "none"
    if str(value).startswith(_UNASKABLE):
        # The reader is a model, not an assessor: say what the absence means.
        return f"not recorded ({str(value)[len(_UNASKABLE) :]})"
    return f"`{value}`"
