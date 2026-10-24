"""#2297 — ``contract_assertions_match`` refuses a request that is a declared route with a
required path segment left empty.

Two TensorFold cycles (``cyc_af79e6520ae6``, ``cyc_935ec2afb53f``) each spent a correction
round on a leave test whose name, a path segment, was empty: the request ended at the
parent with a trailing slash, the router redirected it to the parent's path, which serves
another method, and the test got 405 whatever the handler did. Leave had no probe, so the
pinned-status rule never read it. The suites below are invented; the stored ones are the
vault replay's evidence on the PR.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from squadops.cycles.acceptance_check_spec import CHECK_CONTRACT_ASSERTIONS
from squadops.cycles.acceptance_checks import get_check
from squadops.cycles.acceptance_evaluation import evaluate_criterion, split_acceptance_criteria
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.cycles.task_plan import generate_task_plan
from squadops.cycles.verification_contract import VerificationContract
from squadops.stacks.scaffold import InterfaceManifest

pytestmark = [pytest.mark.domain_contracts]

_FILE = "backend/tests/test_lists.py"
_PINNED = {
    "file": _FILE,
    "endpoints": ["POST /lists 201", "POST /lists 422", "POST /lists/{list_id}/items 200"],
    "allowed_error_statuses": [404, 409, 422],
}
_DECLARED = [
    "POST /lists",
    "GET /lists/{list_id}",
    "POST /lists/{list_id}/items",
    "GET /lists/{list_id}/items",
    "GET /lists/{list_id}/items/{item_id}",
    "DELETE /lists/{list_id}/items/{item_id}",
    "DELETE /tags/{tag}",  # nothing serves /tags itself
    "GET /files/{rest:path}",
    "DELETE /files/{name}",
    "DELETE /files/{folder}/{rest:path}",
]


def _suite(request: str, assertion: str = "== 200") -> str:
    """One test: create a list, make ``request``, assert its status on line 4."""
    return (
        "def test_case(client):\n"
        '    list_id = client.post("/lists", json={"title": "x"}).json()["id"]\n'
        f"    resp = {request}\n"
        f"    assert resp.status_code {assertion}\n"
    )


async def _evaluate(tmp_path: Path, source: str, params: dict):
    suite = tmp_path / _FILE
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text(source)
    return await get_check(CHECK_CONTRACT_ASSERTIONS).evaluate(
        dict(params), tmp_path, stack="fastapi"
    )


def _with_routes(routes: list[str] = _DECLARED) -> dict:
    return {**_PINNED, "declared_routes": list(routes)}


class TestTheRule:
    @pytest.mark.parametrize(
        ("request_", "assertion", "reason"),
        [
            # the cycles' shape: the parent, with a trailing slash
            (
                'client.delete(f"/lists/{list_id}/items/")',
                "== 404",
                "line 4: DELETE /lists/{list_id}/items/ requests declared route "
                "DELETE /lists/{list_id}/items/{item_id} with its required segment "
                "{item_id} empty; the router answers 405 before any handler runs",
            ),
            (
                'client.delete("/lists//items/7")',
                "== 422",
                "line 4: DELETE /lists//items/7 requests declared route "
                "DELETE /lists/{list_id}/items/{item_id} with its required segment "
                "{list_id} empty; the router answers 404 before any handler runs",
            ),
            (
                'client.delete("/lists//items/")',
                "== 422",
                "line 4: DELETE /lists//items/ requests declared route "
                "DELETE /lists/{list_id}/items/{item_id} with its required segments "
                "{list_id}, {item_id} empty; the router answers 404 before any handler runs",
            ),
            # a query string does not fill the segment
            (
                'client.delete(f"/lists/{list_id}/items/?force=true")',
                "== 422",
                "line 4: DELETE /lists/{list_id}/items/ requests declared route "
                "DELETE /lists/{list_id}/items/{item_id} with its required segment "
                "{item_id} empty; the router answers 405 before any handler runs",
            ),
        ],
        ids=["trailing-slash", "middle-segment", "two-segments", "query"],
    )
    async def test_an_emptied_required_segment_fails_naming_line_route_and_segment(
        self, tmp_path, request_, assertion, reason
    ):
        """Bug caught: the cycles' leave test passing emission, so the suite runs, gets the
        router's 405 and costs a correction round no repair of the app can win."""
        outcome = await _evaluate(tmp_path, _suite(request_, assertion), _with_routes())

        assert outcome.status == "failed"
        assert outcome.reason == reason
        assert outcome.actual["violations"] == 1

    @pytest.mark.parametrize(
        ("request_", "status", "reason"),
        [
            # the parent serves another method: the router redirects the slash, then 405
            ('client.delete(f"/lists/{list_id}/items/")', 405, None),
            (
                'client.delete(f"/lists/{list_id}/items/")',
                422,
                "line 4: DELETE /lists/{list_id}/items/ requests declared route "
                "DELETE /lists/{list_id}/items/{item_id} with its required segment "
                "{item_id} empty; the router answers 405 before any handler runs",
            ),
            # nothing serves the parent: no redirect, 404
            ('client.delete("/tags/")', 404, None),
            (
                'client.delete("/tags/")',
                405,
                "line 4: DELETE /tags/ requests declared route DELETE /tags/{tag} with its "
                "required segment {tag} empty; the router answers 404 before any handler runs",
            ),
            # the path as requested matches a route of another method: 405, no redirect
            ('client.delete("/files/")', 405, None),
        ],
        ids=[
            "405-asserted",
            "405-other-status",
            "404-asserted",
            "404-other-status",
            "405-on-the-path-itself",
        ],
    )
    async def test_the_routers_own_answer_is_not_refused(self, tmp_path, request_, status, reason):
        """Bug caught: refusing a winnable assertion. The router answers the emptied request
        before any handler runs, so asserting exactly that answer passes whatever the app
        does; both cycles' repairs asserted 405 and were accepted. Any other status is
        refused with the answer named, derived from the routes, never a fixed status."""
        outcome = await _evaluate(tmp_path, _suite(request_, f"== {status}"), _with_routes())

        if reason is None:
            assert outcome.status == "passed", outcome.reason
        else:
            assert outcome.status == "failed"
            assert outcome.reason == reason

    @pytest.mark.parametrize(
        "request_",
        [
            'client.delete(f"/lists/{list_id}/items/7")',  # every segment filled
            # the emptied child's parent serves its method: the trailing slash redirects there
            'client.get(f"/lists/{list_id}/items/")',
            'client.patch(f"/lists/{list_id}/items/", json={"text": "b"})',  # no declared PATCH
            # {folder} is empty, but the route's {rest:path} gives it no fixed shape
            'client.delete("/files//x")',
            'client.delete(f"/archive/{list_id}/items/")',  # not a declared route
        ],
        ids=["full", "own-method-parent", "other-method", "path-convertor", "undeclared"],
    )
    async def test_requests_that_reach_a_route_or_no_declared_one_pass(self, tmp_path, request_):
        """Bug caught: a false positive in a blocking check, which is a new unwinnable loop.
        Each case asserts 200, not the router's answer, and is one the rule would flag if it
        dropped one of its conditions: an interpolation read as empty, the redirect to a
        route of the request's own method, the method match, the ``path`` convertor, the
        literal segments."""
        outcome = await _evaluate(tmp_path, _suite(request_), _with_routes())

        assert outcome.status == "passed", outcome.reason


