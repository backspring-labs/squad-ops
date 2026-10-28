"""A source-backed run's candidate, verified by the product's own checks (SIP-0112 FR-10, FR-20;
E.4.3).

The candidate (the pinned commit's tree, with the squad's accepted changes) is checked exactly
as the inherited baseline was: the same Development Configuration revision, through the same
X-3a path. Each check's result is the candidate's own. Its attribution is read against the
baseline's, and the two are kept apart (§8.3.1). On a repository-backed Campaign's branch, past
the calibration record, the baseline is the accepted verification that made the head instead
(SIP-0109 §24bv point 3, ``previous_verification_baseline``).

2.4's acceptance policy, until a Project records an owner-approved one (FR-10):
- a FAIL the baseline didn't have, or one whose origin can't be told, blocks;
- an inherited FAIL stays visible and does not block;
- UNVERIFIED never credits. A candidate no check executed and passed is unverified, and an
  unverified candidate is not approved: missing evidence grants no waiver.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.projects.baseline import (
    FAIL,
    INHERITED,
    INTRODUCED,
    PASS,
    BaselineInvalid,
    CheckResult,
    InheritedBaseline,
    attribute,
    parse_check,
)

SOURCE_VERIFICATION_SCHEMA = "source-verification/v1"
#: How a run's verification is stored in the vault, beside its cycle and run (E.4.3).
SOURCE_VERIFICATION_TYPE = "source_verification"
SOURCE_VERIFICATION_FILENAME = "source_verification.json"
#: v2 (#2609): a check failing on both sides is compared finding by finding when it declares a
#: reader, so a change that adds findings to an already-failing check is a regression.
ACCEPTANCE_POLICY = "no-introduced-regression/v2"
ACCEPTED, REGRESSED, UNVERIFIED_CANDIDATE = "accepted", "regressed", "unverified"
#: What a candidate's checks are compared with (SIP-0109 §24bv point 3): the inherited baseline at
#: the commit it was built on, or the accepted verification of the increment that made that commit
#: a campaign branch's head.
INHERITED_BASELINE, PREVIOUS_VERIFICATION = "inherited_baseline", "previous_verification"


class RegressionBaselineInvalid(ValueError):
    """A stored verification that can't be an increment's regression baseline, and why."""


@dataclass(frozen=True)
class SourceVerification:
    project_id: str
    cycle_id: str
    run_id: str
    baseline_commit: str
    development_configuration_revision: int
    candidate_revision_id: str
    candidate_tree_identity: str
    changed_paths: tuple[str, ...]
    environment: dict[str, str]
    checks: tuple[CheckResult, ...]
    #: What the squad emitted that isn't a file of the product, so the candidate leaves it out
    #: (#2591): named here rather than dropped silently.
    left_out: tuple[str, ...] = ()
    #: The source verification the candidate was compared with, when it was built on a campaign
    #: branch's head past the calibration record (SIP-0109 §24bv point 3). ``None``: the
    #: inherited baseline at ``baseline_commit``.
    regression_baseline_ref: str | None = None

    @property
    def blocking(self) -> list[str]:
        return [c.id for c in self.checks if c.result == FAIL and c.attribution != INHERITED]

    @property
    def verdict(self) -> str:
        if self.blocking:
            return REGRESSED
        return ACCEPTED if any(c.result == PASS for c in self.checks) else UNVERIFIED_CANDIDATE

    def summary(self) -> str:
        """One line a reader can act on: the verdict, and the checks that decided it."""
        if self.verdict == REGRESSED:
            return "regressed: " + "; ".join(
                _why_blocking(c) for c in self.checks if c.id in self.blocking
            )
        inherited = [c.id for c in self.checks if c.result == FAIL]
        passed = [c.id for c in self.checks if c.result == PASS]
        if self.verdict == UNVERIFIED_CANDIDATE:
            return "unverified: no check of the product's own executed and passed"
        tail = f"; inherited failures: {', '.join(inherited)}" if inherited else ""
        return f"accepted: {', '.join(passed)} passed{tail}"

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": SOURCE_VERIFICATION_SCHEMA,
            "project_id": self.project_id,
            "cycle_id": self.cycle_id,
            "run_id": self.run_id,
            "baseline_commit": self.baseline_commit,
            "development_configuration_revision": self.development_configuration_revision,
            "candidate_revision_id": self.candidate_revision_id,
            "candidate_tree_identity": self.candidate_tree_identity,
            "changed_paths": list(self.changed_paths),
            "left_out": list(self.left_out),
            "acceptance_policy": ACCEPTANCE_POLICY,
            # §24bv point 3: what the checks' attributions were read against.
            "regression_baseline": (
                {"kind": PREVIOUS_VERIFICATION, "ref": self.regression_baseline_ref}
                if self.regression_baseline_ref is not None
                else {"kind": INHERITED_BASELINE, "ref": None}
            ),
            "verdict": self.verdict,
            "environment": dict(self.environment),
            "checks": [c.to_document() for c in self.checks],
            "evidence": {c.id: dict(c.evidence) for c in self.checks if c.evidence},
        }


def _why_blocking(check: CheckResult) -> str:
    """One blocking check, said as what a reader acts on (#2609)."""
    read = check.read or {}
    if read.get("grown"):
        found = ", ".join(read["grown"])
        return f"{check.id} gained findings the baseline didn't have ({found})"
    if check.attribution != INTRODUCED:
        return f"{check.id} couldn't be compared with its baseline ({read.get('reason', 'no reading')})"
    return f"{check.id} failed where the baseline did not"


def previous_verification_baseline(
    document: Any, *, ref: str, project_id: str, commit: str, revision: int
) -> tuple[InheritedBaseline, str]:
    """SIP-0109 §24bv point 3: the regression baseline of an increment built on a campaign
    branch's head, read from the stored verification ``ref`` of the increment whose promotion made
    it. It's the checks' results on the head's own tree, at ``commit``, with their readings, in
    the inherited baseline's form, so ``attributed`` reads a candidate against it as it reads one
    against the Project's (FR-20). Also returns the tree identity it verified, which the caller
    holds to the tree at ``commit``.

    Raises:
        RegressionBaselineInvalid: The document is no source verification of this Project; it
            wasn't accepted; it ran at another Development Configuration revision, so its checks
            aren't the candidate's like for like; or a check row can't be read.
    """
    if not isinstance(document, Mapping) or document.get("schema") != SOURCE_VERIFICATION_SCHEMA:
        raise RegressionBaselineInvalid(f"verification {ref} is no {SOURCE_VERIFICATION_SCHEMA}")
    if document.get("project_id") != project_id:
        raise RegressionBaselineInvalid(
            f"verification {ref} is Project {document.get('project_id')}'s, not {project_id}'s"
        )
    if document.get("verdict") != ACCEPTED:
        raise RegressionBaselineInvalid(
            f"verification {ref} reads {document.get('verdict')!r}: only an accepted one made a head"
        )
    at = document.get("development_configuration_revision")
    if at != revision:
        raise RegressionBaselineInvalid(
            f"verification {ref} ran at Development Configuration revision {at}, and the run pins "
            f"revision {revision}: a candidate is compared only with checks run as its own are "
            "(FR-20). The rebase onto a reconciled Project re-verifies the head (§24bv point 4)"
        )
    tree = document.get("candidate_tree_identity")
    if not isinstance(tree, str) or not tree:
        raise RegressionBaselineInvalid(f"verification {ref} names no tree it verified")
    try:
        checks = tuple(parse_check(entry) for entry in document.get("checks") or ())
    except (BaselineInvalid, KeyError) as e:
        raise RegressionBaselineInvalid(f"verification {ref}'s checks can't be read: {e}") from e
    baseline = InheritedBaseline(
        project_id=project_id,
        commit=commit,
        development_configuration_revision=revision,
        environment=document.get("environment") or {},
        checks=checks,
    )
    return baseline, tree


def attributed(
    candidate: tuple[CheckResult, ...], baseline: InheritedBaseline
) -> tuple[CheckResult, ...]:
    """Each candidate check, attributed against the baseline's check of the same id."""
    inherited = {c.id: c for c in baseline.checks}
    return tuple(attribute(c, inherited.get(c.id)) for c in candidate)
