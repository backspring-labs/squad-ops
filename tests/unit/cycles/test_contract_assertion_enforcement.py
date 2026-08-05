"""#629 (1.5 A6/D2) — contract-assertion enforcement: the blocking, deterministic half.

pf-54 is the exhibit these tests pin: the contract pinned ``POST /runs → 201``
(create probe) and 422 (blank-input probe); all five authored suite versions
asserted 200-on-create — five dev-chain repairs of a contract-correct app were
honestly rejected against a suite the contract says is wrong. The design bound
is zero false positives: a rejection-case assertion is contract-correct, and
anything unextractable or off-contract is out of scope, never a guess.
"""

from __future__ import annotations

import pytest

from squadops.cycles.acceptance_check_spec import (
    CHECK_CONTRACT_ASSERTIONS,
    parse_method_path_status,
)
from squadops.cycles.acceptance_checks import get_check
from squadops.cycles.failure_evidence import FailureLocus, classify_failure_locus
from squadops.cycles.implementation_plan import PlanTask
from squadops.cycles.task_plan import _contract_assertion_criteria
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_contracts]


class TestPinnedStatusGrammar:
    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("POST /runs 201", ("POST", "/runs", 201)),
            ("get /runs/ 200", ("GET", "/runs", 200)),  # normalized, not dropped
            ("POST /runs", None),  # two fields is the OTHER grammar
            ("TELEPORT /runs 200", None),
            ("POST /runs 99", None),  # not an HTTP status
            ("POST /runs abc", None),
            ("", None),
        ],
    )
    def test_parse(self, token, expected):
        # malformed tokens must be inert, not fatal — same tolerance rule as
        # parse_method_path (a bad entry disables itself, not the check)
        assert parse_method_path_status(token) == expected


_PARAMS = {
    "file": "backend/tests/test_runs.py",
    "endpoints": ["POST /runs 201", "POST /runs 422", "GET /runs 200"],
    "allowed_error_statuses": [404, 409, 422],
}


async def _evaluate(tmp_path, source: str, params: dict | None = None):
    suite = tmp_path / "backend" / "tests"
    suite.mkdir(parents=True)
    (suite / "test_runs.py").write_text(source)
    return await get_check(CHECK_CONTRACT_ASSERTIONS).evaluate(
        dict(params or _PARAMS), tmp_path, stack="fastapi"
    )


