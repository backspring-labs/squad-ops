"""The inherited baseline (SIP-0112 FR-20, §8.3.1; E.4.2).

Before any change to an unfamiliar product, its own checks are run against the pinned,
unmodified source in the sandbox (X-3a), and what happened is recorded, as it happened:
- a check that ran and passed is PASS, and one that ran and failed is FAIL, attributed
  ``inherited``: a failure that was already there is never a regression a Cycle introduced;
- a check that couldn't run is UNVERIFIED with its reason. That covers a missing tool, a timeout,
  a setup step that failed, a sandbox that runs nothing, or an environment the check declares and
  the sandbox doesn't provide. UNVERIFIED never credits.

The source is never patched and no check is suppressed to make onboarding look green.

The baseline's document is the shape the shared fixture records. Each check's evidence (exit
status, duration, bounded output) is kept beside it, not in it.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from squadops.projects.development_configuration import Check
from squadops.sandbox.findings import READERS, FindingsReading, UnknownReader, comparable, grown

BASELINE_SCHEMA = "inherited-baseline/v1"
_SCHEMA_MAJOR = re.compile(r"^inherited-baseline/v(\d+)$")
PASS, FAIL, UNVERIFIED = "PASS", "FAIL", "UNVERIFIED"
RESULTS = (PASS, FAIL, UNVERIFIED)
INHERITED = "inherited"
#: FR-20's other attributions, read against the inherited baseline: a check the candidate fails
#: and the baseline passed; one it passes and the baseline failed; and one either side couldn't
#: run, so nothing can be said of where its result came from.
INTRODUCED = "introduced/regressed"
RESOLVED = "resolved"
UNVERIFIED_ATTRIBUTION = "unverified attribution"
#: X-3a's outcomes that mean the check itself never reached an exit status.
_DID_NOT_RUN = {
    "timeout": "timed out",
    "command_not_found": "its command was not found in the sandbox's image",
    "command_not_executable": "its command is not executable in the sandbox's image",
    "setup_failed": "a setup step failed before it ran",
}
#: Of those, the outcomes that say the check's own command isn't in the image: H.4's toolchain gap.
_TOOLCHAIN_MISSING = ("command_not_found", "command_not_executable")


class BaselineInvalid(ValueError):
    pass


#: #2609: how a check that fails on both sides was compared. ``findings``, finding by finding by
#: its declared reader; ``whole``, by its result alone, with the reason.
READ_FINDINGS, READ_WHOLE = "findings", "whole"


@dataclass(frozen=True)
class CheckResult:
    id: str
    result: str
    attribution: str = INHERITED
    reason: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict, compare=False)
    #: #2609: the run's findings by its check's declared reader, or ``None`` for a check with none.
    findings: FindingsReading | None = field(default=None, compare=False)
    #: #2609: how its attribution was read, when the check fails on both sides (``read_as``).
    read: Mapping[str, Any] | None = field(default=None, compare=False)

    def to_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "result": self.result,
            "attribution": self.attribution,
            **({"reason": self.reason} if self.reason else {}),
            **({"findings": self.findings.as_dict()} if self.findings else {}),
            **({"read": dict(self.read)} if self.read else {}),
        }


@dataclass(frozen=True)
class InheritedBaseline:
    project_id: str
    commit: str
    development_configuration_revision: int
    environment: Mapping[str, str]
    checks: tuple[CheckResult, ...]

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": BASELINE_SCHEMA,
            "project_id": self.project_id,
            "commit": self.commit,
            "development_configuration_revision": self.development_configuration_revision,
            "environment": dict(self.environment),
            "checks": [c.to_document() for c in self.checks],
        }

    def evidence(self) -> dict[str, Any]:
        return {c.id: dict(c.evidence) for c in self.checks if c.evidence}

    def failing(self) -> list[str]:
        return [c.id for c in self.checks if c.result == FAIL]


def missing_environment(check: Check, available: Iterable[str]) -> CheckResult | None:
    """A check the sandbox can't give its declared environment: UNVERIFIED by its declaration,
    decided before anything runs. Its exit status would lie (a skipped test exits 0)."""
    missing = [n for n in check.requires_environment if n not in set(available)]
    if not missing:
        return None
    return CheckResult(
        check.id, UNVERIFIED, reason=f"environment gap: {', '.join(missing)} is not set"
    )


def result_of(check: Check, run: Any) -> CheckResult:
    """A declared check's X-3a run (``CommandResult``), in §8.3.1's vocabulary."""
    evidence = {
        "outcome": run.outcome,
        "exit_code": run.exit_code,
        "duration_seconds": run.duration_seconds,
        "stdout_tail": run.stdout_tail,
        "stderr_tail": run.stderr_tail,
        "stdout_truncated": run.stdout_truncated,
        "stderr_truncated": run.stderr_truncated,
    }
    if not run.ran:
        reason = f"not run: {run.unavailable_reason or 'the sandbox runs nothing'}"
        return CheckResult(check.id, UNVERIFIED, reason=reason, evidence=evidence)
    if run.outcome in _DID_NOT_RUN:
        return CheckResult(
            check.id, UNVERIFIED, reason=_DID_NOT_RUN[run.outcome], evidence=evidence
        )
    verdict = PASS if run.exit_code == 0 else FAIL
    return CheckResult(check.id, verdict, evidence=evidence, findings=_reading_of(check, run))


def toolchain_missing(result: CheckResult) -> bool:
    """Whether a check couldn't run because its command isn't in the sandbox's image (H.4). Read
    from its evidence when it has any, and otherwise from its recorded reason, which a stored
    baseline keeps without the evidence."""
    if result.evidence:
        return result.evidence.get("outcome") in _TOOLCHAIN_MISSING
    return result.reason in {_DID_NOT_RUN[o] for o in _TOOLCHAIN_MISSING}


def _reading_of(check: Check, run: Any) -> FindingsReading | None:
    """The run's reading by its check's declared reader, or ``None`` for a check that declares
    none. A declared reader whose run brought back no reading (a sandbox from before #2623, or a
    stand-in) reads as unreadable, never as a check with no reader: that would read it whole."""
    if not check.findings:
        return None
    if run.findings:
        return FindingsReading.from_dict(run.findings)
    return FindingsReading(
        check.findings,
        READERS[check.findings],
        readable=False,
        reason="the run returned no reading for its declared reader",
    )


def attribute(candidate: CheckResult, baseline: CheckResult | None) -> CheckResult:
    """A candidate's check, attributed against the inherited baseline's (FR-20). The result stays
    the candidate's own, and only the attribution compares:
    - the same result as the baseline is inherited: it was already there (a FAIL on both sides is
      read as below);
    - a FAIL where the baseline passed is introduced, and a PASS where it failed is resolved;
    - an UNVERIFIED on either side, or a check the baseline never ran, is unverified
      attribution.

    A FAIL on both sides is compared finding by finding when its check declares a reader and both
    runs were read (#2609, ``no-introduced-regression/v2``): a finding key whose count grew is
    introduced; two readings that can't be compared (another reader or version, an unreadable run,
    a pytest run that ran fewer tests) is unverified attribution; neither, inherited. Otherwise it
    is compared as a whole, and says so (``read``)."""
    if candidate.result == UNVERIFIED or baseline is None or baseline.result == UNVERIFIED:
        attribution = UNVERIFIED_ATTRIBUTION
    elif candidate.result == FAIL and baseline.result == FAIL:
        return _failing_on_both_sides(candidate, baseline)
    elif candidate.result == baseline.result:
        attribution = INHERITED
    elif candidate.result == FAIL:
        attribution = INTRODUCED
    else:
        attribution = RESOLVED
    return dataclasses.replace(candidate, attribution=attribution)


def _failing_on_both_sides(candidate: CheckResult, baseline: CheckResult) -> CheckResult:
    """#2609: a check that fails at the baseline and again with the change."""
    if candidate.findings is None:
        whole = {"by": READ_WHOLE, "reason": "the check declares no findings reader"}
        return dataclasses.replace(candidate, attribution=INHERITED, read=whole)
    if baseline.findings is None:
        whole = {"by": READ_WHOLE, "reason": "baseline has no findings"}
        return dataclasses.replace(candidate, attribution=INHERITED, read=whole)
    why = comparable(baseline.findings, candidate.findings)
    if why is not None:
        unread = {"by": READ_FINDINGS, "reason": why}
        return dataclasses.replace(candidate, attribution=UNVERIFIED_ATTRIBUTION, read=unread)
    grew = grown(baseline.findings, candidate.findings)
    read = {
        "by": READ_FINDINGS,
        "reader": candidate.findings.reader,
        "version": candidate.findings.version,
        **({"grown": {k: list(v) for k, v in grew.items()}} if grew else {}),
    }
    return dataclasses.replace(candidate, attribution=INTRODUCED if grew else INHERITED, read=read)


