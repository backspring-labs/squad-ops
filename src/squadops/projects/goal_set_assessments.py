"""The crew's assessments of a goal set's expected results (SIP-0115 §5.7, §6, Q43; slice 5,
#2888).

An assessment is one judgement of one expected result at a point in a Campaign: its ``reading``
(``met``, ``not_met`` or ``unclear``), for a shortfall the ``cause``, for a framework cause the
squad-ops ``issue`` it filed, the ``evidence`` it read by id, the goal-set revision it read, and
its ``source_ref``: the signed statement it came from (Q43).

**It is a report, not curation.** §6 lets the owner and the crew's supervisor seat record one, with
no Campaign grant: Q41's grant covers the order, which an assessment never touches. It decides
nothing (§5.7): it writes no goal-set revision, changes no item's status and no gate. A closing
interpretation comes after the close, so a completed Campaign takes one.

**Append-only, in its own order.** Each takes the next ``sequence`` on the goal set, and is never
edited. It may name earlier ones it ``supersedes``. Its Campaign's control-log position
(``log_seq``) is read at the write. It orders it against that Campaign's acceptances only: log
positions can't be compared across Campaigns (§5.7).

**The derived reading** is per Campaign, as an item's status is, and nothing derived is stored.
``standings`` reads each expected result of the revision the Campaign reads now:
- the latest is the highest ``sequence`` not superseded;
- it is ``stale`` when, after it, an increment serving the result was accepted, or the result
  changed from the revision it read;
- two not-stale assessments that disagree, neither superseding the other, are ``conflicting``.
  Nothing resolves them: a new assessment naming both in ``supersedes`` does;
- a result a later revision removed drops out of this view and stays in the history.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from squadops.campaigns.backlog import Acceptance, acceptances, campaign_backlog
from squadops.campaigns.models import Campaign, CampaignNotFoundError
from squadops.projects.development_configuration import submission_digest
from squadops.projects.goal_set import ExpectedResult, GoalSetInvalid, GoalSetRevision
from squadops.projects.goal_set_actions import Actor

if TYPE_CHECKING:
    from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.projects.goal_sets import GoalSetRegistryPort

#: A cited id: a cycle's, a control-log row's, an evaluation's. No spaces, so a citation can't
#: carry a scenario's step or value (§7).
_CITED_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EVIDENCE_KEYS = frozenset({"cycles", "rulings", "evaluations"})
_EVALUATION_KEYS = frozenset({"id", "passed", "failed"})


class Reading(StrEnum):
    MET = "met"
    NOT_MET = "not_met"
    UNCLEAR = "unclear"


class Cause(StrEnum):
    """Whose work a shortfall is (§5.7)."""

    APP_WORK = "app_work"
    FRAMEWORK_DEFECT = "framework_defect"
    FRAMEWORK_GAP = "framework_gap"
    NEEDS_OWNER = "needs_owner"

    @property
    def files_an_issue(self) -> bool:
        """A framework cause names the squad-ops issue it filed (§5.7)."""
        return self in (Cause.FRAMEWORK_DEFECT, Cause.FRAMEWORK_GAP)


class Standing(StrEnum):
    """How an expected result's latest assessment reads now (§5.7)."""

    CURRENT = "current"
    STALE = "stale"
    CONFLICTING = "conflicting"
    UNASSESSED = "unassessed"


class CampaignHasNoGoalSet(LookupError):
    """The Campaign named reads requirements, so it has no expected result to assess."""


@dataclass(frozen=True)
class CitedEvaluation:
    """An evaluation an assessment read: its id and counts, never a step or value (§5.7, §7)."""

    id: str
    passed: int
    failed: int


@dataclass(frozen=True)
class AssessmentEvidence:
    """What an assessment read, by id: cycles, gate rulings (control-log rows) and evaluations."""

    cycles: tuple[str, ...] = ()
    rulings: tuple[str, ...] = ()
    evaluations: tuple[CitedEvaluation, ...] = ()

    def to_document(self) -> dict[str, Any]:
        return {
            "cycles": list(self.cycles),
            "rulings": list(self.rulings),
            "evaluations": [
                {"id": e.id, "passed": e.passed, "failed": e.failed} for e in self.evaluations
            ],
        }


