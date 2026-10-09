"""The plan-review tier's escalation queue (SIP-0109 §24bj, §24bk; #1708).

An escalation is opened when a tier campaign's plan gate is not approved by the tier, and it ends
exactly once: ``resolved`` (a person decided the gate before the bound), ``expired`` (the bound
passed with it pending, so its cycle is parked), ``superseded`` (its gate stopped waiting without a
person's decision, as when a revision re-framed the cycle), or ``cancelled`` (its campaign ended
while it was pending).

The queue is the campaign's control log: an ``escalation_opened`` row keyed by the escalation's
identity, and one ``escalation_closed`` row whose every ending shares a key, so a second ending of
one escalation is refused as a conflicting key, recorded, and never applied. Both are records: the
campaign holds where it is. ``cancelled`` is read, not written: the campaign's own terminal row is
its record. Pure, so the gate and the sweep write exactly what this decides.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from squadops.campaigns.gate import EXECUTOR_ROLE, SWEEP_ROLE
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
)
from squadops.campaigns.plan_review_tier import TierVerdict


class LogRow(Protocol):
    """What the projection reads of a control-log row: a ``ControlLogEntry``, or the package's
    plain record of one read back for the digest."""

    @property
    def operation(self) -> ControlOperation: ...
    @property
    def outcome(self) -> ControlOutcome: ...
    @property
    def binding(self) -> dict: ...
    @property
    def actor(self) -> str: ...
    @property
    def committed_at(self) -> datetime: ...


class EscalationState(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class EscalationIdentity:
    """What one escalation is about (§24bj): its campaign, cycle, run and gate, the proposal and
    version it builds (none for a calibration), the accepted baseline it builds on, and the plan
    it read (its manifest's and its implementation plan's content hash)."""

    campaign_id: str
    cycle_id: str
    run_id: str
    gate_name: str
    proposal_id: str | None
    proposal_version: int | None
    baseline: str | None
    plan_identity: str

    @property
    def escalation_id(self) -> str:
        digest = hashlib.sha256(
            json.dumps(self.__dict__, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return f"esc_{digest[:12]}"


def plan_identity(manifest: str | None, plan_yaml: str | None) -> str:
    """The content hash of the design the tier read: a changed plan is a different escalation."""
    return hashlib.sha256(json.dumps([manifest or "", plan_yaml or ""]).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Escalation:
    """One escalation, as the control log holds it."""

    escalation_id: str
    run_id: str
    cycle_id: str
    gate_name: str
    opened_at: datetime
    failed: tuple[tuple[str, str], ...]
    questions: tuple[str, ...]
    state: EscalationState
    #: The open decisions' ids, matched by a later gate's question (§24bl); empty on an
    #: escalation opened before they were recorded.
    decision_ids: tuple[str, ...] = ()
    closed_by: str | None = None
    closed_at: datetime | None = None
    #: The late answer (§24bj, §24bm): recorded against an expired or cancelled escalation, one
    #: answer per decision it names, never one text for all of them.
    answers: Mapping[str, str] = field(default_factory=dict)
    answered_by: str | None = None
    answered_at: datetime | None = None

    def question_of(self, decision_id: str) -> str | None:
        """The question this escalation recorded for ``decision_id``, or ``None``."""
        for d, q in zip(self.decision_ids, self.questions, strict=False):
            if d == decision_id:
                return q
        return None


@dataclass(frozen=True)
class RecordedAnswer:
    """One decision's late answer, as a later proposal launch and plan gate read it (§24bm): the
    decision and the question it answered, the answer, by whom, when, and the escalation it was
    recorded against."""

    decision_id: str
    question: str
    answer: str
    answered_by: str
    answered_at: datetime
    escalation_id: str


@dataclass(frozen=True)
class RunAtGate:
    """What the sweep read of an escalation's run: whether it still waits at the gate, and the
    person's decision on that gate, if one was recorded."""

    waiting: bool
    decided_by: str | None


