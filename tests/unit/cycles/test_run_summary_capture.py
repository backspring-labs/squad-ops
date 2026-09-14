"""SIP-0108 §4.1/§4.2 — each correction round's classified failure and each absent emission,
captured on the run summary.

Each test names what it catches: a round's category or locus read from anything but the
evidence the round was diagnosed from, an absent emission counted as a row that says nothing, or
a row written before the capture read as a run that had none.
"""

from __future__ import annotations

import pytest

from squadops.cycles.failure_evidence import FailureEvidenceCategory, FailureLocus
from squadops.cycles.llm_usage import RunUsage
from squadops.cycles.run_loop_summary import AbsentEmission, RoundFailure, RunLoopSummary

pytestmark = [pytest.mark.domain_orchestration]

_USAGE = RunUsage(by_task_type={}, tasks_reported=0, tasks_unreported=())


class TestTheStoredShape:
    def test_both_records_survive_the_row(self):
        summary = RunLoopSummary(
            run_id="run_1",
            usage=_USAGE,
            round_failures=(
                RoundFailure(
                    task_id="t-qa",
                    round_index=1,
                    category=FailureEvidenceCategory.EXECUTED_AND_FAILED,
                    locus=FailureLocus.SUBJECT,
                    failed_checks=("acceptance:additive_containment", "tests_pass"),
                ),
            ),
            absent_emissions=(
                AbsentEmission(task_id="t-build", signatures=("cap_exhausted",), attempt=2),
                AbsentEmission(task_id="t-qa", round_index=0),
            ),
        )

        assert RunLoopSummary.from_dict(summary.to_dict()) == summary

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [(None, None), ([], ()), ("absent", None)],
        ids=["null", "empty", "row predates the field"],
    )
    def test_a_row_without_the_capture_reads_none_and_an_empty_one_reads_empty(
        self, stored, expected
    ):
        """Bug caught: a row written before the capture read as "no failed rounds" — the
        attribution would then call a correction-terminated run's contributors none."""
        row = RunLoopSummary(run_id="run_1", usage=_USAGE).to_dict()
        for key in ("round_failures", "absent_emissions"):
            if stored == "absent":
                row.pop(key)
            else:
                row[key] = stored

        read = RunLoopSummary.from_dict(row)

        assert (read.round_failures, read.absent_emissions) == (expected, expected)


class TestFromEvidence:
    @pytest.mark.parametrize(
        ("evidence", "expected"),
        [
            (
                {
                    "validation_result": {
                        "checks": [
                            {
                                "check": "tests_pass",
                                "status": "failed",
                                "passed": False,
                                "executed": True,
                                "exit_code": 1,
                                "suite_broken": False,
                            },
                            {"check": "acceptance:file_exists", "status": "passed", "passed": True},
                            {"check": "acceptance:lint", "status": "failed", "passed": True},
                        ]
                    }
                },
                (
                    FailureEvidenceCategory.EXECUTED_AND_FAILED,
                    FailureLocus.SUBJECT,
                    None,
                    ("tests_pass",),
                ),
            ),
            (
                {
                    "emission_failure": {
                        "reason": "no_fenced_blocks",
                        "signature": "cap_exhausted",
                    }
                },
                (
                    FailureEvidenceCategory.EMISSION_ABSENT,
                    FailureLocus.OWN_ARTIFACT,
                    "cap_exhausted",
                    (),
                ),
            ),
        ],
        ids=["the suite ran and the app failed it", "the producer emitted nothing"],
    )
    def test_the_round_reads_the_evidence_classifiers(self, evidence, expected):
        """Bug caught: an advisory row (``passed: True``) counted as a failed check, or the
        locus and category taken from anywhere but the classifiers routing already uses."""
        from squadops.cycles.failure_evidence import derive_failure_category

        evidence = {**evidence, "failure_category": derive_failure_category(evidence)}

        record = RoundFailure.from_evidence("t-qa", 0, evidence)

        assert (
            record.category,
            record.locus,
            record.emission_signature,
            record.failed_checks,
        ) == expected