@dataclass(frozen=True)
class Assessment:
    """One assessment. ``sequence`` is the store's, 0 until it is recorded; ``log_seq`` is the
    Campaign's last control-log row when it was written."""

    project_id: str
    campaign_id: str
    expected_result: str
    goals_revision: int
    reading: Reading
    evidence: AssessmentEvidence
    reason: str
    author: str
    created_at: datetime
    source_ref: str | None = None
    cause: Cause | None = None
    issue: int | None = None
    supersedes: tuple[int, ...] = ()
    log_seq: int = 0
    sequence: int = 0


@dataclass(frozen=True)
class ResultStanding:
    """One expected result as a Campaign's assessments leave it: the latest alone, or, while they
    conflict, each one that disagrees, newest first; none when it is ``unassessed``."""

    expected_result: str
    standing: Standing
    assessments: tuple[Assessment, ...] = ()


# --- reading a submitted or stored assessment ---


def parse_reading(value: Any) -> Reading:
    if value not in {r.value for r in Reading}:
        raise GoalSetInvalid("reading", f"one of {[r.value for r in Reading]}, not {value!r}")
    return Reading(value)


def parse_cause(reading: Reading, value: Any) -> Cause | None:
    """§5.7: a cause is a shortfall's. ``not_met`` needs one and nothing else takes one, so a
    ``met`` can't carry a cause a reader would act on."""
    if reading is not Reading.NOT_MET:
        if value is not None:
            raise GoalSetInvalid("cause", f"only a not_met reading has a cause, not {reading}")
        return None
    if value not in {c.value for c in Cause}:
        raise GoalSetInvalid(
            "cause", f"a not_met reading names one of {[c.value for c in Cause]}, not {value!r}"
        )
    return Cause(value)


def parse_issue(cause: Cause | None, value: Any) -> int | None:
    """§5.7: a framework cause names the squad-ops issue it filed, by number. Any other names
    none: framework work is the only kind tracked there."""
    filed = cause is not None and cause.files_an_issue
    if value is None:
        if filed:
            raise GoalSetInvalid("issue", f"{cause} names the squad-ops issue it filed")
        return None
    if not filed:
        raise GoalSetInvalid("issue", "only a framework cause names a squad-ops issue")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GoalSetInvalid("issue", f"a squad-ops issue's number, not {value!r}")
    return value


def parse_evidence(doc: Any) -> AssessmentEvidence:
    """What it read, at least one id. Unknown keys are refused rather than kept: nothing in here
    is free text, so held-out content has nowhere to go (§7)."""
    if not isinstance(doc, Mapping):
        raise GoalSetInvalid("evidence", "a mapping of cycles, rulings and evaluations")
    unknown = sorted(str(k) for k in doc if k not in _EVIDENCE_KEYS)
    if unknown:
        raise GoalSetInvalid("evidence", f"unknown field(s) {unknown}")
    evidence = AssessmentEvidence(
        cycles=_cited(doc, "cycles"),
        rulings=_cited(doc, "rulings"),
        evaluations=_evaluations(doc.get("evaluations", [])),
    )
    if not (evidence.cycles or evidence.rulings or evidence.evaluations):
        raise GoalSetInvalid("evidence", "what the assessment read: at least one id")
    return evidence


def _cited(doc: Mapping[str, Any], key: str) -> tuple[str, ...]:
    ids = doc.get(key, [])
    at = f"evidence.{key}"
    if not isinstance(ids, list):
        raise GoalSetInvalid(at, "a list of ids")
    for i, value in enumerate(ids):
        if not isinstance(value, str) or not _CITED_ID.match(value):
            raise GoalSetInvalid(f"{at}[{i}]", f"an id, not {value!r}")
    return tuple(ids)


def _evaluations(docs: Any) -> tuple[CitedEvaluation, ...]:
    if not isinstance(docs, list):
        raise GoalSetInvalid("evidence.evaluations", "a list of an id and its counts")
    cited = []
    for i, doc in enumerate(docs):
        at = f"evidence.evaluations[{i}]"
        if not isinstance(doc, Mapping) or set(doc) != _EVALUATION_KEYS:
            raise GoalSetInvalid(at, f"exactly {sorted(_EVALUATION_KEYS)}")
        if not isinstance(doc["id"], str) or not _CITED_ID.match(doc["id"]):
            raise GoalSetInvalid(f"{at}.id", f"an id, not {doc['id']!r}")
        for key in ("passed", "failed"):
            count = doc[key]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise GoalSetInvalid(f"{at}.{key}", f"a count, not {count!r}")
        cited.append(CitedEvaluation(doc["id"], doc["passed"], doc["failed"]))
    return tuple(cited)


