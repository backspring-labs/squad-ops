"""The runner's browser vocabulary, as pure code (SIP-0113 §10k, §10p rulings 1 to 4, 9 and 10;
#2564's build step 1). Entered at ``run_scenario`` with a fake app and a fake browser, and at
``vocabulary_refusals``, which the draft and the approval read.

What bugs would these catch?
- a check reading the wrong page, or a response at a shifted index, once browser steps sit
  between HTTP steps;
- a saved value spliced into a pattern unescaped, so a title with ``(`` or ``+`` breaks or widens
  it;
- a control not found read as a failure, or a broken page as unverified;
- a check's failure reported before the step that failed after it;
- a segment sent with checks that read another segment's steps;
- a malformed browser step accepted at draft, or a refusal that echoes a held-out value.
"""

from __future__ import annotations

import re

import pytest

from squadops.scenarios.steps import (
    BrowseAnswer,
    BrowseCheck,
    BrowserUnavailable,
    BrowseStep,
    HttpRequest,
    HttpResponse,
    run_scenario,
    vocabulary_refusals,
)

TITLE = "Dawn (5k) + coffee"
JOIN = {"role": "button", "names": ["Join", "Join this run"]}
NAME_BOX = {"role": "textbox", "names": ["Name", "Your name"], "near": JOIN}


