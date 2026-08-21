"""Gate 5's exit corpus: routing per class, correlation grouped-not-collapsed, report fields.

Every case runs against the REAL emission and REAL merged shells, with observation rows in
the measured vitest shapes (bare chai messages, location.line) — the same rows the runner's
JSON report produces in production.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.test_runner import parse_vitest_failure_rows
from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from squadops.capabilities.verification_scaffold_fill import merge_fills, parse_fill_emission
from squadops.cycles.scaffold_evidence import (
    CLASS_APP_CONTRACT,
    CLASS_FILL,
    CLASS_INFRASTRUCTURE,
    CLASS_SCAFFOLD_INVALID,
    ShellObservation,
    build_scaffold_evidence_summary,
    classify_shell_failures,
    correlate,
)
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_contracts]

_CREATE_SHELL = "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"
_LIST_SHELL = "__tests__/scaffold/vs-get-api-runs.scaffold.test.ts"


@pytest.fixture(scope="module")
def emission():
    return emit_verification_scaffold(manifest_for_stack("nextjs_ts"))


@pytest.fixture(scope="module")
def merged(emission):
    """The create shell filled; every other slot missing (its injected failing state)."""
    return merge_fills(
        list(emission.files),
        emission.manifest,
        parse_fill_emission(
            "```fill:slot-vc-probe-api-runs\n    expect(body.title).toBe('sample')\n```\n"
        ),
    )


@pytest.fixture(scope="module")
def merged_contents(merged):
    return {f.path: f.content for f in merged.files}


@pytest.fixture(scope="module")
def dispositions(merged):
    return {d.slot_id: d.disposition for d in merged.dispositions}


def _line_of(content: str, needle: str) -> int:
    return next(i for i, line in enumerate(content.split("\n"), start=1) if needle in line)


def _classify(emission, merged_contents, dispositions, rows, executed=True):
    return classify_shell_failures(
        rows, merged_contents, emission.manifest, dispositions, runner_executed=executed
    )


class TestRoutingPerClass:
    def test_a_spine_status_failure_is_app_contract_routed_to_dev(
        self, emission, merged_contents, dispositions
    ):
        line = _line_of(merged_contents[_CREATE_SHELL], "expect(res.status).toBe(201)")
        rows = [
            {
                "file": _CREATE_SHELL,
                "title": "POST /api/runs -> 201 [vc-probe-api-runs]",
                "messages": ["expected 500 to be 201 // Object.is equality"],
                "line": line,
                "suite_level": False,
            }
        ]
        (obs,) = _classify(emission, merged_contents, dispositions, rows)
        assert obs.failure_class == CLASS_APP_CONTRACT
        assert obs.criterion_id == "vc-probe-api-runs"  # the correlation join key
        assert obs.to_dict()["owner"] == "dev"
        assert obs.to_dict()["route"] == "dev_repair"

    def test_a_fill_assertion_failure_is_fill_class_slot_scoped_to_qa(
        self, emission, merged_contents, dispositions
    ):
        line = _line_of(merged_contents[_CREATE_SHELL], "expect(body.title).toBe('sample')")
        rows = [
            {
                "file": _CREATE_SHELL,
                "title": "POST /api/runs -> 201 [vc-probe-api-runs]",
                "messages": ["expected undefined to be 'sample'"],
                "line": line,
                "suite_level": False,
            }
        ]
        (obs,) = _classify(emission, merged_contents, dispositions, rows)
        assert obs.failure_class == CLASS_FILL
        assert obs.slot_id == "slot-vc-probe-api-runs"
        assert obs.criterion_id == ""  # fill failures never join probe correlation
        assert obs.to_dict()["owner"] == "qa"
        assert obs.to_dict()["route"] == "qa_repair_slot_scoped"

    def test_a_missing_slots_injected_failing_state_is_fill_class(
        self, emission, merged_contents, dispositions
    ):
        """The P3 missing-slot rule ends here: the injected expect() line sits inside the
        region, so its failure attributes to the fill layer with the disposition named."""
        line = _line_of(merged_contents[_LIST_SHELL], "expect('fill layer: slot-vs-get-api-runs")
        rows = [
            {
                "file": _LIST_SHELL,
                "title": "GET /api/runs -> 200 [vs-get-api-runs]",
                "messages": ["expected 'fill layer: …' to be 'a valid fill …'"],
                "line": line,
                "suite_level": False,
            }
        ]
        (obs,) = _classify(emission, merged_contents, dispositions, rows)
        assert obs.failure_class == CLASS_FILL
        assert "missing" in obs.detail

    def test_a_mechanical_death_of_a_filled_shell_is_fill_class(
        self, emission, merged_contents, dispositions
    ):
        rows = [
            {
                "file": _CREATE_SHELL,
                "title": "",
                "messages": ["Transform failed with 1 error:"],
                "line": None,
                "suite_level": True,
            }
        ]
        (obs,) = _classify(emission, merged_contents, dispositions, rows)
        assert obs.failure_class == CLASS_FILL
        assert "merged fill broke the shell" in obs.detail

    def test_a_mechanical_death_of_an_unfilled_shell_is_scaffold_invalid(
        self, emission, merged_contents, dispositions
    ):
        """The P6 window rule's subject: a spine that dies with no fill merged is a NEW
        uncovered generator surface — named, never sent to an LLM round."""
        rows = [
            {
                "file": _LIST_SHELL,
                "title": "GET /api/runs -> 200 [vs-get-api-runs]",
                "messages": ["Requests is not defined"],
                "line": None,
                "suite_level": False,
            }
        ]
        (obs,) = _classify(emission, merged_contents, dispositions, rows)
        assert obs.failure_class == CLASS_SCAFFOLD_INVALID
        assert "uncovered generator surface" in obs.detail
        assert obs.to_dict()["route"] == "name_uncovered_surface_no_llm_round"

    def test_a_runner_that_could_not_execute_is_infrastructure(
        self, emission, merged_contents, dispositions
    ):
        (obs,) = _classify(emission, merged_contents, dispositions, [], executed=False)
        assert obs.failure_class == CLASS_INFRASTRUCTURE
        assert obs.to_dict()["owner"] == "environment"

    def test_non_shell_failures_pass_through_unclassified(
        self, emission, merged_contents, dispositions
    ):
        rows = [
            {
                "file": "__tests__/extra.test.ts",
                "title": "t",
                "messages": ["expected 1 to be 2"],
                "line": 3,
                "suite_level": False,
            }
        ]
        assert _classify(emission, merged_contents, dispositions, rows) == []

    def test_an_assertion_failure_without_line_info_falls_to_app_contract(
        self, emission, merged_contents, dispositions
    ):
        """Ambiguity falls toward the dev/subject direction (the test-gaming guard's
        side): qa must never be invited to rewrite the suite on an ambiguous signal."""
        rows = [
            {
                "file": _CREATE_SHELL,
                "title": "t",
                "messages": ["expected 500 to be 201"],
                "line": None,
                "suite_level": False,
            }
        ]
        (obs,) = _classify(emission, merged_contents, dispositions, rows)
        assert obs.failure_class == CLASS_APP_CONTRACT


class TestCorrelation:
    def _shell_obs(self, criterion="vc-probe-api-runs"):
        return ShellObservation(
            file=_CREATE_SHELL,
            slot_id="slot-vc-probe-api-runs",
            failure_class=CLASS_APP_CONTRACT,
            criterion_id=criterion,
        )

    def test_shared_criterion_groups_both_observations_retained(self):
        """The §5 dedup rule: ONE defect observed twice — grouped, both retained, never
        collapsed into a single observation."""
        probe_row = {
            "check": "vc-probe-api-runs",
            "criterion_id": "vc-probe-api-runs",
            "status": "failed",
            "reason": "status 500 != 201",
        }
        findings = correlate([self._shell_obs()], [probe_row])
        assert len(findings) == 1
        finding = findings[0]
        assert len(finding.shell_observations) == 1
        assert len(finding.probe_failures) == 1  # both sides retained in full
        assert finding.probe_redundant

    def test_different_criterion_ids_are_never_merged(self):
        findings = correlate(
            [self._shell_obs("vc-probe-api-runs"), self._shell_obs("vc-probe-api-runs-join")],
            [],
        )
        assert [f.criterion_id for f in findings] == [
            "vc-probe-api-runs",
            "vc-probe-api-runs-join",
        ]

    def test_a_probe_only_failure_manufactures_no_finding(self):
        probe_row = {"criterion_id": "vc-probe-api-runs", "status": "failed"}
        assert correlate([], [probe_row]) == []

    def test_a_shell_only_finding_is_not_probe_redundant(self):
        findings = correlate([self._shell_obs()], [{"criterion_id": "other", "status": "failed"}])
        assert len(findings) == 1
        assert not findings[0].probe_redundant

    def test_passing_probe_rows_never_join(self):
        probe_row = {"criterion_id": "vc-probe-api-runs", "status": "pass"}
        findings = correlate([self._shell_obs()], [probe_row])
        assert findings[0].probe_failures == ()


class TestSummary:
    def test_the_report_fields_are_present_and_counted(self, emission, dispositions):
        observations = [
            ShellObservation(
                file=_CREATE_SHELL,
                slot_id="slot-vc-probe-api-runs",
                failure_class=CLASS_APP_CONTRACT,
                criterion_id="vc-probe-api-runs",
            ),
            ShellObservation(
                file=_LIST_SHELL, slot_id="slot-vs-get-api-runs", failure_class=CLASS_FILL
            ),
        ]
        correlations = correlate(
            observations,
            [{"criterion_id": "vc-probe-api-runs", "status": "failed"}],
        )
        summary = build_scaffold_evidence_summary(
            emission.manifest, dispositions, observations, correlations, additive_test_count=2
        )
        d = summary.to_dict()
        # the promotion model's fields (SIP §6/§12) — schema preserved, workflow not built
        assert d["stack"] == "nextjs_ts" and d["generator_version"] == 5
        assert d["shell_count"] == 8 and d["slot_count"] == 8
        assert d["fill_dispositions"] == {"filled": 1, "missing": 7}
        assert d["additive_test_count"] == 2
        assert d["failure_classes"] == {CLASS_APP_CONTRACT: 1, CLASS_FILL: 1}
        assert d["uncorrelated_fill_failures"] == 1
        assert d["probe_redundant_findings"] == 1
        assert d["observations"][0]["owner"] == "dev"
        assert d["correlations"][0]["criterion_id"] == "vc-probe-api-runs"


class TestObservationParser:
    def test_rows_from_a_vitest_report_are_relative_and_shaped(self):
        report = {
            "testResults": [
                {
                    "name": f"/ws/{_CREATE_SHELL}",
                    "status": "failed",
                    "message": "",
                    "assertionResults": [
                        {
                            "status": "failed",
                            "title": "POST /api/runs -> 201",
                            "failureMessages": ["expected 500 to be 201 // Object.is equality"],
                            "location": {"line": 21, "column": 24},
                        },
                        {"status": "passed", "title": "other", "failureMessages": []},
                    ],
                },
                {
                    "name": f"/ws/{_LIST_SHELL}",
                    "status": "failed",
                    "message": "Failed to resolve import '@/app/api/run/route'",
                    "assertionResults": [],
                },
            ]
        }
        rows = parse_vitest_failure_rows(report, "/ws")
        assert rows == [
            {
                "file": _CREATE_SHELL,
                "title": "POST /api/runs -> 201",
                "messages": ["expected 500 to be 201 // Object.is equality"],
                "line": 21,
                "suite_level": False,
            },
            {
                "file": _LIST_SHELL,
                "title": "",
                "messages": ["Failed to resolve import '@/app/api/run/route'"],
                "line": None,
                "suite_level": True,
            },
        ]

    def test_a_passing_report_yields_no_rows(self):
        report = {
            "testResults": [
                {
                    "name": "/ws/a.test.ts",
                    "status": "passed",
                    "assertionResults": [{"status": "passed"}],
                }
            ]
        }
        assert parse_vitest_failure_rows(report, "/ws") == []


class TestUncollectedTestFiles:
    """SIP-0104 roll 1 (cyc_04d36309d793): qa authored ~9KB at `tests/api/runs.test.ts`,
    outside the stack's `**/__tests__/**/*.test.ts` include — 9 files handed in, 8
    collected, and the surrounding suite read green. Silent non-coverage of the authored
    layer is the #884 class one step down, and nothing reported it."""

    _REPORT = {
        "testResults": [
            {"name": "/ws/__tests__/scaffold/a.scaffold.test.ts", "status": "passed"},
            {"name": "/ws/__tests__/extra.test.ts", "status": "passed"},
        ]
    }

    def test_a_runnable_suite_the_runner_ignored_is_named(self):
        from squadops.capabilities.handlers.test_runner import uncollected_test_files

        handed_in = [
            "__tests__/scaffold/a.scaffold.test.ts",
            "__tests__/extra.test.ts",
            "tests/api/runs.test.ts",  # outside the include → never collected
        ]
        assert uncollected_test_files(self._REPORT, "/ws", handed_in) == ["tests/api/runs.test.ts"]

    def test_a_non_test_helper_is_not_flagged(self):
        """A helper module beside the suite is legitimately uncollected; only files that
        declare themselves suites (`*.test.ts` / `*.spec.ts`) are."""
        from squadops.capabilities.handlers.test_runner import uncollected_test_files

        handed_in = ["__tests__/helpers/factory.ts", "__tests__/extra.test.ts"]
        assert uncollected_test_files(self._REPORT, "/ws", handed_in) == []

    def test_everything_collected_reports_nothing(self):
        from squadops.capabilities.handlers.test_runner import uncollected_test_files

        handed_in = ["__tests__/scaffold/a.scaffold.test.ts", "__tests__/extra.test.ts"]
        assert uncollected_test_files(self._REPORT, "/ws", handed_in) == []

    def test_the_summary_banks_it(self, emission, dispositions):
        summary = build_scaffold_evidence_summary(
            emission.manifest,
            dispositions,
            [],
            [],
            additive_test_count=1,
            uncollected_test_files=("tests/api/runs.test.ts",),
        )
        assert summary.to_dict()["uncollected_test_files"] == ["tests/api/runs.test.ts"]