def _supersedes(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list) or any(
        isinstance(s, bool) or not isinstance(s, int) or s < 1 for s in value
    ):
        raise GoalSetInvalid("supersedes", "the sequence numbers of earlier assessments")
    if len(set(value)) != len(value):
        raise GoalSetInvalid("supersedes", f"each assessment once: {value}")
    return tuple(value)


# --- writing one ---


async def record_assessment(
    project_id: str,
    submission: Mapping[str, Any],
    *,
    actor: Actor,
    idempotency_key: str,
    projects: ProjectRegistryPort,
    goal_sets: GoalSetRegistryPort,
    campaigns: CampaignRegistryPort,
    now: datetime | None = None,
) -> tuple[Assessment, bool]:
    """Record the assessment ``submission`` holds (``campaign_id``, ``expected_result``,
    ``goals_revision``, ``reading``, ``cause``, ``issue``, ``evidence``, ``reason``,
    ``source_ref``, ``supersedes``), as the goal set's next in sequence. Returns it and whether
    this replayed an earlier write under its key. Nothing checked here can have changed since
    that write (revisions and assessments are immutable, and a Campaign is never deleted), so a
    retry passes them and the store replays it.

    Raises:
        ProjectNotFoundError: no such Project.
        CampaignNotFoundError: no such Campaign on this Project.
        CampaignHasNoGoalSet: it reads requirements.
        GoalSetInvalid: the submission, naming its field: a revision the goal set doesn't hold, an
            expected result that revision doesn't hold, and a ``supersedes`` that isn't an
            earlier assessment of this result in this Campaign among them.
        ProjectRegistryReadOnlyError, RegistrationKeyConflictError: the store's refusals.
    """
    await projects.get_project(project_id)
    reading = parse_reading(submission.get("reading"))
    cause = parse_cause(reading, submission.get("cause"))
    issue = parse_issue(cause, submission.get("issue"))
    evidence = parse_evidence(submission.get("evidence"))
    supersedes = _supersedes(submission.get("supersedes", []))
    reason = str(submission.get("reason") or "")
    if not reason.strip():
        raise GoalSetInvalid("reason", "required: why it reads so")
    source_ref = submission.get("source_ref")
    if not actor.owner and not source_ref:
        raise GoalSetInvalid("source_ref", "required of the crew: its signed statement (Q43)")
    campaign_id = str(submission["campaign_id"])
    expected_result = str(submission["expected_result"])
    goals_revision = int(submission["goals_revision"])

    request = submission_digest(
        {
            "project_id": project_id,
            "campaign_id": campaign_id,
            "expected_result": expected_result,
            "goals_revision": goals_revision,
            "reading": reading.value,
            "cause": cause.value if cause else None,
            "issue": issue,
            "evidence": evidence.to_document(),
            "reason": reason,
            "source_ref": source_ref,
            "supersedes": list(supersedes),
        }
    )

    campaign = await campaigns.get_campaign(campaign_id)
    if campaign.project_id != project_id:
        raise CampaignNotFoundError(f"Project {project_id} has no campaign {campaign_id}")
    if campaign.objective.goals is None:
        raise CampaignHasNoGoalSet(
            f"campaign {campaign_id} names no goal set (objective.goals): it has no expected "
            "result to assess"
        )
    await _holds_the_result(project_id, goals_revision, expected_result, goal_sets)
    await _supersedes_earlier(project_id, campaign_id, expected_result, supersedes, goal_sets)
    log = await campaigns.control_log(campaign_id)
    return await goal_sets.record_assessment(
        Assessment(
            project_id=project_id,
            campaign_id=campaign_id,
            expected_result=expected_result,
            goals_revision=goals_revision,
            reading=reading,
            evidence=evidence,
            reason=reason,
            author=actor.principal,
            created_at=now or datetime.now(UTC),
            source_ref=source_ref,
            cause=cause,
            issue=issue,
            supersedes=supersedes,
            log_seq=max((e.seq for e in log), default=0),
        ),
        idempotency_key=idempotency_key,
        request_hash=request,
    )


