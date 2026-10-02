"""The prior-cycle brief (#1692; SIP-0109 §10a).

A retry or a repair is launched to recover from a failed cycle of the same increment. Without
this, it starts as blind as the cycle that failed. The brief is that cycle's own record, carried
to the next: derived from its typed assessment only (SIP-0096's integrity rule applied to what the
next cycle reads) — never an LLM's narrative of what went wrong — and rendered through a managed
prompt asset. It is an input to the next cycle's authoring, never to the continuation decision.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from squadops.capabilities.anchored_edits import verbatim_block
from squadops.cycles.cycle_assessment import CycleAssessment, IndicatorState
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


def prior_cycle_brief(
    assessment: CycleAssessment, failures: Iterable[FailedCheck] = ()
) -> dict[str, Any]:
    """The failed cycle's brief, as plain data for its successor's launch: each indicator it
    observed; ``unaskable: <reason>`` for one it could not ask, so an absence is never read as
    "nothing failed"; the cause its attribution names; and why each failed check failed, from
    the runs' stored verification summaries (``failed_detail``, #500) — the latest run's reason
    for a check, and only for a check the assessment counts as failed."""
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
    return "\n".join(lines)


def _value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(f"`{v}`" for v in value) if value else "none"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_value(v)}" for k, v in value.items()) if value else "none"
    if str(value).startswith(_UNASKABLE):
        # The reader is a model, not an assessor: say what the absence means.
        return f"not recorded ({str(value)[len(_UNASKABLE) :]})"
    return f"`{value}`"