class TestEvaluator:
    async def test_pf54_exhibit_wrong_create_status_fails(self, tmp_path):
        # the canonical true positive: 200 asserted where the probe pins 201
        outcome = await _evaluate(
            tmp_path,
            "def test_create_run(client):\n"
            '    resp = client.post("/runs", json={"title": "x"})\n'
            "    assert resp.status_code == 200\n",
        )
        assert outcome.status == "failed"
        assert "POST /runs asserts 200" in outcome.reason
        assert "201" in outcome.reason

    async def test_rejection_assertion_is_contract_correct(self, tmp_path):
        # 422 on blank input is PINNED (rejection probe) — flagging it would
        # recreate the unwinnable loop; the per-endpoint union prevents that
        outcome = await _evaluate(
            tmp_path,
            "def test_blank_input(client):\n"
            '    resp = client.post("/runs", json={})\n'
            "    assert resp.status_code == 422\n",
        )
        assert outcome.status == "passed"

    async def test_allowed_error_status_anywhere_is_silent(self, tmp_path):
        # 404 comes from the suite-wide error map, not this endpoint's probes
        outcome = await _evaluate(
            tmp_path,
            "def test_missing(client):\n"
            '    resp = client.get("/runs")\n'
            "    assert resp.status_code == 404\n",
        )
        assert outcome.status == "passed"

    async def test_api_prefixed_pinned_path_fails(self, tmp_path):
        # pf-54: 3 of 5 versions prefixed every call with /api — no pinned
        # match, so the status rule alone is blind while every call 404s
        outcome = await _evaluate(
            tmp_path,
            "def test_create_run(client):\n"
            '    resp = client.post("/api/runs", json={"title": "x"})\n'
            "    assert resp.status_code == 201\n",
        )
        assert outcome.status == "failed"
        assert "undeclared prefix" in outcome.reason

    async def test_direct_call_and_reversed_operands_extract(self, tmp_path):
        outcome = await _evaluate(
            tmp_path,
            'def test_list(client):\n    assert 500 == client.get("/runs").status_code\n',
        )
        assert outcome.status == "failed"
        assert "GET /runs asserts 500" in outcome.reason

    async def test_await_form_extracts(self, tmp_path):
        outcome = await _evaluate(
            tmp_path,
            "async def test_create(client):\n"
            '    resp = await client.post("/runs")\n'
            "    assert resp.status_code == 200\n",
        )
        assert outcome.status == "failed"

    async def test_rebinding_uses_the_latest_call(self, tmp_path):
        # resp is rebound between asserts — each assert reads its own binding
        outcome = await _evaluate(
            tmp_path,
            "def test_flow(client):\n"
            '    resp = client.post("/runs", json={})\n'
            "    assert resp.status_code == 201\n"
            '    resp = client.get("/runs")\n'
            "    assert resp.status_code == 500\n",
        )
        assert outcome.status == "failed"
        assert "GET /runs asserts 500" in outcome.reason
        assert "POST" not in outcome.reason

    async def test_non_contract_paths_and_unextractable_are_out_of_scope(self, tmp_path):
        # off-contract endpoint, variable status, membership test: none is a
        # deterministic contradiction — never a guess (the zero-false-positive bound)
        outcome = await _evaluate(
            tmp_path,
            "def test_misc(client):\n"
            '    assert client.get("/health").status_code == 200\n'
            "    expected = 200\n"
            '    resp = client.post("/runs", json={})\n'
            "    assert resp.status_code == expected\n"
            "    assert resp.status_code in (201, 422)\n",
        )
        assert outcome.status == "passed"

    async def test_syntax_error_skips(self, tmp_path):
        # the syntax gate owns unparseable emissions (#605 sibling semantics)
        outcome = await _evaluate(tmp_path, "def broken(:\n")
        assert outcome.status == "skipped"
        assert outcome.reason == "unsupported_stack_or_syntax"

    async def test_empty_endpoints_param_is_an_evaluator_error(self, tmp_path):
        # injection only fires with pins in hand — an empty set is a contract
        # bug between injector and evaluator (RC-9a), not a pass and not a skip
        outcome = await _evaluate(
            tmp_path,
            "def test_x(client):\n    assert client.get('/runs').status_code == 200\n",
            params={"file": "backend/tests/test_runs.py", "endpoints": ["garbage"]},
        )
        assert outcome.status == "error"
        assert outcome.reason == "invalid_endpoints_param"


def _bound_contract(probes: list[dict] | None = None, coverage: list[str] | None = None):
    return VerificationContract.from_dict(
        {
            "contract_version": 1,
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "a" * 64,
            },
            "capabilities": ["python"],
            "frozen": [{"path": "backend/errors.py", "sha256": "b" * 64}],
            "fill_files": {
                "backend/routes.py": {
                    "interface": [
                        {
                            "check": "endpoint_defined",
                            "id": "vc-routes-endpoints",
                            "methods_paths": ["POST /runs", "GET /runs"],
                        }
                    ],
                    "implementation": [],
                }
            },
            "behavioral": {
                "probes": (
                    probes
                    if probes is not None
                    else [
                        {
                            "id": "p-create",
                            "subject": "backend",
                            "request": {"method": "POST", "path": "/runs"},
                            "expect": {"status": 201},
                        },
                        {
                            "id": "p-blank",
                            "subject": "backend",
                            "request": {"method": "POST", "path": "/runs"},
                            "expect": {"status": 422, "error_code": "validation_error"},
                        },
                        {
                            "id": "p-missing",
                            "subject": "backend",
                            "request": {"method": "GET", "path": "/runs/missing"},
                            "expect": {"status": 404},
                        },
                    ]
                ),
                "suite": {
                    "checks": [],
                    "coverage_expectations": (
                        coverage if coverage is not None else ["duplicate_participant → 409"]
                    ),
                },
            },
        }
    )


