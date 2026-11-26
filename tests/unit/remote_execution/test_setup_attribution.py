"""SIP-0117 R5.32 (#3200): a candidate's setup failure is attributed to the candidate only when
all six conditions hold. Each reading here is built by ``records_document`` from a request and a
result, as every lane that keeps a reading builds it."""

from __future__ import annotations

import dataclasses
from fnmatch import fnmatch

import pytest

from squadops.remote_execution.models import (
    AssertionOutcome,
    AssertionRecord,
    OperationStatus,
    ReadingSide,
    RemoteOperationResult,
    ScriptError,
    records_document,
)
from squadops.remote_execution.setup_attribution import Condition, attribute, setup_failed
from tests.unit.remote_execution.registry_contract import request

SCREEN = "src/client/screen.luau"
ERROR = ScriptError(SCREEN, 12, "Shown is not a valid member of Panel")
RAN_WITH = {"environment": "env-1", "served_by": "worker-a", "play_session": "s"}
FOOTPRINT = ("src/client/**",)


def _in_footprint(path: str) -> bool:
    return any(fnmatch(path, glob) for glob in FOOTPRINT)


def _result(outcome: AssertionOutcome, *errors: ScriptError, **changes) -> RemoteOperationResult:
    result = RemoteOperationResult(
        status=OperationStatus.COMPLETED,
        records=tuple(
            AssertionRecord(a, outcome, "", "", "client") for a in request().scenario.assertions
        ),
        ran_with=dict(RAN_WITH),
        script_errors=tuple(errors),
        dispatch_id="dispatch-1",
    )
    return dataclasses.replace(result, **changes)


def _reading(side: ReadingSide, result: RemoteOperationResult, **scenario) -> dict:
    asked = request()
    asked = dataclasses.replace(
        asked,
        source_files={**asked.source_files, SCREEN: "return {}\n"},
        scenario=dataclasses.replace(asked.scenario, **scenario),
    )
    return records_document(asked, result, side, not_staged=())


def _candidate(**changes) -> dict:
    return _reading(ReadingSide.CANDIDATE, _result(AssertionOutcome.SETUP_FAILED, ERROR, **changes))


def _baseline(*errors: ScriptError, **changes) -> dict:
    return _reading(ReadingSide.BASELINE, _result(AssertionOutcome.FAILED, *errors, **changes))


def _attribute(candidate=None, baseline=None, *, changed=(SCREEN,), no_baseline=False):
    return attribute(
        candidate if candidate is not None else _candidate(),
        None if no_baseline else (baseline if baseline is not None else _baseline()),
        changed=frozenset(changed),
        in_footprint=_in_footprint,
    )


def _failing(attribution) -> dict[Condition, str]:
    return {r.condition: r.evidence for r in attribution.readings if not r.holds}


def test_an_error_in_a_changed_file_the_baseline_never_raised_is_the_candidates():
    attribution = _attribute()

    assert attribution.attributed is True
    assert attribution.errors == (ERROR,)
    assert [r.condition for r in attribution.readings] == list(Condition)
    assert attribution.repair_evidence() == (
        "src/client/screen.luau line 12: Shown is not a valid member of Panel"
    )
    document = attribution.document(baseline_reading="art_base", candidate_revision="rev_c")
    assert (document["attributed"], document["baseline_reading"], document["errors"]) == (
        True,
        "art_base",
        [{"path": SCREEN, "line": 12, "message": "Shown is not a valid member of Panel"}],
    )
    assert [c["holds"] for c in document["conditions"]] == [True] * 6


def _unrelated() -> ScriptError:
    return ScriptError("src/server/init.luau", 3, "attempt to index nil")


@pytest.mark.parametrize(
    ("kwargs", "condition", "evidence"),
    [
        (
            {"no_baseline": True},
            Condition.BASELINE_SETUP_MET,
            "the cycle holds no baseline reading of it",
        ),
        (
            {
                "baseline": _reading(
                    ReadingSide.BASELINE, _result(AssertionOutcome.FAILED), digest="sha256:other"
                )
            },
            Condition.BASELINE_SETUP_MET,
            "the baseline reading is of scenario digest 'sha256:other'",
        ),
        (
            {"baseline": _reading(ReadingSide.BASELINE, _result(AssertionOutcome.SETUP_FAILED))},
            Condition.BASELINE_SETUP_MET,
            "the baseline's assertions didn't all execute: setup_failed",
        ),
        (
            {"baseline": _baseline(ran_with={**RAN_WITH, "environment": "env-2"})},
            Condition.SAME_ENVIRONMENT,
            "environment is 'env-2' on the baseline and 'env-1' on the candidate",
        ),
        (
            {"baseline": _baseline(ran_with={**RAN_WITH, "served_by": "worker-b"})},
            Condition.SAME_ENVIRONMENT,
            "served_by is 'worker-b' on the baseline and 'worker-a' on the candidate",
        ),
        (
            {"candidate": _candidate(ran_with={"served_by": "worker-a"})},
            Condition.SAME_ENVIRONMENT,
            "environment is unnamed on the candidate",
        ),
        (
            {"candidate": _candidate(script_errors=())},
            Condition.ERROR_IN_CHANGED_FOOTPRINT_FILE,
            "the candidate's provider named no script error",
        ),
        (
            {"changed": ()},
            Condition.ERROR_IN_CHANGED_FOOTPRINT_FILE,
            "no named error is in a changed file: src/client/screen.luau (unchanged by the "
            "candidate)",
        ),
        (
            {
                "candidate": _candidate(script_errors=(_unrelated(),)),
                "changed": ("src/server/init.luau",),
            },
            Condition.ERROR_IN_CHANGED_FOOTPRINT_FILE,
            "no named error is in a changed file: src/server/init.luau (outside the footprint)",
        ),
        (
            {"baseline": _baseline(ERROR)},
            Condition.ERROR_ABSENT_FROM_BASELINE,
            "the baseline's play named the same error in src/client/screen.luau",
        ),
        (
            {"candidate": _candidate(tool_unready=False, unavailable=True)},
            Condition.NO_ENVIRONMENT_REFUSAL,
            "the candidate's reading has unavailable True",
        ),
    ],
    ids=[
        "1: no baseline reading",
        "1: a baseline of another frozen scenario",
        "1: the baseline's setup failed too",
        "2: another environment",
        "2: another worker",
        "2: an environment nobody named",
        "3: no error named",
        "3: the error is in a file the candidate didn't change",
        "3: the error is outside the footprint",
        "5: the baseline raised it too",
        "6: no worker took the candidate's play",
    ],
)
def test_each_condition_failing_alone_attributes_nothing(kwargs, condition, evidence):
    """Bug caught: a rule that attributes on the setup failure and the console alone, so a slow
    tool, another worker's place or an error the baseline already had sends the run to repair
    a candidate nothing faulted."""
    attribution = _attribute(**kwargs)

    assert attribution.attributed is False
    assert attribution.errors == ()
    failing = _failing(attribution)
    assert condition in failing
    assert failing[condition].startswith(evidence)


