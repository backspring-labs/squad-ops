"""The plan-review tier: who decides a campaign cycle's plan gate when the campaign declares it
(SIP-0109 §24bj, #1708; the policy ruled by the owner 2026-10-08).

The tier may approve, and nothing else. It approves when every condition holds and escalates
otherwise; it never rejects, returns, or answers a question. It is reached only after plan
validation passed at the gate, the manifest's schema and winnability gates included
(``framing_gate_check``), so its conditions are the rest of §24bj's:

- **no open question** remains once §24ad's answers are applied, and the cycle has a design to read
  (a cycle with no manifest has nothing the tier can establish);
- **the plan's footprint is inside the objective's allowed scope**: the union of its tasks'
  ``expected_artifacts``. A calibration is not held to it: it builds the baseline the scope is read
  against, and its plan names the builder's own notes at the root;
- **the framing ran once**: a framing that plan validation refused and re-rolled escalates.

Pure: it reads the gate's evidence and the campaign's record, never mutable memory (SIP-0110 §7,
§0.8).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from squadops.campaigns.change_request import outside_allowed_scope
from squadops.campaigns.models import CycleKind
from squadops.cycles.implementation_plan import ImplementationPlan

#: The decider a tier approval records (§24bj), in the machine deciders' vocabulary (#812).
GATE_DECIDED_BY_PLAN_REVIEW_TIER = "system:plan_review_tier"


class TierCondition(StrEnum):
    """One condition of §24bj the tier reads, beyond the plan validation that precedes it."""

    NO_OPEN_QUESTION = "no_open_question"
    INSIDE_SCOPE = "inside_scope"
    FRAMED_ONCE = "framed_once"


@dataclass(frozen=True)
class TierCheck:
    """One condition, whether it held, and what it read, in words."""

    condition: TierCondition
    held: bool
    reading: str


@dataclass(frozen=True)
class TierVerdict:
    """Every condition's check, in §24bj's order. The tier approves only when all held."""

    checks: tuple[TierCheck, ...]

    @property
    def approves(self) -> bool:
        return all(c.held for c in self.checks)

    @property
    def failed(self) -> tuple[TierCheck, ...]:
        return tuple(c for c in self.checks if not c.held)

    def notes(self) -> str:
        """The decision's notes: why, not only who (§24bj)."""
        lines = [
            "Plan validation passed at this gate, the manifest's schema and winnability gates "
            "included."
        ]
        lines += [
            f"{c.condition}: {'held' if c.held else 'FAILED'}: {c.reading}" for c in self.checks
        ]
        return "\n".join(lines)


def plan_footprint(plan_yaml: str | None) -> tuple[str, ...]:
    """The plan's footprint: the union of its tasks' ``expected_artifacts``, in first-seen order.
    An absent or unreadable plan has none, so the tier escalates rather than read scope from
    nothing."""
    if not plan_yaml:
        return ()
    try:
        plan = ImplementationPlan.from_yaml(plan_yaml)
    except ValueError:
        return ()
    return tuple(dict.fromkeys(path for task in plan.tasks for path in task.expected_artifacts))


def plan_review_tier(
    *,
    kind: CycleKind,
    open_questions: Sequence[str] | None,
    footprint: Sequence[str],
    allowed_scope: Sequence[str],
    refused_framing_runs: Sequence[str],
    answered_on_record: Mapping[str, str],
) -> TierVerdict:
    """The tier's verdict on one plan gate.

    ``open_questions`` is the design's questions after §24ad's answers and the late answers on
    record, or ``None`` for a cycle with no manifest. ``answered_on_record`` names each decision a
    late answer covered, with the escalation it was recorded against (§24bl).
    ``refused_framing_runs`` are this cycle's earlier framing runs that plan validation refused,
    each one a re-roll."""
    if open_questions is None:
        questions = TierCheck(
            TierCondition.NO_OPEN_QUESTION,
            False,
            "the cycle has no interface manifest, so the tier can establish nothing about its design",
        )
    elif open_questions:
        questions = TierCheck(
            TierCondition.NO_OPEN_QUESTION,
            False,
            f"{len(open_questions)} open: " + "; ".join(open_questions),
        )
    elif answered_on_record:
        questions = TierCheck(
            TierCondition.NO_OPEN_QUESTION,
            True,
            "every question the design asks is answered on record: "
            + ", ".join(f"{d} ({e})" for d, e in sorted(answered_on_record.items())),
        )
    else:
        questions = TierCheck(TierCondition.NO_OPEN_QUESTION, True, "the design asks nothing")

    if kind is CycleKind.CALIBRATION:
        scope = TierCheck(
            TierCondition.INSIDE_SCOPE,
            True,
            "a calibration builds the baseline the scope is read against, and is not held to it",
        )
    elif not footprint:
        scope = TierCheck(
            TierCondition.INSIDE_SCOPE,
            False,
            "the plan names no file, so it has no footprint to read",
        )
    else:
        outside = outside_allowed_scope(footprint, allowed_scope)
        scope = TierCheck(
            TierCondition.INSIDE_SCOPE,
            not outside,
            (
                f"outside ({', '.join(allowed_scope)}): {', '.join(outside)}"
                if outside
                else f"all {len(footprint)} files inside ({', '.join(allowed_scope)})"
            ),
        )

    once = TierCheck(
        TierCondition.FRAMED_ONCE,
        not refused_framing_runs,
        (
            "plan validation refused and re-rolled " + ", ".join(refused_framing_runs)
            if refused_framing_runs
            else "the framing ran once"
        ),
    )
    return TierVerdict((questions, scope, once))