def opening_transition(
    identity: EscalationIdentity,
    verdict: TierVerdict,
    decisions: Sequence[tuple[str, str]],
    opened_at: datetime,
) -> CampaignTransition:
    """The ``escalation_opened`` row the gate writes when the tier cannot approve (§24bj), with
    the design's open decisions as ``(id, question)``. Keyed by the identity, so re-entering the
    gate after a restart replays it."""
    failed = [{"condition": str(c.condition), "reading": c.reading} for c in verdict.failed]
    return CampaignTransition(
        operation=ControlOperation.ESCALATION_OPENED,
        actor="squadops",
        actor_role=EXECUTOR_ROLE,
        reason="the plan-review tier could not approve this plan gate: "
        + "; ".join(f"{f['condition']}: {f['reading']}" for f in failed),
        idempotency_key=f"escalation:{identity.escalation_id}",
        next_state=None,
        target=identity.run_id,
        binding={
            "escalation_id": identity.escalation_id,
            "identity": dict(identity.__dict__),
            "failed": failed,
            "questions": [question for _id, question in decisions],
            "decision_ids": [decision_id for decision_id, _q in decisions],
            "opened_at": opened_at.isoformat(),
        },
    )


def escalations(log: Sequence[LogRow], campaign_state: CampaignState) -> list[Escalation]:
    """Every escalation the log holds, in opening order, each in its state. One still open when
    its campaign completed reads ``cancelled``: the campaign's terminal row is its record."""
    applied = [e for e in log if e.outcome is ControlOutcome.APPLIED]
    closed = {
        e.binding["escalation_id"]: e
        for e in applied
        if e.operation is ControlOperation.ESCALATION_CLOSED
    }
    answered = {
        e.binding["escalation_id"]: e
        for e in applied
        if e.operation is ControlOperation.ESCALATION_ANSWERED
    }
    out = []
    for e in applied:
        if e.operation is not ControlOperation.ESCALATION_OPENED:
            continue
        b = e.binding
        ending = closed.get(b["escalation_id"])
        if ending is not None:
            state = EscalationState(ending.binding["state"])
        elif campaign_state is CampaignState.COMPLETED:
            state = EscalationState.CANCELLED
        else:
            state = EscalationState.PENDING
        out.append(
            Escalation(
                escalation_id=b["escalation_id"],
                run_id=b["identity"]["run_id"],
                cycle_id=b["identity"]["cycle_id"],
                gate_name=b["identity"]["gate_name"],
                opened_at=datetime.fromisoformat(b["opened_at"]),
                failed=tuple((f["condition"], f["reading"]) for f in b["failed"]),
                questions=tuple(b["questions"]),
                state=state,
                decision_ids=tuple(b.get("decision_ids") or ()),
                closed_by=ending.actor if ending is not None else None,
                closed_at=ending.committed_at if ending is not None else None,
                **_answer_of(answered.get(b["escalation_id"])),
            )
        )
    return out


def _answer_of(row) -> dict:
    if row is None:
        return {}
    return {
        "answers": dict(row.binding.get("answers") or {}),
        "answered_by": row.actor,
        "answered_at": row.committed_at,
    }


def _closing(escalation: Escalation, state: EscalationState, actor: str, reason: str):
    return CampaignTransition(
        operation=ControlOperation.ESCALATION_CLOSED,
        actor=actor,
        actor_role=SWEEP_ROLE,
        reason=reason,
        # One key for every ending: a second ending of one escalation is a conflicting key,
        # refused and recorded, so it ends exactly once.
        idempotency_key=f"escalation_closed:{escalation.escalation_id}",
        next_state=None,
        target=escalation.run_id,
        binding={"escalation_id": escalation.escalation_id, "state": str(state)},
    )


