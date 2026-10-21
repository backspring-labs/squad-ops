"""The inherited baseline's vocabulary and record (SIP-0112 FR-20, §8.3.1; E.4.2)."""

from types import SimpleNamespace

import pytest

from squadops.projects.baseline import (
    FAIL,
    INHERITED,
    INTRODUCED,
    PASS,
    RESOLVED,
    UNVERIFIED,
    UNVERIFIED_ATTRIBUTION,
    BaselineInvalid,
    CheckResult,
    attribute,
    missing_environment,
    parse_baseline,
    result_of,
)
from squadops.projects.development_configuration import Check
from squadops.projects.verification import SourceVerification
from tests.fixtures.shared_contract.repository import recorded

CHECK = Check("unit", ("python3", "-m", "unittest"))


def _run(**fields):
    base = {
        "ran": True,
        "outcome": "exited",
        "exit_code": 0,
        "duration_seconds": 1.0,
        "stdout_tail": "",
        "stderr_tail": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "unavailable_reason": None,
    }
    return SimpleNamespace(**{**base, **fields})


@pytest.mark.parametrize(
    ("run", "result", "reason"),
    [
        (_run(exit_code=0), "PASS", None),
        (_run(exit_code=1), "FAIL", None),
        (_run(outcome="timeout", exit_code=None), "UNVERIFIED", "timed out"),
        (
            _run(outcome="command_not_found", exit_code=127),
            "UNVERIFIED",
            "its command was not found in the sandbox's image",
        ),
        (
            _run(outcome="setup_failed", exit_code=None),
            "UNVERIFIED",
            "a setup step failed before it ran",
        ),
        (
            _run(ran=False, outcome=None, exit_code=None, unavailable_reason="noop sandbox"),
            "UNVERIFIED",
            "not run: noop sandbox",
        ),
    ],
    ids=["passed", "failed", "timeout", "not-found", "setup", "not-run"],
)
def test_a_runs_outcome_maps_onto_the_vocabulary(run, result, reason):
    """§8.3.1. Bugs caught: a missing tool (exit 127) or a timeout recorded as an inherited
    FAIL, which E.4.3 would then excuse in a candidate; a sandbox that ran nothing credited."""
    mapped = result_of(CHECK, run)

    assert (mapped.result, mapped.reason, mapped.attribution) == (result, reason, "inherited")


def test_a_declared_environment_the_sandbox_lacks_is_a_gap_before_anything_runs():
    check = Check("notify", ("python3", "-m", "unittest"), ("TALLY_SMTP_HOST", "TALLY_SMTP_PORT"))

    gap = missing_environment(check, {"TALLY_SMTP_HOST"})

    assert (gap.result, gap.reason) == ("UNVERIFIED", "environment gap: TALLY_SMTP_PORT is not set")
    assert missing_environment(check, {"TALLY_SMTP_HOST", "TALLY_SMTP_PORT"}) is None


def test_the_fixtures_recorded_baseline_reads_back_and_its_bad_forms_are_refused():
    valid = recorded("inherited_baseline", "valid")

    assert parse_baseline(valid).to_document() == valid
    assert parse_baseline(valid).failing() == ["parse"]
    for form, message in [("unknown_major", "schema"), ("missing_field", "commit is required")]:
        with pytest.raises(BaselineInvalid, match=message):
            parse_baseline(recorded("inherited_baseline", form))
    stale = parse_baseline(recorded("inherited_baseline", "stale_commit"))
    assert stale.commit != parse_baseline(valid).commit


@pytest.mark.parametrize(
    ("before", "after", "attribution"),
    [
        (PASS, PASS, INHERITED),
        (FAIL, FAIL, INHERITED),
        (PASS, FAIL, INTRODUCED),
        (FAIL, PASS, RESOLVED),
        (UNVERIFIED, PASS, UNVERIFIED_ATTRIBUTION),
        (UNVERIFIED, FAIL, UNVERIFIED_ATTRIBUTION),
        (PASS, UNVERIFIED, UNVERIFIED_ATTRIBUTION),
        (None, FAIL, UNVERIFIED_ATTRIBUTION),
    ],
)
def test_a_candidates_check_is_attributed_against_the_baselines(before, after, attribution):
    """FR-20. Bugs caught: an inherited failure read as one the change introduced; a check the
    baseline couldn't run credited either way; the candidate's result rewritten by the
    comparison (an inherited FAIL is still a FAIL)."""
    baseline = CheckResult("unit", before) if before else None

    got = attribute(CheckResult("unit", after), baseline)

    assert (got.result, got.attribution) == (after, attribution)


@pytest.mark.parametrize(
    ("results", "verdict"),
    [
        ([(PASS, INHERITED), (FAIL, INHERITED)], "accepted"),
        ([(PASS, INHERITED), (FAIL, INTRODUCED)], "regressed"),
        ([(PASS, UNVERIFIED_ATTRIBUTION), (FAIL, UNVERIFIED_ATTRIBUTION)], "regressed"),
        ([(FAIL, INHERITED), (UNVERIFIED, UNVERIFIED_ATTRIBUTION)], "unverified"),
        ([], "unverified"),
    ],
    ids=[
        "inherited-failure",
        "introduced",
        "unattributable-failure",
        "nothing-passed",
        "no-checks",
    ],
)
def test_2_4s_acceptance_policy(results, verdict):
    """Bugs caught: an inherited failure blocking scoped work; a failure whose origin can't be
    told waved through; a candidate approved on no executed evidence at all."""
    verification = SourceVerification(
        project_id="p",
        cycle_id="c",
        run_id="r",
        baseline_commit="0" * 40,
        development_configuration_revision=1,
        candidate_revision_id="x",
        candidate_tree_identity="t",
        changed_paths=("a.py",),
        environment={},
        checks=tuple(CheckResult(f"c{i}", r, a) for i, (r, a) in enumerate(results)),
    )

    assert verification.verdict == verdict
