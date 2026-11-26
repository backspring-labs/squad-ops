"""Whether a candidate's setup failure is the candidate's own (SIP-0117 R5.32, #3200).

A play whose scenario's world wasn't established reads ``setup_failed`` for every assertion.
That is *not executed* (R3.7, SIP-0096): nothing is credited and nothing failed. It stays so
here. What this decides is narrower: whether the run may spend one correction on the candidate
before it gives the scenario up as unread.

It may only when all six conditions hold, each read from a record and none inferred:

1. the same frozen scenario's setup was met on the baseline, in this cycle;
2. both plays ran in one environment, served by one worker;
3. the candidate's provider named an error in a file the candidate changed, inside its
   approved footprint;
4. the candidate's play stopped at its setup, which is where the provider read its log, so the
   error was logged before the setup's first unmet wait ran out;
5. the baseline's provider named no such error;
6. neither play was refused for the worker's own environment.

When one doesn't hold, the routing is what it was: not executed, never credited or failed. An
unexecuted assertion is never made an executed failure to enable a repair.

Engine-neutral, and pure. It reads two reading documents (``models.records_document``) and what
the caller knows of the candidate's tree. It reads no console and names no tool.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from squadops.remote_execution.models import (
    RAN_WITH_ENVIRONMENT,
    RAN_WITH_SERVED_BY,
    AssertionOutcome,
    OperationStatus,
    ScriptError,
)

SCHEMA = "setup-attribution/v1"
#: The attribution's file among a task's evidence.
ATTRIBUTION_FILENAME = "setup_attribution.json"


class Condition(StrEnum):
    """The six conditions, in the order the amendment gives them."""

    BASELINE_SETUP_MET = "baseline_setup_met"
    SAME_ENVIRONMENT = "same_environment"
    ERROR_IN_CHANGED_FOOTPRINT_FILE = "error_in_changed_footprint_file"
    ERROR_BEFORE_SETUP_STOPPED = "error_before_setup_stopped"
    ERROR_ABSENT_FROM_BASELINE = "error_absent_from_baseline"
    NO_ENVIRONMENT_REFUSAL = "no_environment_refusal"


@dataclass(frozen=True)
class ConditionReading:
    """One condition, with what it was read from."""

    condition: Condition
    holds: bool
    evidence: str


@dataclass(frozen=True)
class SetupAttribution:
    """The six readings of one candidate play, and the errors they attribute."""

    scenario_id: str
    readings: tuple[ConditionReading, ...]
    #: The candidate's errors that condition 3 and condition 5 both admit. Empty unless
    #: ``attributed``: a reading that fails a condition attributes nothing.
    errors: tuple[ScriptError, ...]

    @property
    def attributed(self) -> bool:
        return all(reading.holds for reading in self.readings)

    def document(self, *, baseline_reading: str, candidate_revision: str) -> dict[str, Any]:
        """The attribution as kept beside the play's evidence: every condition, held or not,
        with its evidence, and the baseline reading it was read against."""
        return {
            "schema": SCHEMA,
            "scenario_id": self.scenario_id,
            "attributed": self.attributed,
            "candidate_revision": candidate_revision,
            "baseline_reading": baseline_reading,
            "conditions": [
                {"condition": r.condition.value, "holds": r.holds, "evidence": r.evidence}
                for r in self.readings
            ],
            "errors": [{"path": e.path, "line": e.line, "message": e.message} for e in self.errors],
        }

    def repair_evidence(self) -> str:
        """What the correction is told: each attributed error, where the tool named it."""
        return "; ".join(
            f"{e.path}{f' line {e.line}' if e.line else ''}: {e.message}" for e in self.errors
        )


def setup_failed(reading: Mapping[str, Any]) -> bool:
    """Whether ``reading`` is a play that ran and whose setup failed: completed, with at least
    one assertion reading ``setup_failed`` and none that executed and failed. Only such a
    reading is attributed at all: an executed failure has its own correction (R5.1)."""
    outcomes = _outcomes(reading)
    return (
        reading.get("status") == OperationStatus.COMPLETED.value
        and AssertionOutcome.SETUP_FAILED.value in outcomes
        and AssertionOutcome.FAILED.value not in outcomes
    )


def attribute(
    candidate: Mapping[str, Any],
    baseline: Mapping[str, Any] | None,
    *,
    changed: Collection[str],
    in_footprint: Callable[[str], bool],
) -> SetupAttribution:
    """The six conditions for ``candidate``, a reading for which :func:`setup_failed` holds.

    ``baseline`` is this cycle's stored baseline reading of the same criterion, or ``None``
    when the cycle holds none. ``changed`` is the staged paths whose content differs between
    the candidate and the accepted baseline, and ``in_footprint`` says whether a path is inside
    the approved change's footprint."""
    scenario = candidate.get("scenario") or {}
    named = _script_errors(candidate)
    admitted = tuple(e for e in named if e.path in changed and in_footprint(e.path))
    baseline_errors = _script_errors(baseline) if baseline is not None else ()
    on_baseline = {(e.path, e.message) for e in baseline_errors}
    absent = tuple(e for e in admitted if (e.path, e.message) not in on_baseline)
    readings = (
        _baseline_setup_met(scenario, baseline),
        _same_environment(candidate, baseline),
        _error_in_changed_footprint_file(named, admitted, changed, in_footprint),
        _error_before_setup_stopped(candidate),
        _error_absent_from_baseline(admitted, absent, baseline),
        _no_environment_refusal(candidate, baseline),
    )
    attributed = all(r.holds for r in readings)
    return SetupAttribution(
        scenario_id=str(scenario.get("scenario_id") or ""),
        readings=readings,
        errors=absent if attributed else (),
    )


