"""The runner's vocabulary, against fake apps (SIP-0113 §4.1, §7 prediction 1; #2414)."""

from __future__ import annotations

import pytest

from squadops.scenarios.steps import HttpRequest, HttpResponse, run_scenario

#: The reference scenario's job (#1804, the PRD's Expansion Tier 1 item 1): a run with a capacity
#: of one refuses a second participant.
CAPACITY = {
    "scenario_id": "capacity",
    "steps": [
        {"action": "http", "method": "POST", "path": "/runs", "json": {"name": "Sat", "capacity": 1},
         "save": {"run": "id"}, "expect_status": 201},
        {"action": "http", "method": "POST", "path": "/runs/{run}/participants",
         "json": {"name": "Ada"}},
        {"action": "http", "method": "POST", "path": "/runs/{run}/participants",
         "json": {"name": "Grace"}},
        {"action": "http", "method": "GET", "path": "/runs/{run}"},
    ],
    "checks": [
        {"check": "status", "step": 3, "equals": 409},
        {"check": "json", "step": 4, "path": "participants", "length": 1},
        {"check": "json", "step": 4, "path": "participants.0.name", "equals": "Ada"},
    ],
}  # fmt: skip


def _app(*, enforces_capacity: bool):
    runs: dict[str, dict] = {}

    async def send(request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and request.path == "/runs":
            run_id = f"r{len(runs) + 1}"
            runs[run_id] = {"id": run_id, **request.json, "participants": []}
            return HttpResponse(201, runs[run_id])
        _, _, run_id, *rest = request.path.split("/")
        run = runs.get(run_id)
        if run is None:
            return HttpResponse(404, {"detail": "no run"})
        if rest == ["participants"]:
            if enforces_capacity and len(run["participants"]) >= run["capacity"]:
                return HttpResponse(409, {"detail": "full"})
            run["participants"].append(request.json)
            return HttpResponse(201, run)
        return HttpResponse(200, run)

    return send


async def test_the_capacity_scenario_tells_a_tree_with_the_limit_from_one_without():
    """§7 prediction 1's mechanism. Bug caught: a scenario that passes on the baseline too (a
    check that reads nothing, or a saved id never threaded into the next step's path), which
    can't tell an increment that built its outcome from one that didn't."""
    baseline = await run_scenario(CAPACITY, _app(enforces_capacity=False))
    increment = await run_scenario(CAPACITY, _app(enforces_capacity=True))

    assert (baseline.result, baseline.first_failing_step, baseline.steps_taken) == ("failed", 3, 4)
    assert "answered 201, not 409" in baseline.detail
    assert (increment.result, increment.first_failing_step, increment.steps_taken) == (
        "passed",
        None,
        4,
    )


async def _refused(request: HttpRequest) -> HttpResponse:
    raise ConnectionError("connection refused")


@pytest.mark.parametrize(
    ("steps", "checks", "send", "ended"),
    [
        (CAPACITY["steps"][:1], CAPACITY["checks"][:1], _refused, ("failed", None, 1)),
        ([{"action": "click", "selector": "#join"}], [], None, ("blocked_unverified", "browser_unavailable", None)),
        ([{"action": "ssh", "host": "x"}], [], None, ("blocked_unverified", "no_runner", None)),
        (CAPACITY["steps"][:1], [{"check": "status", "step": 9, "equals": 201}], None, ("blocked_unverified", "no_runner", None)),
        (CAPACITY["steps"][:1], [{"check": "screenshot", "step": 1}], None, ("blocked_unverified", "no_runner", None)),
        ([{**CAPACITY["steps"][0], "save": {"run": "uuid"}}], [], None, ("failed", None, 1)),
        ([{**CAPACITY["steps"][0], "expect_status": 200}], [], None, ("failed", None, 1)),
        ([CAPACITY["steps"][1]], [], None, ("failed", None, 1)),
    ],
    ids=[
        "app-unreachable",
        "browser-action",
        "unknown-action",
        "check-on-a-step-that-did-not-run",
        "unknown-check",
        "save-the-response-cannot-answer",
        "unexpected-status",
        "an-unsaved-name-in-a-path",
    ],
)  # fmt: skip
async def test_a_scenario_that_cannot_complete_says_which_way_it_ended(steps, checks, send, ended):
    """SIP-0112 §8.3.1: blocked_unverified is never passed and never failed. Bug caught: a
    browser step or an unknown check counted as a pass, or an app that refused the connection
    read as the runner's own failure rather than the product's at that step."""
    scenario = {"scenario_id": "s", "steps": steps, "checks": checks}
    result = await run_scenario(scenario, send or _app(enforces_capacity=True))

    if ended[0] == "failed":
        assert (result.result, result.first_failing_step) == ("failed", ended[2])
    else:
        assert (result.result, result.blocked_reason) == ended[:2]
