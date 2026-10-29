"""The runner's vocabulary, against fake apps (SIP-0113 §4.1, §7 prediction 1; #2414)."""

from __future__ import annotations

import pytest

from squadops.scenarios.steps import HttpRequest, HttpResponse, run_scenario, vocabulary_refusals

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


@pytest.mark.parametrize(
    ("status", "result"), [(400, "passed"), (422, "passed"), (500, "failed")], ids=str
)
async def test_a_status_check_may_accept_each_status_a_delivery_can_choose(status, result):
    """#2464: the PRD says a request is "rejected", and each delivery's manifest picks the status,
    422 on the canonical stack and 400 on Next.js. Bug caught: a valid rejection read as a failure
    because the check named one delivery's choice; or a server error read as a rejection."""

    async def send(request: HttpRequest) -> HttpResponse:
        return HttpResponse(status, {"error": "title is required"})

    run = await run_scenario(
        {
            "scenario_id": "a-run-without-a-title-is-refused",
            "steps": [{"action": "http", "method": "POST", "path": "/runs", "json": {}}],
            "checks": [{"check": "status", "step": 1, "in": [400, 422]}],
        },
        send,
    )

    assert run.result == result
    if result == "failed":
        assert run.detail == "step 1 answered 500, not 400 or 422"


_LISTED = [
    {"id": "r1", "title": "Sunrise Social", "meeting_location": "Track", "participants": []},
    {"id": "r2", "title": "Riverside 10K", "meeting_location": "Pier 4", "participants": []},
]


@pytest.mark.parametrize(
    ("body", "where", "result", "detail"),
    [
        (_LISTED, {"title": "Riverside 10K", "meeting_location": "Pier 4"}, "passed", None),
        (_LISTED, {"title": "Riverside 10K", "meeting_location": "Track"}, "failed",
         "'' (2 elements) has none with {'title': 'Riverside 10K', 'meeting_location': 'Track'}"),
        (_LISTED, {"title": "Riverside 10K", "location": "Pier 4"}, "failed",
         "'' (2 elements) has none with {'title': 'Riverside 10K', 'location': 'Pier 4'}"),
        ([], {"title": "Riverside 10K"}, "failed", "'' (0 elements) has none with {'title': 'Riverside 10K'}"),
        ({"runs": _LISTED}, {"title": "Riverside 10K"}, "failed",
         "'' (None elements) has none with {'title': 'Riverside 10K'}"),
        (["Riverside 10K"], {"title": "Riverside 10K"}, "failed", "'' (1 elements) has none with {'title': 'Riverside 10K'}"),
    ],
    ids=["an-element-has-every-field", "one-field-differs", "a-field-it-lacks", "empty-list",
         "not-a-list", "elements-not-mappings"],
)  # fmt: skip
async def test_a_where_check_finds_the_element_by_its_fields_not_its_place(
    body, where, result, detail
):
    """#2464: "a created run appears in the list" names the run, and the list holds the suite's
    other runs in an order the scenario can't know. Bug caught: a check that passes when one field
    matches and another doesn't, when the element lacks a named field, or on a body that isn't a
    list of objects at all."""

    async def send(request: HttpRequest) -> HttpResponse:
        return HttpResponse(200, body)

    run = await run_scenario(
        {
            "scenario_id": "a-created-run-is-listed",
            "steps": [{"action": "http", "method": "GET", "path": "/runs"}],
            "checks": [{"check": "json", "step": 1, "path": "", "where": where}],
        },
        send,
    )

    assert (run.result, run.detail) == (result, detail)


async def test_a_where_check_that_names_no_field_is_one_the_runner_cannot_read():
    """Bug caught: an empty ``where`` holding vacuously on any non-empty list, a pass with no
    condition behind it. It reads as the runner's gap, blocked_unverified, never passed."""

    async def send(request: HttpRequest) -> HttpResponse:
        return HttpResponse(200, _LISTED)

    run = await run_scenario(
        {
            "scenario_id": "s",
            "steps": [{"action": "http", "method": "GET", "path": "/runs"}],
            "checks": [{"check": "json", "step": 1, "path": "", "where": {}}],
        },
        send,
    )

    assert (run.result, run.blocked_reason) == ("blocked_unverified", "no_runner")