class TestWithoutDeclaredRoutes:
    @pytest.mark.parametrize(
        "params",
        [_PINNED, _with_routes(["garbage", "DELETE"])],
        ids=["absent", "malformed"],
    )
    async def test_the_check_reads_what_it_read_before(self, tmp_path, params):
        """Bug caught: a seam whose envelope predates the param (a resumed run, an older
        plan) newly failing a suite it accepted: the rule run on routes it was not given
        (the pinned ones), or a malformed token breaking the evaluation. The second test's
        request empties the pinned ``POST /lists/{list_id}/items``."""
        source = (
            _suite('client.delete(f"/lists/{list_id}/items/")') + "\n\ndef test_other(client):\n"
            '    resp = client.post("/lists//items", json={"text": "a"})\n'
            "    assert resp.status_code == 422\n"
        )

        outcome = await _evaluate(tmp_path, source, params)

        assert outcome.status == "passed", outcome.reason

    @pytest.mark.parametrize("params", [_PINNED, _with_routes()], ids=["without", "with"])
    async def test_probed_endpoints_are_read_exactly_as_before(self, tmp_path, params):
        """Bug caught: the f-string reading leaking into the pinned rule. ``POST
        /lists/{list_id}/items`` is pinned at 200 and the second request templates to exactly
        that key, asserting 500: the pinned rule reads literals only, so it is not flagged,
        with the routes or without. The literal create asserting 200 is flagged identically."""
        source = (
            "def test_flow(client):\n"
            '    resp = client.post("/lists", json={"title": "x"})\n'
            "    assert resp.status_code == 200\n"
            '    list_id = resp.json()["id"]\n'
            '    resp = client.post(f"/lists/{list_id}/items", json={"text": "a"})\n'
            "    assert resp.status_code == 500\n"
        )

        outcome = await _evaluate(tmp_path, source, params)

        assert outcome.status == "failed"
        assert (
            outcome.reason == "line 3: POST /lists asserts 200; contract pins [201, 404, 409, 422]"
        )


