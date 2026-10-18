"""An evaluation run's record and its reference (SIP-0113 §4.1, §4.8; shared contract 5; #2415).

One record per evaluation run: a cycle evaluated against one suite, with its own ID, since a cycle
can be evaluated more than once (a re-run after ``blocked_unverified``, a #1959 replay, a second
suite). It names trees only by SIP-0109's ``FileTree.identity``, never by sandbox revision or Git
commit; a commit is reached through SIP-0112's mapping (contract 4).

``OutcomeEvaluationRef`` is what SIP-0112's Project history stores (SIP-0112 §8.2.1). Its reader
refuses an unknown schema major version with a typed error and reads none of it, and refuses a
reference with a field absent, a nullable one included.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from squadops.scenarios.models import ScenarioSuite

REF_SCHEMA = "outcome-evaluation-ref/v1"
_REF_FAMILY = "outcome-evaluation-ref/"
_IDENTITY = re.compile(r"[0-9a-f]{64}")


class EvaluationInvalid(ValueError):
    """A record or a reference whose content can't be held as given."""


class UnknownSchemaMajor(EvaluationInvalid):
    """A reference under a schema major version this reader doesn't know (SIP-0112 §8.2.1)."""


class Applicability(StrEnum):
    APPLICABLE = "applicable"
    # A scenario whose surface kind the Project doesn't have. Not evidence: it counts in no rate,
    # and is never reported as blocked_unverified or as passed (§4.1).
    NOT_APPLICABLE = "not_applicable"


class ScenarioResult(StrEnum):
    """SIP-0096's three families, as §4.1 rules them."""

    PASSED = "passed"
    FAILED = "failed"
    BLOCKED_UNVERIFIED = "blocked_unverified"


class BlockedReason(StrEnum):
    """Why an applicable scenario couldn't run (§4.1, and SIP-0112 §8.2.1's contract 7)."""

    NO_RUNNER = "no_runner"
    NO_START_DECLARATION = "no_start_declaration"
    START_FAILED = "start_failed"
    SECRET_NOT_AVAILABLE = "secret_not_available"
    SURFACE_ABSENT = "surface_absent"
    BROWSER_UNAVAILABLE = "browser_unavailable"


@dataclass(frozen=True)
class ScenarioOutcome:
    """One scenario's part of an evaluation: what ran, and how it ended."""

    scenario_id: str
    version: str
    goal: str
    applicability: Applicability
    result: ScenarioResult | None = None
    blocked_reason: BlockedReason | None = None
    steps_taken: int = 0
    first_failing_step: int | None = None
    elapsed_seconds: float | None = None
    retries: int = 0

    def __post_init__(self) -> None:
        where = f"scenario {self.scenario_id!r}"
        if self.applicability is Applicability.NOT_APPLICABLE:
            if self.result is not None or self.blocked_reason is not None:
                raise EvaluationInvalid(f"{where} is not applicable, so it has no result")
            return
        if self.result is None:
            raise EvaluationInvalid(f"{where} is applicable, so it has a result")
        blocked = self.result is ScenarioResult.BLOCKED_UNVERIFIED
        if blocked != (self.blocked_reason is not None):
            raise EvaluationInvalid(
                f"{where}: a blocked_unverified result names why, and only it does"
            )
        if (self.result is ScenarioResult.FAILED) != (self.first_failing_step is not None):
            raise EvaluationInvalid(f"{where}: a failed result names its first failing step")

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "version": self.version,
            "goal": self.goal,
            "applicability": self.applicability.value,
            "result": self.result.value if self.result else None,
            "blocked_reason": self.blocked_reason.value if self.blocked_reason else None,
            "steps_taken": self.steps_taken,
            "first_failing_step": self.first_failing_step,
            "elapsed_seconds": self.elapsed_seconds,
            "retries": self.retries,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> ScenarioOutcome:
        return cls(
            scenario_id=d["scenario_id"],
            version=d["version"],
            goal=d["goal"],
            applicability=Applicability(d["applicability"]),
            result=ScenarioResult(d["result"]) if d.get("result") else None,
            blocked_reason=BlockedReason(d["blocked_reason"]) if d.get("blocked_reason") else None,
            steps_taken=d.get("steps_taken", 0),
            first_failing_step=d.get("first_failing_step"),
            elapsed_seconds=d.get("elapsed_seconds"),
            retries=d.get("retries", 0),
        )