def test_a_play_that_went_past_its_setup_read_its_log_too_late():
    """Condition 4. One assertion executed, so the play didn't stop at its setup and the log
    was read after later steps ran."""
    result = _result(AssertionOutcome.SETUP_FAILED, ERROR)
    first, *rest = result.records
    mixed = dataclasses.replace(
        result, records=(dataclasses.replace(first, outcome=AssertionOutcome.PASSED), *rest)
    )

    attribution = _attribute(candidate=_reading(ReadingSide.CANDIDATE, mixed))

    assert _failing(attribution) == {
        Condition.ERROR_BEFORE_SETUP_STOPPED: (
            "the play went past its setup (it also read passed), so its log was read later "
            "than the setup's stop"
        )
    }


@pytest.mark.parametrize(
    ("strip", "condition", "evidence"),
    [
        (
            "script_errors",
            Condition.ERROR_ABSENT_FROM_BASELINE,
            "the baseline reading was kept before readings named script errors",
        ),
        (
            "tool_unready",
            Condition.NO_ENVIRONMENT_REFUSAL,
            "the baseline's reading has tool_unready None",
        ),
    ],
    ids=["a baseline kept before the key", "a baseline that doesn't say whether it was refused"],
)
def test_a_reading_that_cant_say_is_not_read_as_saying_no(strip, condition, evidence):
    """Evidence missing. Bug caught: an older reading's missing key read as "none" or "false",
    so a baseline that never recorded its errors vouches that it had none."""
    baseline = _baseline()
    del baseline[strip]

    failing = _failing(_attribute(baseline=baseline))

    assert failing[condition].startswith(evidence)


@pytest.mark.parametrize(
    "listed",
    [[{"path": SCREEN, "message": "no line"}], "prose", [None], {"path": SCREEN}],
    ids=["an entry with no line", "a string", "a null entry", "an object where a list goes"],
)
def test_script_errors_that_cant_be_read_attribute_nothing_on_either_side(listed):
    """Evidence contradictory, from the MacBook lane's review. Nothing is dropped and read
    around. Bug caught: a baseline whose list holds an entry that doesn't parse (or is a string,
    which iterates as characters) read as naming no such error, so condition 5 holds on a
    record nobody could read."""
    candidate, baseline = _candidate(), _baseline()
    candidate["script_errors"] = listed
    baseline["script_errors"] = listed

    as_candidate = _failing(_attribute(candidate=candidate))
    as_baseline = _failing(_attribute(baseline=baseline))

    assert as_candidate[Condition.ERROR_IN_CHANGED_FOOTPRINT_FILE] == (
        "the candidate's script errors can't be read"
    )
    assert as_baseline == {
        Condition.ERROR_ABSENT_FROM_BASELINE: "the baseline's script errors can't be read"
    }


def test_with_no_baseline_no_condition_claims_to_have_read_one():
    """The kept evidence says only what was read. Bug caught: "both plays completed" written
    for a cycle that holds no baseline reading at all."""
    failing = _failing(_attribute(no_baseline=True))

    assert failing[Condition.NO_ENVIRONMENT_REFUSAL] == "no baseline reading to read it from"
    assert set(failing) == {
        Condition.BASELINE_SETUP_MET,
        Condition.SAME_ENVIRONMENT,
        Condition.ERROR_ABSENT_FROM_BASELINE,
        Condition.NO_ENVIRONMENT_REFUSAL,
    }


@pytest.mark.parametrize(
    ("outcomes", "status", "expected"),
    [
        (("setup_failed", "setup_failed"), "completed", True),
        (("setup_failed", "failed"), "completed", False),
        (("passed", "failed"), "completed", False),
        (("missing", "missing"), "completed", False),
        ((), "not_executed", False),
    ],
    ids=[
        "the setup failed",
        "an executed failure has its own correction",
        "it executed",
        "nothing was recorded",
        "it didn't run",
    ],
)
def test_only_a_play_whose_setup_failed_is_attributed_at_all(outcomes, status, expected):
    reading = {"status": status, "assertions": [{"outcome": o} for o in outcomes]}

    assert setup_failed(reading) is expected