async def _app(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return HttpResponse(201, {"id": "r1", **(request.json or {})})
    return HttpResponse(200, {"id": "r1", "title": TITLE, "participants": [{"name": "Ida"}]})


class _Browser:
    """Answers each segment with its steps' outcomes and its checks' readings, by step and index."""

    def __init__(self, outcomes=None, holds=None, raises=None) -> None:
        self.requests = []
        self.outcomes, self.holds, self.raises = outcomes or {}, holds or {}, raises

    async def __call__(self, request):
        self.requests.append(request)
        if self.raises:
            raise self.raises
        steps = tuple(
            BrowseStep(
                n,
                self.outcomes.get(n, "done"),
                None if n not in self.outcomes else "Moonrise-Relay was on the page",
                0.25,
            )
            for n in range(request.first_step, request.first_step + len(request.steps))
            if self.outcomes.get(n) != "missing"
        )
        checks = tuple(
            BrowseCheck(i, self.holds.get(i, True), None if self.holds.get(i, True) else "seen 0")
            for i, _ in request.checks
        )
        return BrowseAnswer(steps, checks, browser="ev:1 Chrome/155")


def _joining(*checks) -> dict:
    return {
        "scenario_id": "join-from-the-page",
        "steps": [
            {"action": "http", "method": "POST", "path": "/runs", "json": {"title": TITLE},
             "save": {"run_id": "id", "title": "title"}, "expect_status": 201},
            {"action": "visit", "path": "/runs/{run_id}"},
            {"action": "fill", "target": NAME_BOX, "value": "Ida"},
            {"action": "click", "target": JOIN},
            {"action": "http", "method": "GET", "path": "/runs/{run_id}"},
        ],
        "checks": list(checks),
    }  # fmt: skip


async def test_a_mixed_scenario_sends_its_segment_rendered_with_only_the_checks_that_read_it():
    """§10p rulings 1 and 2. Bug caught: the segment sent unrendered, a saved title spliced into a
    pattern unescaped, an HTTP check reading a shifted response once browser steps sit before it,
    or a check on another step sent to the browser."""
    browser = _Browser()
    scenario = _joining(
        {"check": "text", "step": 4, "pattern": "{title}"},
        {"check": "json", "step": 5, "path": "participants", "length": 1},
        {"check": "status", "step": 1, "equals": 201},
    )

    run = await run_scenario(scenario, _app, browser)

    [request] = browser.requests
    [(index, pattern_check)] = request.checks
    assert (run.result, run.steps_taken) == ("passed", 5)
    assert (request.first_step, [s["action"] for s in request.steps]) == (
        2,
        ["visit", "fill", "click"],
    )
    assert request.steps[0]["path"] == "/runs/r1"
    assert (index, pattern_check["pattern"]) == (0, re.escape(TITLE))
    assert re.fullmatch(pattern_check["pattern"], TITLE)


@pytest.mark.parametrize(
    ("browser", "ended"),
    [
        (_Browser(outcomes={3: "not_found"}), ("blocked_unverified", "control_absent", None)),
        (_Browser(outcomes={4: "action_failed"}), ("failed", None, 4)),
        (_Browser(outcomes={2: "timeout"}), ("failed", None, 2)),
        (_Browser(outcomes={2: "page_broken"}), ("failed", None, 2)),
        (_Browser(outcomes={4: "missing"}), ("blocked_unverified", "browser_unavailable", None)),
        (_Browser(raises=BrowserUnavailable("no answer")), ("blocked_unverified", "browser_unavailable", None)),
        (None, ("blocked_unverified", "browser_unavailable", None)),
    ],
    ids=[
        "a-control-none-of-its-names-finds",
        "a-found-control-whose-action-failed",
        "a-wait-that-ran-out",
        "a-page-that-broke",
        "a-step-the-browser-never-answered",
        "no-browser-answered",
        "no-browser-runs",
    ],
)  # fmt: skip
async def test_a_browser_step_ends_its_scenario_the_way_the_browser_says(browser, ended):
    """§10p ruling 4. Bug caught: a control a delivery names differently read as a broken app, a
    broken page or an expired wait read as unverified, or a browser that never answered read as
    the product failing."""
    run = await run_scenario(_joining(), _app, browser)

    assert (run.result, run.blocked_reason, run.first_failing_step) == ended


async def test_a_step_that_fails_after_a_check_that_didnt_hold_is_the_failure_reported():
    """§10p ruling 2: checks are reported after every step. Bug caught: a check on the page after
    step 2 reported as the failure when step 4, which ran after it, failed."""
    browser = _Browser(outcomes={4: "action_failed"}, holds={0: False})

    run = await run_scenario(
        _joining({"check": "text", "step": 2, "pattern": "Ida"}), _app, browser
    )

    assert (run.result, run.first_failing_step) == ("failed", 4)


async def test_a_browser_check_that_doesnt_hold_fails_at_its_step_with_what_the_page_showed():
    run = await run_scenario(
        _joining({"check": "count", "step": 4, "target": {"role": "listitem"}, "equals": 1}),
        _app,
        _Browser(holds={0: False}),
    )

    assert (run.result, run.first_failing_step, run.detail) == ("failed", 4, "seen 0")


async def test_an_unsaved_name_in_a_browser_step_fails_at_that_step_and_nothing_is_browsed():
    browser = _Browser()
    scenario = _joining()
    scenario["steps"][2] = {"action": "fill", "target": NAME_BOX, "value": "{nickname}"}

    run = await run_scenario(scenario, _app, browser)

    assert (run.result, run.first_failing_step, browser.requests) == ("failed", 3, [])


async def test_each_segment_goes_to_the_browser_apart_with_its_own_checks():
    """§10p ruling 1: one container per segment, each beginning with visit. Bug caught: two
    segments merged into one, or a check sent with the segment that doesn't hold its step."""
    browser = _Browser()
    scenario = {
        "scenario_id": "reload",
        "steps": [
            {"action": "visit", "path": "/"},
            {"action": "http", "method": "POST", "path": "/runs", "json": {"title": TITLE},
             "save": {"run_id": "id"}},
            {"action": "visit", "path": "/runs/{run_id}"},
        ],
        "checks": [
            {"check": "absent", "step": 1, "pattern": "went wrong"},
            {"check": "text", "step": 3, "pattern": "Dawn"},
        ],
    }  # fmt: skip

    run = await run_scenario(scenario, _app, browser)

    assert run.result == "passed"
    assert [(r.first_step, [i for i, _ in r.checks]) for r in browser.requests] == [
        (1, [0]),
        (3, [1]),
    ]


@pytest.mark.parametrize("action", ["page", "browser"])
async def test_the_retired_reserved_actions_are_no_runners(action):
    """§10p ruling 10. Bug caught: a step no runner will ever read waiting on a browser."""
    run = await run_scenario(
        {"scenario_id": "s", "steps": [{"action": action}], "checks": []}, _app, _Browser()
    )

    assert (run.result, run.blocked_reason) == ("blocked_unverified", "no_runner")


SECRET = "Moonrise-Relay-Ninety"


@pytest.mark.parametrize(
    ("steps", "checks", "refusal"),
    [
        ([{"action": "click", "target": JOIN}], [], "step 1: a run of browser steps begins with visit"),
        ([{"action": "visit", "path": SECRET}], [], "step 1: visit names a path from '/'"),
        ([{"action": "visit", "path": "/"}, {"action": "fill", "target": NAME_BOX, "value": 7}], [],
         "step 2: fill names the text it types"),
        ([{"action": "visit", "path": "/"}, {"action": "click", "target": {"role": "button"}}], [],
         "step 2: a target's names are a non-empty list of text"),
        ([{"action": "visit", "path": "/"},
          {"action": "click", "target": {**JOIN, "near": {**JOIN, "near": JOIN}}}], [],
         "step 2: its near a near target has no near of its own"),
        ([{"action": "visit", "path": "/"}], [{"check": "text", "step": 1, "pattern": "(" + SECRET}],
         "check 1: pattern isn't a pattern"),
        ([{"action": "visit", "path": "/"}], [{"check": "absent", "step": 1, "pattern": "\\A" + SECRET}],
         "check 1: pattern uses Python's syntax, which the browser reads otherwise"),
        ([{"action": "visit", "path": "/"}], [{"check": "text", "step": 1, "pattern": "(?P<n>" + SECRET + ")"}],
         "check 1: pattern uses Python's syntax, which the browser reads otherwise"),
        ([{"action": "visit", "path": "/"}], [{"check": "order", "step": 1, "target": {"role": "listitem"},
                                              "patterns": [SECRET]}],
         "check 1: order names two patterns or more"),
        ([{"action": "visit", "path": "/"}], [{"check": "control", "step": 1, "target": JOIN, "is": SECRET}],
         "check 1: control is one of ('unavailable', 'enabled')"),
        ([{"action": "visit", "path": "/"}], [{"check": "text", "step": 2, "pattern": "x"}],
         "check 1: names a step the scenario has"),
        ([{"action": "http", "method": "GET", "path": "/runs"}], [{"check": "text", "step": 1, "pattern": "x"}],
         "check 1: a text check reads a browser step, and step 1 isn't one"),
        ([{"action": "visit", "path": "/"}], [{"check": "status", "step": 1, "equals": 200}],
         "check 1: a status check reads an HTTP step, and step 1 isn't one"),
        ([{"action": "visit", "path": "/"}, {"action": "fill", "target": NAME_BOX, "value": "x", "if_enabled": True}],
         [], "step 2: if_enabled is a click's, true or false"),
        ([{"action": "http", "method": "GET", "path": "/runs", "if_enabled": True}], [],
         "step 1: if_enabled is a click's, true or false"),
        ([{"action": "visit", "path": "/"}, {"action": "click", "target": JOIN, "if_enabled": SECRET}], [],
         "step 2: if_enabled is a click's, true or false"),
    ],
    ids=[
        "a-segment-that-doesnt-begin-with-visit",
        "a-visit-with-no-path",
        "a-fill-with-no-text",
        "a-target-with-no-names",
        "a-nested-near",
        "a-pattern-that-doesnt-compile",
        "a-python-only-anchor",
        "a-python-only-named-group",
        "an-order-of-one",
        "a-control-state-not-in-the-vocabulary",
        "a-check-on-a-step-that-isnt-there",
        "a-browser-check-on-an-http-step",
        "an-http-check-on-a-browser-step",
        "if-enabled-on-a-fill",
        "if-enabled-on-an-http-step",
        "if-enabled-not-a-boolean",
    ],
)  # fmt: skip
def test_a_malformed_browser_step_or_check_is_refused_by_its_place_never_its_value(
    steps, checks, refusal
):
    """§10p ruling 9. Bug caught: a malformed step accepted, so it fails only when it runs, inside
    the window; or a refusal that echoes the value, which is held out."""
    refusals = vocabulary_refusals(steps, checks)

    assert refusal in refusals
    assert not any(SECRET in r for r in refusals)


def test_a_well_formed_mixed_scenario_and_an_http_only_one_are_refused_nothing():
    """Bug caught: a rule that refuses revision 4's HTTP-only scenarios, an HTTP check with no
    step among them, or the vocabulary's own example."""
    mixed = _joining(
        {"check": "text", "step": 4, "pattern": "{title}\\s+(1|one)"},
        {"check": "control", "step": 4, "target": JOIN, "is": "unavailable"},
        {"check": "order", "step": 2, "target": {"role": "link", "text": "Dawn"}, "patterns": ["a", "b"]},
        {"check": "json", "step": 5, "path": "participants", "length": 1},
    )  # fmt: skip
    http_only = [{"action": "http", "method": "POST", "path": "/runs"}]

    assert vocabulary_refusals(mixed["steps"], mixed["checks"]) == []
    assert vocabulary_refusals(http_only, [{"check": "status", "equals": 201}]) == []


async def test_an_if_enabled_click_is_refused_nothing_and_reaches_the_browser_as_written():
    """#2659. Bugs caught: the draft-time rule refusing a well-formed `if_enabled` click, so a
    two-form outcome can't be written; or the runner's rendering dropping the key, so the driver
    clicks a disabled control and the delivery that disables it reads failed."""
    scenario = _joining()
    scenario["steps"][3] = {**scenario["steps"][3], "if_enabled": True}
    browser = _Browser()

    run = await run_scenario(scenario, _app, browser)

    assert vocabulary_refusals(scenario["steps"], scenario["checks"]) == []
    assert run.result == "passed"
    sent = browser.requests[0].steps
    assert [s.get("if_enabled") for s in sent] == [None, None, True]


async def test_the_run_records_its_runner_and_each_steps_seconds_and_never_the_browsers_text():
    """§10p rulings 1 and 7. Bugs caught: the runner unrecorded, so a change of browser can't be
    read as a methodology break; a step's seconds lost; or the browser's own text, which can quote
    the page and so the scenario's held-out values, copied into the run's detail."""
    passed = await run_scenario(_joining(), _app, _Browser())
    failed = await run_scenario(_joining(), _app, _Browser(outcomes={4: "action_failed"}))

    assert (passed.result, passed.runner) == ("passed", "ev:1 Chrome/155")
    assert len(passed.step_seconds) == 5 and passed.step_seconds[1:4] == (0.25, 0.25, 0.25)
    assert (failed.first_failing_step, failed.detail) == (4, "step 4 action_failed")
    assert len(failed.step_seconds) == 4


async def test_a_run_that_didnt_pass_keeps_its_segments_evidence_and_one_that_passed_none():
    """§10p ruling 8. Bug caught: evidence kept for a passing scenario, which the store would hold
    for nothing, or lost for the one that failed, so its failure can't be read."""

    class _WithEvidence(_Browser):
        async def __call__(self, request):
            answer = await super().__call__(request)
            return BrowseAnswer(answer.steps, answer.checks, answer.browser, {"step": 4})

    failed = await run_scenario(_joining(), _app, _WithEvidence(outcomes={4: "action_failed"}))
    passed = await run_scenario(_joining(), _app, _WithEvidence())

    assert (failed.result, failed.evidence) == ("failed", {"step": 4})
    assert (passed.result, passed.evidence) == ("passed", None)