@dataclass(frozen=True)
class OutcomeEvaluationRef:
    """The reference SIP-0112's Project history stores (contract 5). ``evaluation_id`` is opaque
    to every reader. ``campaign_id`` is null only outside a campaign, never absent."""

    evaluation_id: str
    suite_digest: str
    project_id: str
    campaign_id: str | None
    cycle_id: str
    evaluated_tree_identity: str
    previous_accepted_tree_identity: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REF_SCHEMA,
            "evaluation_id": self.evaluation_id,
            "suite_digest": self.suite_digest,
            "project_id": self.project_id,
            "campaign_id": self.campaign_id,
            "cycle_id": self.cycle_id,
            "evaluated_tree_identity": self.evaluated_tree_identity,
            "previous_accepted_tree_identity": self.previous_accepted_tree_identity,
        }


_REQUIRED_TEXT = ("evaluation_id", "project_id", "cycle_id")
_IDENTITIES = ("suite_digest", "evaluated_tree_identity")
_NULLABLE = ("campaign_id", "previous_accepted_tree_identity")


def parse_reference(doc: Mapping[str, Any]) -> OutcomeEvaluationRef:
    """Read a stored reference, or refuse it with a typed error, reading none of it."""
    schema = doc.get("schema")
    if not isinstance(schema, str) or not schema.startswith(_REF_FAMILY):
        raise EvaluationInvalid(f"not an outcome evaluation reference: schema {schema!r}")
    if schema != REF_SCHEMA:
        raise UnknownSchemaMajor(f"{schema!r} is not a major version this reader knows")
    absent = [k for k in (*_REQUIRED_TEXT, *_IDENTITIES, *_NULLABLE) if k not in doc]
    if absent:
        raise EvaluationInvalid(f"the reference has no {absent}: every field is present")
    for key in _REQUIRED_TEXT:
        if not isinstance(doc[key], str) or not doc[key].strip():
            raise EvaluationInvalid(f"{key} must be non-empty text, got {doc[key]!r}")
    for key in (*_IDENTITIES, "previous_accepted_tree_identity"):
        value = doc[key]
        if value is None and key == "previous_accepted_tree_identity":
            continue
        if not isinstance(value, str) or not _IDENTITY.fullmatch(value):
            raise EvaluationInvalid(f"{key} must be 64 lowercase hex characters, got {value!r}")
    if doc["campaign_id"] is not None and not str(doc["campaign_id"]).strip():
        raise EvaluationInvalid("campaign_id is null outside a campaign, never empty")
    return OutcomeEvaluationRef(**{k: doc[k] for k in (*_REQUIRED_TEXT, *_IDENTITIES, *_NULLABLE)})


@dataclass(frozen=True)
class EvaluationRecord:
    """A cycle evaluated against one suite (§4.1)."""

    evaluation_id: str
    project_id: str
    campaign_id: str | None
    cycle_id: str
    evaluated_tree_identity: str
    previous_accepted_tree_identity: str | None
    suite_digest: str
    outcomes: tuple[ScenarioOutcome, ...]
    evaluated_at: datetime

    def reference(self) -> OutcomeEvaluationRef:
        return OutcomeEvaluationRef(
            evaluation_id=self.evaluation_id,
            suite_digest=self.suite_digest,
            project_id=self.project_id,
            campaign_id=self.campaign_id,
            cycle_id=self.cycle_id,
            evaluated_tree_identity=self.evaluated_tree_identity,
            previous_accepted_tree_identity=self.previous_accepted_tree_identity,
        )


def new_evaluation_id() -> str:
    return f"evl_{uuid.uuid4().hex[:12]}"


def evaluation_record(
    suite: ScenarioSuite,
    outcomes: tuple[ScenarioOutcome, ...],
    *,
    project_id: str,
    campaign_id: str | None,
    cycle_id: str,
    evaluated_tree_identity: str,
    previous_accepted_tree_identity: str | None,
    evaluated_at: datetime,
    evaluation_id: str | None = None,
) -> EvaluationRecord:
    """A record that names its suite's scenarios exactly: one outcome for each, at the version and
    goal the suite holds. Anything else would report against a suite it didn't run."""
    expected = {s.scenario_id: (s.version, s.goal) for s in suite.scenarios}
    given = {o.scenario_id: (o.version, o.goal) for o in outcomes}
    if len(given) != len(outcomes) or given != expected:
        raise EvaluationInvalid(
            "an evaluation names each of its suite's scenarios once, at the suite's version and goal"
        )
    record = EvaluationRecord(
        evaluation_id=evaluation_id or new_evaluation_id(),
        project_id=project_id,
        campaign_id=campaign_id,
        cycle_id=cycle_id,
        evaluated_tree_identity=evaluated_tree_identity,
        previous_accepted_tree_identity=previous_accepted_tree_identity,
        suite_digest=suite.digest,
        outcomes=outcomes,
        evaluated_at=evaluated_at,
    )
    parse_reference(record.reference().to_dict())  # the reference it yields must be readable
    return record