def _baseline_setup_met(
    scenario: Mapping[str, Any], baseline: Mapping[str, Any] | None
) -> ConditionReading:
    condition = Condition.BASELINE_SETUP_MET
    if baseline is None:
        return ConditionReading(condition, False, "the cycle holds no baseline reading of it")
    frozen = (baseline.get("scenario") or {}).get("digest")
    if not frozen or frozen != scenario.get("digest"):
        return ConditionReading(
            condition,
            False,
            f"the baseline reading is of scenario digest {frozen!r}, and the candidate's is "
            f"{scenario.get('digest')!r}",
        )
    if baseline.get("status") != OperationStatus.COMPLETED.value:
        return ConditionReading(
            condition, False, f"the baseline's play is {baseline.get('status')!r}"
        )
    outcomes = _outcomes(baseline)
    not_met = sorted(
        o for o in outcomes if o not in (AssertionOutcome.PASSED, AssertionOutcome.FAILED)
    )
    if not outcomes or not_met:
        return ConditionReading(
            condition,
            False,
            "the baseline's assertions didn't all execute: " + (", ".join(not_met) or "none read"),
        )
    return ConditionReading(
        condition, True, f"every assertion executed on the baseline, scenario digest {frozen}"
    )


def _same_environment(
    candidate: Mapping[str, Any], baseline: Mapping[str, Any] | None
) -> ConditionReading:
    condition = Condition.SAME_ENVIRONMENT
    if baseline is None:
        return ConditionReading(condition, False, "no baseline reading to compare with")
    differs = []
    shared = []
    for key in (RAN_WITH_ENVIRONMENT, RAN_WITH_SERVED_BY):
        ours = (candidate.get("ran_with") or {}).get(key)
        theirs = (baseline.get("ran_with") or {}).get(key)
        if not ours or not theirs:
            differs.append(f"{key} is unnamed on {'the candidate' if not ours else 'the baseline'}")
        elif ours != theirs:
            differs.append(f"{key} is {theirs!r} on the baseline and {ours!r} on the candidate")
        else:
            shared.append(f"{key} {ours}")
    if differs:
        return ConditionReading(condition, False, "; ".join(differs))
    return ConditionReading(condition, True, "both plays: " + ", ".join(shared))