# --- the wiring: where a live cycle builds the criterion ----------------------------------

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = InterfaceManifest.from_yaml(
    (_REPO / "examples" / "03_group_run" / "interface_manifest.yaml").read_text(encoding="utf-8")
)
_NOW = datetime(2026, 10, 24, tzinfo=UTC)
_QA_SUITE = "backend/tests/test_items.py"


def _contract() -> VerificationContract:
    return VerificationContract.from_dict(
        {
            "contract_version": 1,
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "a" * 64,
            },
            "capabilities": ["python"],
            "frozen": [],
            "fill_files": {
                "backend/routes.py": {
                    "interface": [
                        {
                            "check": "endpoint_defined",
                            "id": "vc-routes-endpoints",
                            "methods_paths": ["POST /runs"],
                        }
                    ],
                    "implementation": [],
                }
            },
            "behavioral": {
                "build": [],
                "suite": {"checks": [], "coverage_expectations": []},
                "probes": [
                    {
                        "id": "vc-probe-create",
                        "subject": "backend",
                        "request": {"method": "POST", "path": "/runs", "json": {"title": "x"}},
                        "expect": {"status": 201},
                    }
                ],
            },
        }
    )


def _plan() -> ImplementationPlan:
    return ImplementationPlan.from_yaml(
        yaml.safe_dump(
            {
                "version": 1,
                "project_id": "p",
                "cycle_id": "cyc_wiring",
                "prd_hash": "h",
                "tasks": [
                    {
                        "task_index": 0,
                        "task_type": "development.develop",
                        "role": "dev",
                        "focus": "routes",
                        "description": "implement the routes fill slot",
                        "expected_artifacts": ["backend/routes.py"],
                        "acceptance_criteria": [],
                        "depends_on": [],
                        "criteria_refs": ["vc-routes-endpoints"],
                    },
                    {
                        "task_index": 1,
                        "task_type": "qa.test",
                        "role": "qa",
                        "focus": "suite",
                        "description": "author the API suite",
                        "expected_artifacts": [_QA_SUITE],
                        "acceptance_criteria": [],
                        "depends_on": [0],
                        "criteria_refs": [],
                    },
                ],
                "summary": {"total_dev_tasks": 1, "total_qa_tasks": 1, "total_tasks": 2},
            }
        )
    )


