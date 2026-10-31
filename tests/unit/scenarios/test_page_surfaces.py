"""A browser scenario's pages, checked against the delivery's declared routes before anything
runs (SIP-0113 §10p ruling 4; #2564 step 3). Entered at ``evaluate_cycle`` with the runner faked.

What bugs would these catch?
- a browser scenario sent to a route the delivery doesn't declare, so every lookup on it reads
  "not found" and the scenario reads ``control_absent`` instead of ``surface_absent``;
- a route the delivery writes in its router's syntax (``/runs/:id``) read as another route than
  the scenario's ``/runs/{id}``;
- an HTTP-only scenario's page surface, declarative until now, newly checked, which would move
  revision 4's readings.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.scenarios import evaluate
from squadops.scenarios.evaluation import BlockedReason
from squadops.scenarios.models import parse_suite
from squadops.scenarios.runner import TreeEvaluation
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import approve_suite, draft_suite
from tests.unit.scenarios.test_quality_evaluation import _MANIFEST, _Cycle, _Vault

T0 = datetime(2026, 10, 22, 5, 0, tzinfo=UTC)


def _scenario(scenario_id: str, page: str, *, browser: bool) -> dict:
    steps = [{"action": "visit", "path": "/"}] if browser else [
        {"action": "http", "method": "GET", "path": "/runs"}
    ]  # fmt: skip
    return {
        "scenario_id": scenario_id,
        "goal": f"{scenario_id}'s outcome.",
        "surfaces": [{"kind": "page", "path": page}],
        "steps": steps,
        "checks": [
            {"check": "absent", "step": 1, "pattern": "went wrong"}
            if browser
            else {"check": "status", "step": 1, "equals": 200}
        ],
    }


class _Runner:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def evaluate_tree(self, **kw):
        self.sent = [s["scenario_id"] for s in kw["scenarios"]]
        runs = tuple(ScenarioRun(i, "passed") for i in self.sent)
        return TreeEvaluation(kw["tree_identity"], started=True, runs=runs)


@pytest.fixture
async def evaluated(monkeypatch):
    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    suite = parse_suite(
        {
            "name": "pages",
            "scenarios": [
                _scenario("a-declared-route", "/runs/{id}", browser=True),
                _scenario("an-undeclared-route", "/leaderboard", browser=True),
                _scenario("an-http-scenario-with-a-page", "/leaderboard", browser=False),
            ],
        }
    )
    store = MemoryScenarioStore()
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)
    runner = _Runner()
    record = await evaluate.evaluate_cycle(
        store=store, runner=runner, vault=_Vault(_MANIFEST), cycle=_Cycle(),
        suite_digest=suite.digest, campaign_id=None, previous_accepted_tree_identity=None,
        evaluated_at=T0,
    )  # fmt: skip
    return runner, {o.scenario_id: o for o in record.outcomes}


async def test_a_browser_scenario_on_a_route_the_delivery_doesnt_declare_is_surface_absent(
    evaluated,
):
    runner, outcomes = evaluated

    assert outcomes["an-undeclared-route"].blocked_reason is BlockedReason.SURFACE_ABSENT
    assert "an-undeclared-route" not in runner.sent


async def test_a_declared_route_in_the_routers_syntax_and_an_http_scenarios_page_still_run(
    evaluated,
):
    runner, outcomes = evaluated

    assert runner.sent == ["a-declared-route", "an-http-scenario-with-a-page"]
    assert outcomes["an-http-scenario-with-a-page"].blocked_reason is None


def test_a_route_reads_the_same_in_either_parameter_syntax():
    assert evaluate.delivered_routes(None) is None
    assert evaluate._route("/runs/:id") == evaluate._route("/runs/{run_id}") == "/runs/{}"