def closing_transitions(
    campaign: Campaign,
    log: Sequence[ControlLogEntry],
    runs: Mapping[str, RunAtGate],
    now: datetime,
) -> list[CampaignTransition]:
    """Each pending escalation's ending at ``now``, read against its run (§24bj, §24bk):

    - a person decided its gate: ``resolved``, whatever the decision. A blank-noted approval
      answers no question (§24ad), and the question is asked again at the next gate;
    - its run no longer waits, with no person's decision: ``superseded``;
    - it still waits and the campaign's ruling bound has passed since it opened: ``expired``. The
      sweep then cancels the run, and the cycle ends parked.

    An escalation whose run the sweep could not read is left pending."""
    if campaign.state is CampaignState.COMPLETED:
        return []
    bound = campaign.policy.ruling_bound_s
    out = []
    for esc in escalations(log, campaign.state):
        if esc.state is not EscalationState.PENDING or esc.run_id not in runs:
            continue
        run = runs[esc.run_id]
        if run.decided_by is not None:
            out.append(
                _closing(
                    esc,
                    EscalationState.RESOLVED,
                    run.decided_by,
                    f"{run.decided_by} decided the {esc.gate_name} gate on {esc.run_id}",
                )
            )
        elif not run.waiting:
            out.append(
                _closing(
                    esc,
                    EscalationState.SUPERSEDED,
                    "squadops",
                    f"{esc.run_id} no longer waits at {esc.gate_name}, and no person decided it",
                )
            )
        elif (now - esc.opened_at).total_seconds() >= bound:
            out.append(
                _closing(
                    esc,
                    EscalationState.EXPIRED,
                    "squadops",
                    f"the escalation opened at {esc.opened_at.isoformat()} and the ruling bound "
                    f"of {bound}s passed with nobody deciding the gate: its cycle is parked, "
                    "unaccepted",
                )
            )
    return out


def parked_run(log: Sequence[ControlLogEntry], run_id: str) -> bool:
    """Whether an expired escalation parked ``run_id``: the cycle ends parked (§24bj) when its
    last run is the one an expiry named, and that run was cancelled."""
    expired = {
        e.binding["escalation_id"]
        for e in log
        if e.outcome is ControlOutcome.APPLIED
        and e.operation is ControlOperation.ESCALATION_CLOSED
        and e.binding.get("state") == EscalationState.EXPIRED
    }
    return any(
        e.operation is ControlOperation.ESCALATION_OPENED
        and e.outcome is ControlOutcome.APPLIED
        and e.binding["escalation_id"] in expired
        and e.binding["identity"]["run_id"] == run_id
        for e in log
    )


#: The states a late answer is recorded against: the bound passed, or the campaign ended, with
#: nobody deciding the gate (§24bj). A pending escalation is answered at its gate.
ANSWERABLE = frozenset({EscalationState.EXPIRED, EscalationState.CANCELLED})


def _cleaned(answers: Mapping[str, str]) -> dict[str, str]:
    return {str(d).strip(): str(text).strip() for d, text in answers.items()}


def answer_refusal(escalation: Escalation | None, answers: Mapping[str, str]) -> str | None:
    """Why a late answer is refused, or ``None`` (§24bm). It answers each decision it names, by the
    decision's id, and only decisions the escalation recorded: one free text never stands for
    several questions. Blank text states nothing (§24ad), and an escalation that was resolved,
    superseded or is still pending has nothing to answer late."""
    if escalation is None:
        return "no escalation with that id is recorded in this campaign"
    if escalation.state not in ANSWERABLE:
        return (
            f"escalation {escalation.escalation_id} is {escalation.state}: only an expired or "
            "cancelled one takes a late answer; a pending one is answered at its gate"
        )
    if not escalation.decision_ids:
        return (
            f"escalation {escalation.escalation_id} recorded no decision ids, so an answer could "
            "not say which question it answers"
        )
    given = _cleaned(answers)
    if not given:
        return "a late answer names each decision it answers, by its id"
    unknown = sorted(set(given) - set(escalation.decision_ids))
    if unknown:
        return (
            f"escalation {escalation.escalation_id} asked {list(escalation.decision_ids)}; "
            f"{unknown} are not among them"
        )
    blank = sorted(d for d, text in given.items() if not text)
    if blank:
        return f"an answer with no text states nothing (§24ad): {blank}"
    if escalation.answers and dict(escalation.answers) != given:
        # The same answers again are a retry, and replay; others would make the record ambiguous
        # for every later launch and gate that reads it.
        return (
            f"escalation {escalation.escalation_id} already holds its late answer: "
            f"{dict(escalation.answers)!r}"
        )
    return None