def _error_in_changed_footprint_file(
    named: tuple[ScriptError, ...],
    admitted: tuple[ScriptError, ...],
    changed: Collection[str],
    in_footprint: Callable[[str], bool],
) -> ConditionReading:
    condition = Condition.ERROR_IN_CHANGED_FOOTPRINT_FILE
    if not named:
        return ConditionReading(condition, False, "the candidate's provider named no script error")
    if not admitted:
        why = "; ".join(
            f"{e.path} ("
            + ("unchanged by the candidate" if e.path not in changed else "outside the footprint")
            + ")"
            for e in named
        )
        return ConditionReading(condition, False, f"no named error is in a changed file: {why}")
    return ConditionReading(
        condition,
        True,
        "; ".join(f"{e.path} line {e.line}, changed and inside the footprint" for e in admitted),
    )


def _error_before_setup_stopped(candidate: Mapping[str, Any]) -> ConditionReading:
    condition = Condition.ERROR_BEFORE_SETUP_STOPPED
    outcomes = _outcomes(candidate)
    others = sorted(o for o in outcomes if o != AssertionOutcome.SETUP_FAILED.value)
    if others:
        return ConditionReading(
            condition,
            False,
            "the play went past its setup (it also read " + ", ".join(others) + "), so its log "
            "was read later than the setup's stop",
        )
    return ConditionReading(
        condition,
        True,
        "every assertion reads setup_failed: the play stopped at its setup, where its provider "
        "read the log",
    )


def _error_absent_from_baseline(
    admitted: tuple[ScriptError, ...],
    absent: tuple[ScriptError, ...],
    baseline: Mapping[str, Any] | None,
) -> ConditionReading:
    condition = Condition.ERROR_ABSENT_FROM_BASELINE
    if baseline is None:
        return ConditionReading(condition, False, "no baseline reading to compare with")
    if "script_errors" not in baseline:
        return ConditionReading(
            condition,
            False,
            "the baseline reading was kept before readings named script errors, so it can't "
            "say it had none",
        )
    if not admitted:
        return ConditionReading(condition, False, "no error to compare")
    if len(absent) != len(admitted):
        also = sorted({e.path for e in admitted} - {e.path for e in absent})
        return ConditionReading(
            condition, False, "the baseline's play named the same error in " + ", ".join(also)
        )
    return ConditionReading(
        condition, True, f"the baseline's play named none of the {len(admitted)} error(s)"
    )


def _no_environment_refusal(
    candidate: Mapping[str, Any], baseline: Mapping[str, Any] | None
) -> ConditionReading:
    condition = Condition.NO_ENVIRONMENT_REFUSAL
    for side, reading in (("candidate", candidate), ("baseline", baseline)):
        if reading is None:
            continue
        for flag in ("tool_unready", "unavailable"):
            if reading.get(flag) is not False:
                return ConditionReading(
                    condition, False, f"the {side}'s reading has {flag} {reading.get(flag)!r}"
                )
        if reading.get("status") != OperationStatus.COMPLETED.value:
            return ConditionReading(
                condition, False, f"the {side}'s play is {reading.get('status')!r}"
            )
    return ConditionReading(
        condition, True, "both plays completed, and neither was refused for its worker"
    )


def _outcomes(reading: Mapping[str, Any]) -> list[str]:
    return [
        str(a.get("outcome")) for a in reading.get("assertions") or () if isinstance(a, Mapping)
    ]


def _script_errors(reading: Mapping[str, Any]) -> tuple[ScriptError, ...]:
    """A reading's script errors. One that isn't a path, a line and a message is dropped: a
    record this can't read attributes nothing."""
    errors = []
    for raw in reading.get("script_errors") or ():
        if (
            isinstance(raw, Mapping)
            and isinstance(raw.get("path"), str)
            and raw["path"]
            and isinstance(raw.get("line"), int)
            and not isinstance(raw.get("line"), bool)
            and isinstance(raw.get("message"), str)
        ):
            errors.append(ScriptError(raw["path"], raw["line"], raw["message"]))
    return tuple(errors)