def _qa_task(artifacts: list[str]) -> PlanTask:
    return PlanTask(
        task_index=2,
        task_type="qa.test",
        role="qa",
        focus="behavioral suite",
        description="author the suite",
        expected_artifacts=artifacts,
    )


class TestDerivation:
    def test_pinned_statuses_union_per_endpoint(self):
        # create (201) + blank-input rejection (422) probes pin the SAME
        # endpoint: both statuses are contract-correct for POST /runs
        pinned = _bound_contract().pinned_endpoint_statuses()
        assert pinned[("POST", "/runs")] == (201, 422)
        assert pinned[("GET", "/runs/missing")] == (404,)

    def test_allowed_error_statuses_from_probes_and_coverage(self):
        # 4xx probe statuses + statuses named in coverage_expectations prose
        assert _bound_contract().allowed_error_statuses() == (404, 409, 422)

    def test_probeless_contract_derives_nothing(self):
        contract = _bound_contract(probes=[], coverage=[])
        assert contract.pinned_endpoint_statuses() == {}
        assert contract.allowed_error_statuses() == ()


class TestInjection:
    def test_bound_qa_task_gets_one_row_per_suite_file(self):
        rows = _contract_assertion_criteria(
            "qa.test",
            _qa_task(["backend/tests/test_runs.py", "backend/tests/test_events.py", "notes.md"]),
            _bound_contract(),
        )
        assert [r.params["file"] for r in rows] == [
            "backend/tests/test_runs.py",
            "backend/tests/test_events.py",
        ]
        for row in rows:
            assert row.check == CHECK_CONTRACT_ASSERTIONS
            assert row.id == f"contract-assertions:{row.params['file']}"
            assert "POST /runs 201" in row.params["endpoints"]
            assert "POST /runs 422" in row.params["endpoints"]
            assert row.params["allowed_error_statuses"] == [404, 409, 422]

    def test_author_mode_non_qa_and_probeless_inject_nothing(self):
        task = _qa_task(["backend/tests/test_runs.py"])
        assert _contract_assertion_criteria("qa.test", task, None) == []
        assert _contract_assertion_criteria("development.develop", task, _bound_contract()) == []
        assert _contract_assertion_criteria("qa.test", task, _bound_contract(probes=[])) == []


class TestLocusRouting:
    def test_failed_contract_row_routes_own_artifact(self):
        # the frozen contract says the suite is wrong — eve re-authors the
        # suite; the app is never the repair target for this signal
        evidence = {
            "validation_result": {
                "passed": False,
                "checks": [{"check": f"acceptance:{CHECK_CONTRACT_ASSERTIONS}", "passed": False}],
            }
        }
        assert classify_failure_locus(evidence) == FailureLocus.OWN_ARTIFACT

    def test_precedence_over_tests_pass_regardless_of_row_order(self):
        # when the suite both contradicts the contract AND fails, repairing the
        # app against a contract-contradicting suite is the pf-54 budget burn —
        # the earlier tests_pass row must not win by position
        evidence = {
            "validation_result": {
                "passed": False,
                "checks": [
                    {
                        "check": "tests_pass",
                        "passed": False,
                        "executed": True,
                        "suite_broken": False,  # would route SUBJECT on its own
                    },
                    {"check": f"acceptance:{CHECK_CONTRACT_ASSERTIONS}", "passed": False},
                ],
            }
        }
        assert classify_failure_locus(evidence) == FailureLocus.OWN_ARTIFACT

    def test_passing_contract_row_is_no_signal(self):
        evidence = {
            "validation_result": {
                "passed": False,
                "checks": [{"check": f"acceptance:{CHECK_CONTRACT_ASSERTIONS}", "passed": True}],
            }
        }
        assert classify_failure_locus(evidence) == FailureLocus.UNKNOWN