def parse_baseline(doc: Mapping[str, Any]) -> InheritedBaseline:
    """A stored baseline. An unknown major version is refused before anything else is read."""
    schema = doc.get("schema")
    match = _SCHEMA_MAJOR.match(schema) if isinstance(schema, str) else None
    if match is None or match.group(1) != "1":
        raise BaselineInvalid(f"schema {schema!r} is not a baseline this reads")
    for key in ("project_id", "commit", "development_configuration_revision", "checks"):
        if key not in doc:
            raise BaselineInvalid(f"{key} is required")
    return InheritedBaseline(
        project_id=doc["project_id"],
        commit=doc["commit"],
        development_configuration_revision=doc["development_configuration_revision"],
        environment=doc.get("environment") or {},
        checks=tuple(parse_check(entry) for entry in doc["checks"]),
    )


def parse_check(entry: Mapping[str, Any]) -> CheckResult:
    """One stored check row, a baseline's or a source verification's, with its reading."""
    if entry.get("result") not in RESULTS:
        raise BaselineInvalid(f"check {entry.get('id')!r}: result is one of {RESULTS}")
    findings = entry.get("findings")
    try:
        reading = FindingsReading.from_dict(findings) if findings else None
    except (UnknownReader, ValueError, KeyError) as e:
        raise BaselineInvalid(f"check {entry.get('id')!r}: its findings can't be read ({e})") from e
    return CheckResult(
        entry["id"],
        entry["result"],
        entry.get("attribution", INHERITED),
        entry.get("reason"),
        findings=reading,
    )