#: A ledger with two accounts, each read alone at ``/accounts/<id>`` (#2784's shape).
_ACCOUNTS = [{"id": "acct-a", "balance": 3}, {"id": "acct-b", "balance": 5}]


def _ledger(*, reads_by_id: bool):
    async def send(request: HttpRequest) -> HttpResponse:
        if request.path == "/accounts":
            return HttpResponse(200, _ACCOUNTS)
        wanted = request.path.rsplit("/", 1)[-1]
        found = [a for a in _ACCOUNTS if a["id"] == wanted] if reads_by_id else _ACCOUNTS[:1]
        return HttpResponse(200, found[0]) if found else HttpResponse(404, {"detail": "none"})

    return send


_COMPARED = {
    "scenario_id": "an-account-read-alone-matches-the-list",
    "steps": [
        {"action": "http", "method": "GET", "path": "/accounts",
         "save": {"account": "1.id", "balance": "1.balance"}},
        {"action": "http", "method": "GET", "path": "/accounts/{account}"},
    ],
    "checks": [
        {"check": "json", "step": 2, "path": "id", "equals": "{account}"},
        {"check": "json", "step": 2, "path": "balance", "equals": "{balance}"},
        {"check": "json", "step": 1, "path": "", "where": {"id": "{account}"}},
    ],
}  # fmt: skip


@pytest.mark.parametrize(
    ("reads_by_id", "result", "detail"),
    [(True, "passed", None), (False, "failed", "'id' is 'acct-a'")],
    ids=["the item asked for", "always the first item"],
)
async def test_a_check_compares_a_response_with_a_value_an_earlier_step_saved(
    reads_by_id, result, detail
):
    """#2784. Bugs caught: an HTTP check left unrendered, so ``"{account}"`` is compared as text
    and a correct product fails; a saved number rendered as text, so ``3 == "3"`` fails; and a
    check that holds whichever item the product answers."""
    run = await run_scenario(_COMPARED, _ledger(reads_by_id=reads_by_id))

    assert (run.result, run.detail) == (result, detail)


async def test_a_check_naming_a_value_no_step_saved_is_the_suites_gap_not_a_failure():
    """#2784. Bug caught: a suite's typo read as the product failing. Drafting refuses it
    (``vocabulary_refusals``); a suite stored before the rule still reads blocked_unverified."""
    scenario = {**_COMPARED, "checks": [{"check": "json", "step": 2, "path": "id", "equals": "{acount}"}]}  # fmt: skip

    run = await run_scenario(scenario, _ledger(reads_by_id=True))

    assert (run.result, run.blocked_reason) == ("blocked_unverified", "no_runner")
    assert "acount" in run.detail


@pytest.mark.parametrize(
    ("steps", "checks", "refused"),
    [
        (_COMPARED["steps"], _COMPARED["checks"], []),
        (
            [_COMPARED["steps"][1], _COMPARED["steps"][0]],
            [],
            ["step 1: names {account}, which no earlier step saves"],
        ),
        (
            _COMPARED["steps"],
            [{"check": "json", "step": 2, "path": "owner", "equals": "{owner}"}],
            ["check 1: names {owner}, which no step before it saves"],
        ),
        (
            # An HTTP check is read after every step, so a later step's save is known to it.
            [*_COMPARED["steps"], {"action": "http", "method": "GET", "path": "/x", "save": {"late": "id"}}],
            [{"check": "json", "step": 1, "path": "0.id", "equals": "{late}"}],
            [],
        ),
        (
            # A browser check's segment is sent before a later step saves anything.
            [{"action": "visit", "path": "/accounts"},
             {"action": "http", "method": "GET", "path": "/accounts", "save": {"late": "0.id"}}],
            [{"check": "text", "step": 1, "pattern": "{late}"}],
            ["check 1: names {late}, which no step before it saves"],
        ),
    ],
    ids=[
        "every name saved first",
        "a step reads a name before it's saved",
        "a check names a value nothing saves",
        "an http check reads a later save",
        "a browser check reads a later save",
    ],
)  # fmt: skip
def test_a_name_no_step_saves_before_its_read_is_refused_when_drafted(steps, checks, refused):
    """#2784. Bugs caught: a misspelt or misordered name reaching an approved suite, where it
    reads as the product failing; and a refusal of a name a step does save, or of a ``save``'s own
    response paths."""
    assert vocabulary_refusals(steps, checks) == refused