async def _holds_the_result(
    project_id: str, revision: int, expected_result: str, goal_sets: GoalSetRegistryPort
) -> None:
    held = {r.revision: r for r in await goal_sets.list_revisions(project_id)}
    if revision not in held:
        raise GoalSetInvalid(
            "goals_revision", f"Project {project_id}'s goal set holds no revision {revision}"
        )
    if expected_result not in {r.id for r in held[revision].goal_set.expected_results}:
        raise GoalSetInvalid(
            "expected_result", f"revision {revision} holds no expected result {expected_result!r}"
        )


async def _supersedes_earlier(
    project_id: str,
    campaign_id: str,
    expected_result: str,
    supersedes: Sequence[int],
    goal_sets: GoalSetRegistryPort,
) -> None:
    if not supersedes:
        return
    earlier = await goal_sets.list_assessments(
        project_id, campaign_id=campaign_id, expected_result=expected_result
    )
    unknown = sorted(set(supersedes) - {a.sequence for a in earlier})
    if unknown:
        raise GoalSetInvalid(
            "supersedes",
            f"{unknown} name no assessment of {expected_result} in campaign {campaign_id}",
        )


# --- the derived reading ---


def standings(
    assessments: Iterable[Assessment],
    revisions: Iterable[GoalSetRevision],
    at: int,
    accepted: Sequence[Acceptance],
) -> tuple[ResultStanding, ...]:
    """Each expected result of revision ``at`` as one Campaign's ``assessments`` leave it.
    ``accepted`` is that Campaign's acceptances (``backlog.acceptances``)."""
    by_number = {r.revision: r for r in revisions}
    held = list(assessments)
    return tuple(
        _standing(result.id, [a for a in held if a.expected_result == result.id], by_number, at,
                  accepted)
        for result in by_number[at].goal_set.expected_results
    )  # fmt: skip


def _standing(
    result_id: str,
    mine: list[Assessment],
    by_number: Mapping[int, GoalSetRevision],
    at: int,
    accepted: Sequence[Acceptance],
) -> ResultStanding:
    superseded = {s for a in mine for s in a.supersedes}
    live = sorted(
        (a for a in mine if a.sequence not in superseded), key=lambda a: a.sequence, reverse=True
    )
    if not live:
        return ResultStanding(result_id, Standing.UNASSESSED)

    def stale(a: Assessment) -> bool:
        return _accepted_since(a, accepted) or _result_changed(a, by_number, at)

    if stale(live[0]):
        return ResultStanding(result_id, Standing.STALE, (live[0],))
    fresh = tuple(a for a in live if not stale(a))
    if len({(a.reading, a.cause) for a in fresh}) > 1:
        return ResultStanding(result_id, Standing.CONFLICTING, fresh)
    return ResultStanding(result_id, Standing.CURRENT, (live[0],))


def _accepted_since(assessment: Assessment, accepted: Sequence[Acceptance]) -> bool:
    return any(
        a.seq > assessment.log_seq and assessment.expected_result in a.serves for a in accepted
    )


def _result_changed(
    assessment: Assessment, by_number: Mapping[int, GoalSetRevision], at: int
) -> bool:
    def result_in(revision: int) -> ExpectedResult | None:
        held = by_number[revision].goal_set.expected_results
        return next((r for r in held if r.id == assessment.expected_result), None)

    return result_in(assessment.goals_revision) != result_in(at)


async def campaign_assessments(
    campaign: Campaign, *, goal_sets: GoalSetRegistryPort, campaigns: CampaignRegistryPort
) -> tuple[int, tuple[ResultStanding, ...]]:
    """The revision the Campaign reads now, its pinned one or the latest, and each of that
    revision's expected results as this Campaign's assessments leave it.

    Raises:
        CampaignHasNoGoalSet: it reads requirements.
    """
    if campaign.objective.goals is None:
        raise CampaignHasNoGoalSet(f"campaign {campaign.campaign_id} names no goal set")
    view, revisions = await campaign_backlog(campaign, goal_sets=goal_sets, campaigns=campaigns)
    accepted = acceptances(
        revisions,
        await campaigns.control_log(campaign.campaign_id),
        await campaigns.launch_intents(campaign.campaign_id),
    )
    held = await goal_sets.list_assessments(campaign.project_id, campaign_id=campaign.campaign_id)
    return view.revision, standings(held, revisions, view.revision, accepted)