def answer_transition(
    escalation: Escalation,
    answers: Mapping[str, str],
    *,
    actor: str,
    actor_role: str,
    reason: str,
) -> CampaignTransition:
    """The ``escalation_answered`` row: a record, accepted on a completed campaign too, that never
    reopens it or resumes the parked cycle (§24bj). One per escalation, by its key. Each answer is
    kept with the question it answers, as the escalation recorded it."""
    given = _cleaned(answers)
    return CampaignTransition(
        operation=ControlOperation.ESCALATION_ANSWERED,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        idempotency_key=f"escalation_answered:{escalation.escalation_id}",
        next_state=None,
        target=escalation.run_id,
        binding={
            "escalation_id": escalation.escalation_id,
            "answers": given,
            "questions": {d: escalation.question_of(d) or "" for d in given},
        },
    )


def recorded_answers(
    logs: Iterable[tuple[Sequence[LogRow], CampaignState]],
) -> dict[str, RecordedAnswer]:
    """Each decision a late answer names, across the given campaigns' logs, with the latest answer
    for it and the question it answered (§24bm). A later proposal launch carries a compatible one
    into its manifest; a later plan gate checks the plan still holds it."""
    found: dict[str, RecordedAnswer] = {}
    for log, state in logs:
        for esc in escalations(log, state):
            if not esc.answers or esc.answered_at is None or esc.answered_by is None:
                continue
            for decision_id, text in esc.answers.items():
                prior = found.get(decision_id)
                if prior is None or esc.answered_at > prior.answered_at:
                    found[decision_id] = RecordedAnswer(
                        decision_id=decision_id,
                        question=esc.question_of(decision_id) or "",
                        answer=text,
                        answered_by=esc.answered_by,
                        answered_at=esc.answered_at,
                        escalation_id=esc.escalation_id,
                    )
    return found


def same_question(a: str, b: str) -> bool:
    """Whether two questions are the same one (§24bm): equal once case, spacing and trailing
    punctuation are set aside. A shared decision id is not enough: an author's ids recur across a
    project's framings, and one id can ask a different question."""

    def norm(q: str) -> str:
        return " ".join(q.split()).casefold().rstrip("?.! ")

    return bool(norm(a)) and norm(a) == norm(b)


def uncarried(
    cited: Mapping[str, tuple[str, str]], on_record: Mapping[str, RecordedAnswer]
) -> list[tuple[str, str]]:
    """Each decision whose plan cites a late answer it does not carry, as ``(id, why)`` (§24bm).

    ``cited`` is the manifest's decisions that name a late answer in their warrant, as
    ``{id: (choice, escalation_id)}``. The plan carries the answer only when that escalation's
    recorded answer for the decision is still the decision's choice. A historical "descending"
    never authorizes an ascending plan because both are called ``list-ordering``."""
    out = []
    for decision_id, (choice, escalation_id) in sorted(cited.items()):
        held = on_record.get(decision_id)
        if held is None or held.escalation_id != escalation_id:
            out.append(
                (
                    decision_id,
                    f"{decision_id}: the plan cites a late answer from {escalation_id} "
                    "that is not on record for this decision",
                )
            )
        elif " ".join(choice.split()) != " ".join(held.answer.split()):
            out.append(
                (
                    decision_id,
                    f"{decision_id}: the plan's choice {choice!r} is not the late answer "
                    f"it cites, {held.answer!r} ({escalation_id})",
                )
            )
    return out