def _qa_criteria(interface_manifest: InterfaceManifest | None) -> list:
    """The qa.test envelope's acceptance criteria, as they cross the A2A wire (JSON)."""
    cycle = Cycle(
        cycle_id="cyc_wiring",
        project_id="proj",
        created_at=_NOW,
        created_by="s",
        prd_ref="PRD",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"build_profile": "fullstack_fastapi_react", "implementation_plan": True},
        execution_overrides={"contract_ref": "art_c"},
        expected_artifact_types=["source"],
    )
    run = Run(
        run_id="run_abcdef123456",
        cycle_id="cyc_wiring",
        run_number=1,
        status="running",
        initiated_by="api",
        resolved_config_hash="h",
        workload_type=WorkloadType.IMPLEMENTATION,
    )
    profile = SquadProfile(
        profile_id="full",
        name="F",
        description="d",
        version=1,
        agents=tuple(
            AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
            for a, r in (
                ("max", "lead"),
                ("neo", "dev"),
                ("nat", "strat"),
                ("eve", "qa"),
                ("data", "data"),
                ("bob", "builder"),
            )
        ),
        created_at=_NOW,
    )
    envelopes = generate_task_plan(
        cycle,
        run,
        profile,
        plan=_plan(),
        contract=_contract(),
        interface_manifest=interface_manifest,
    )
    (qa,) = [e for e in envelopes if e.task_type == "qa.test"]
    return json.loads(json.dumps(qa.to_dict(), default=str))["inputs"]["acceptance_criteria"]


def _contract_row(criteria: list) -> dict:
    (row,) = [c for c in criteria if c.get("check") == CHECK_CONTRACT_ASSERTIONS]
    return row


class TestTheWiring:
    def test_the_manifests_routes_reach_the_suites_check(self):
        """Bug caught: the rule built and never fed — the criterion built without the
        manifest's routes, so every live cycle evaluates the check as before."""
        row = _contract_row(_qa_criteria(_MANIFEST))

        assert row["params"]["file"] == _QA_SUITE
        assert row["params"]["endpoints"] == ["POST /runs 201"]
        assert row["params"]["declared_routes"] == [
            "GET /runs",
            "POST /runs",
            "GET /runs/{run_id}",
            "POST /runs/{run_id}/join",
            "POST /runs/{run_id}/leave",
        ]

    def test_a_cycle_with_no_manifest_builds_the_row_it_built_before(self):
        row = _contract_row(_qa_criteria(None))

        assert row["params"] == {"file": _QA_SUITE, "endpoints": ["POST /runs 201"]}

    async def test_the_dispatched_row_parses_and_refuses_an_emptied_segment(self, tmp_path):
        """Bug caught: the param missing from the check's spec. The agent re-parses the wire
        row, an unknown param makes it unparseable, and the handler discloses it as passed
        without evaluating it."""
        split = split_acceptance_criteria(_qa_criteria(_MANIFEST))
        assert split.unparseable == ()
        (criterion,) = [c for c in split.typed if c.check == CHECK_CONTRACT_ASSERTIONS]
        suite = tmp_path / _QA_SUITE
        suite.parent.mkdir(parents=True)
        suite.write_text(
            "def test_join_needs_a_run(client):\n"
            '    resp = client.post("/runs//join", json={"name": "A"})\n'
            "    assert resp.status_code == 422\n"
        )

        outcome = await evaluate_criterion(
            criterion,
            tmp_path,
            stack="fastapi",
            typed_acceptance_enabled=True,
            command_acceptance_enabled=True,
        )

        assert outcome.status == "failed"
        assert outcome.reason == (
            "line 3: POST /runs//join requests declared route POST /runs/{run_id}/join "
            "with its required segment {run_id} empty; the router answers 404 before any "
            "handler runs"
        )
