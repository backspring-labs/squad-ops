"""The skills replay's cases and judgement (SIP-0116 §17p; #3041).

What bugs would these catch? A case read with a field dropped, so it runs as another case under
its name; a stop case counted as passing because the handler failed for any reason; an
expectation nothing was run for read as met; a baseline-style success hiding a stop.
"""

from __future__ import annotations

import pytest

from squadops.memory.skill_replay import (
    MET,
    NOT_JUDGED,
    NOT_MET,
    SkillCasesError,
    judge,
    read_cases,
)

pytestmark = [pytest.mark.domain_memory]

_CASES = """\
# Skill cases `fixture-skills@2`
cases:
  - id: strategy-unobservable
    task_type: strategy.propose_increment
    skillset: fixture-design
    vocabulary_skillset: fixture-qa
    why: an effect the reader can't observe is refused by name
    swaps:
      - path: [resolved_config, campaign_proposal, objective, statement]
        value: A chime plays when gold is picked up.
    expect: {stop: "no scenario:"}
  - id: qa-capture
    task_type: qa.test
    skillset: fixture-qa
    expect: {accepted: true, emits: ["tests/*.spec.luau"], specs_pass: true}
"""
_STOP = {"skillset": "s", "skill": "k", "opening": "no scenario:", "line": "no scenario: a sound"}
_SPEC = {"name": "tests/Shop.spec.luau", "content": "x"}
_REQUEST = {
    "name": "change_request.yaml",
    "content": "criteria:\n  - {id: S1, surface_kind: scenario}\n  - {id: T1, surface_kind: package}\n",
}


def test_the_cases_file_reads_each_case_whole_and_names_itself():
    cases = read_cases(_CASES)

    assert cases.id == "fixture-skills@2"
    first, second = cases.cases
    assert first.notes() == {
        "case": "strategy-unobservable",
        "skillset": "fixture-design",
        "vocabulary_skillset": "fixture-qa",
        "swaps": [
            {
                "path": ["resolved_config", "campaign_proposal", "objective", "statement"],
                "value": "A chime plays when gold is picked up.",
            }
        ],
        "expect": {"stop": "no scenario:"},
    }
    assert (second.id, second.task_type, second.swaps, second.vocabulary_skillset) == (
        "qa-capture",
        "qa.test",
        (),
        "",
    )


@pytest.mark.parametrize(
    ("old", "new", "says"),
    [
        ("# Skill cases `fixture-skills@2`", "# Cases", "the first line is"),
        ("id: qa-capture", "id: strategy-unobservable", "strategy-unobservable is given twice"),
        ("id: qa-capture", "id: QA Capture", "lower-case letters, digits and hyphens"),
        ("    skillset: fixture-qa\n    expect: {acc", "    expect: {acc", "skillset is a name"),
        ("why: an effect", "because: an effect", "unknown fields because"),
        ('expect: {stop: "no scenario:"}', "expect: {stop: no scenario}", "ending in a colon"),
        (
            'expect: {stop: "no scenario:"}',
            'expect: {stop: "no scenario:", accepted: true}',
            "stop stands alone",
        ),
        ("specs_pass: true", "specs_pass: false", "specs_pass is true, or left out"),
        ('emits: ["tests/*.spec.luau"]', "emits: tests", "emits is a list of path patterns"),
        ("accepted: true, emits", "accepts: true, emits", "unknown accepts"),
        ("      - path: [resolved_config", "      - at: [resolved_config", "each with a path"),
    ],
    ids=[
        "no-header",
        "id-twice",
        "bad-id",
        "no-skillset",
        "unknown-field",
        "stop-without-colon",
        "stop-with-more",
        "false-expectation",
        "emits-not-a-list",
        "unknown-expectation",
        "swap-without-path",
    ],
)
def test_a_cases_file_with_a_defect_is_refused_by_name(old, new, says):
    assert old in _CASES

    with pytest.raises(SkillCasesError, match=says):
        read_cases(_CASES.replace(old, new))


def test_every_defect_of_a_cases_file_is_named_in_one_pass():
    text = _CASES.replace("why: an effect", "because: an effect").replace(
        "specs_pass: true", "specs_pass: false"
    )

    with pytest.raises(SkillCasesError) as refused:
        read_cases(text)

    assert "unknown fields because" in str(refused.value)
    assert "specs_pass is true" in str(refused.value)


#: A suite the qa image left to the product's own runner (#3150): unsuccessful, with no verdict.
_HANDED = {"left_to_the_product_runner": True}


@pytest.mark.parametrize(
    ("expect", "record", "specs", "verdict", "finding"),
    [
        ({"stop": "no scenario:"}, {"success": False, "skill_stop": _STOP}, None, MET, None),
        (
            {"stop": "no scenario:"},
            {"success": False, "error": "refused after its revision budget"},
            None,
            NOT_MET,
            "no declared stop was read",
        ),
        (
            {"stop": "saved data:"},
            {"success": False, "skill_stop": _STOP},
            None,
            NOT_MET,
            "the stop read opens 'no scenario:', not 'saved data:'",
        ),
        (
            {"accepted": True},
            {"success": False, "skill_stop": _STOP, "error": "stopped"},
            None,
            NOT_MET,
            "the task was stopped by its skill: no scenario: a sound",
        ),
        (
            {"accepted": True, "emits": ["tests/*.spec.luau"]},
            {"success": True, "artifacts": [_SPEC]},
            None,
            MET,
            None,
        ),
        (
            {"emits": ["tests/*.spec.luau", "src/Shared/**"]},
            {"success": True, "artifacts": [_SPEC]},
            None,
            NOT_MET,
            "no emitted file matches src/Shared/**",
        ),
        (
            {"emits_expected": True},
            {
                "success": True,
                "artifacts": [_SPEC],
                "expected_artifacts": [_SPEC["name"]],
            },
            None,
            MET,
            None,
        ),
        (
            {"emits_expected": True},
            {
                "success": True,
                "artifacts": [_SPEC],
                "expected_artifacts": [_SPEC["name"], "src/Shared/Modules/Pricing.luau"],
            },
            None,
            NOT_MET,
            "the task expected src/Shared/Modules/Pricing.luau, and it was not emitted",
        ),
        (
            {"emits_expected": True},
            {"success": True, "artifacts": [_SPEC]},
            None,
            NOT_MET,
            "the task expected no file",
        ),
        (
            {"scenario_criterion": True},
            {"success": True, "artifacts": [_REQUEST]},
            None,
            MET,
            None,
        ),
        (
            {"scenario_criterion": True},
            {
                "success": True,
                "artifacts": [
                    {**_REQUEST, "content": "criteria:\n  - {id: T1, surface_kind: package}\n"}
                ],
            },
            None,
            NOT_MET,
            "no criterion is a scenario (kinds: package)",
        ),
        (
            {"scenario_criterion": True},
            {"success": False, "error": "refused", "artifacts": []},
            None,
            NOT_MET,
            "no change_request.yaml was accepted",
        ),
        (
            {"specs_pass": True},
            {"success": True, "artifacts": [_SPEC]},
            None,
            NOT_JUDGED,
            "the emitted specs were not run on the product",
        ),
        (
            {"specs_pass": True},
            {"success": True, "artifacts": [_SPEC]},
            {"passed": ["Shop > pays the bonus"], "failed": []},
            MET,
            None,
        ),
        (
            {"specs_pass": True},
            {"success": True, "artifacts": [_SPEC]},
            {"passed": ["a"], "failed": ["Shop > rounds down"]},
            NOT_MET,
            "1 passing and 1 failing: Shop > rounds down",
        ),
        (
            {"specs_pass": True},
            {"success": True, "artifacts": [_SPEC]},
            {"passed": [], "failed": []},
            NOT_MET,
            "0 passing and 0 failing",
        ),
        (
            {"accepted": True, "specs_pass": True},
            {"success": False, "error": "Tests not executed", "artifacts": [_SPEC], **_HANDED},
            {"passed": ["Shop > pays the bonus"], "failed": []},
            MET,
            None,
        ),
        (
            {"accepted": True},
            {"success": False, "error": "Tests not executed", "artifacts": [_SPEC], **_HANDED},
            None,
            NOT_JUDGED,
            "accepted: the emitted specs were not run on the product",
        ),
        (
            {"accepted": True},
            {"success": False, "error": "Tests not executed", "artifacts": [_SPEC], **_HANDED},
            {"passed": [], "failed": ["Shop > rounds down"]},
            NOT_MET,
            "0 passing and 1 failing: Shop > rounds down",
        ),
        (
            {"accepted": True},
            {"success": False, "error": "refused after its revision budget", "artifacts": []},
            {"passed": ["a"], "failed": []},
            NOT_MET,
            "the handler refused the answer: refused after its revision budget",
        ),
        (
            {"discriminates": True},
            {"success": True, "artifacts": [_SPEC]},
            None,
            NOT_JUDGED,
            "discriminates: the emitted specs were not run on the product",
        ),
        (
            {"discriminates": True},
            {"success": True, "artifacts": [_SPEC]},
            {"discrimination": {_SPEC["name"]: "discriminates"}},
            MET,
            None,
        ),
        (
            {"discriminates": True},
            {"success": True, "artifacts": [_SPEC]},
            {"discrimination": {_SPEC["name"]: "only_setup_failures"}},
            NOT_MET,
            "doesn't prove its change: only_setup_failures",
        ),
        (
            {"discriminates": True},
            {"success": True, "artifacts": [_SPEC]},
            {"passed": ["a"], "failed": [], "discrimination": {}},
            NOT_MET,
            "no emitted spec was run before and after its change",
        ),
    ],
    ids=[
        "the-stop",
        "a-failure-that-is-no-stop",
        "another-skills-stop",
        "stopped-where-work-was-expected",
        "emitted",
        "one-pattern-unmatched",
        "the-tasks-own-files",
        "one-expected-file-missing",
        "no-file-expected",
        "a-scenario-criterion",
        "no-scenario-among-the-criteria",
        "nothing-accepted",
        "specs-not-run",
        "specs-passed",
        "a-spec-failed",
        "no-spec-ran",
        "handed-off-and-passing-on-the-product",
        "handed-off-and-not-run",
        "handed-off-and-failing-on-the-product",
        "a-refusal-is-still-a-refusal",
        "discrimination-not-run",
        "the-spec-proves-its-change",
        "the-spec-cant-load-before",
        "no-spec-judged",
    ],
)
def test_an_authoring_is_judged_by_the_handlers_verdict_and_the_stop_read(
    expect, record, specs, verdict, finding
):
    judged = judge(expect, record, specs=specs)

    assert judged["verdict"] == verdict
    if finding is None:
        assert judged["findings"] == []
    else:
        assert any(finding in f for f in judged["findings"]), judged["findings"]


# roblox-skills-v4 (#3199): the gate's rules, by rule. The values are invented: a tide timer that
# counts down, a harbour sign that shows on the dock and hides at sea.

_TIMER = {"kind": "gui_state", "state": "text", "path": "@player.PlayerGui.HUD.*"}
_RULES = {
    "sentences": [
        {"says": "The HUD counts down to the tide", "read_by": ["Band:"]},
        {"says": "At sea the sign is hidden", "read_by": ["at sea"]},
    ],
    "headless_half": True,
    "unreachable": [{"kind": "attribute", "path": "@player", "name": "AtSea"}],
    "baseline_attributes": True,
    "changing": [_TIMER],
    "named": [
        {
            "match": _TIMER,
            "fails_on": ["Tide in 50 s", "37", None],
            "passes_on": ["Tide in 39 s", "Tide in 31 s", "Tide in 22 s"],
        }
    ],
}


def _criterion(cid, op, value, observable, *, wait=None):
    observe = {"kind": "gui_state", "path": "@player.PlayerGui.HUD.TideLabel", "state": "text"}
    steps = [{"action": "wait_until", "observe": wait, "expect": {"op": "equals", "value": 1}}]
    return {
        "id": cid,
        "statement": "The tide label counts down",
        "surface_kind": "scenario",
        "observable": observable,
        "scenario": {
            "setup": [],
            "steps": steps if wait else [],
            "assertions": [
                {"id": "tide", "observe": observe, "expect": {"op": op, "value": value}}
            ],
            "named_assertion": "tide",
        },
    }


_HEADLESS = {
    "id": "P1",
    "surface_kind": "package",
    "statement": "The sign's rule hides it at sea",
    "observable": "Headless. SignRules.shows('sea') is false. Not played: no action sails. "
    "Fails on: a sign that always shows.",
}


def _record(*criteria, prd_delta=()):
    import yaml

    request = {"criteria": list(criteria), "prd_delta": list(prd_delta)}
    return {
        "success": True,
        "artifacts": [{"name": "change_request.yaml", "content": yaml.safe_dump(request)}],
    }


def _judged(record):
    return judge({"scenario_rules": _RULES}, record, baseline_attributes=["Stamina"])


_GOOD = "Played. The label holds 'in 3'. Fails on: a label stuck at 50, and a bare number. Band: from the HUD."


def test_a_request_that_answers_every_rule_meets_them():
    """Bug caught: a correct answer read as failing a rule, so the skill is refused for following
    it."""
    verdict = _judged(_record(_criterion("S1", "contains", "in 3", _GOOD), _HEADLESS))

    assert verdict == {"verdict": MET, "findings": []}


@pytest.mark.parametrize(
    ("criterion", "says"),
    [
        # The window's B-2 v1: a format-only check passes on a clock that never moves.
        (
            _criterion("S1", "contains", "Tide in", _GOOD),
            "passes on a broken build reading 'Tide in 50 s'",
        ),
        # B-2 v2: the exact text at one instant fails on correct work.
        (_criterion("S1", "equals", "Tide in 31 s", _GOOD), "exact match on a value that changes"),
        # A not_equals passes wherever the label is missing.
        (_criterion("S1", "not_equals", "Tide in 50 s", _GOOD), "<absent>"),
        # A band that holds the first value can't tell a stuck label from a working one.
        (
            _criterion("S1", "contains", "in 5", _GOOD),
            "passes on a broken build reading 'Tide in 50 s'",
        ),
        # A band no correct reading reaches.
        (_criterion("S1", "contains", "in 9", _GOOD), "passes on no reading a correct build shows"),
        (
            _criterion("S1", "contains", "in 3", _GOOD.replace(" Band: from the HUD.", "")),
            "with no 'Band:'",
        ),
        (
            _criterion("S1", "contains", "in 3", _GOOD.replace("Played. ", "")),
            "doesn't open 'Played.'",
        ),
        (
            _criterion("S1", "contains", "in 3", _GOOD.replace("Fails on:", "Breaks on:")),
            "names no broken build",
        ),
        # B-1 v2: a wait on a state no action reaches.
        (
            _criterion(
                "S1",
                "contains",
                "in 3",
                _GOOD,
                wait={"kind": "attribute", "path": "@player", "name": "AtSea"},
            ),
            "steps 1 reads @player AtSea, which no action reaches",
        ),
        (
            _criterion(
                "S1",
                "contains",
                "in 3",
                _GOOD,
                wait={"kind": "attribute", "path": "@player", "name": "Tide"},
            ),
            "the attribute Tide, which the baseline doesn't set",
        ),
    ],
)
def test_each_returned_shape_is_named(criterion, says):
    """Bug caught: a rule that reads the window's returned shapes as met, so the replay passes a
    skill that still writes them."""
    verdict = _judged(_record(criterion, _HEADLESS))

    assert verdict["verdict"] == NOT_MET
    assert any(says in f for f in verdict["findings"]), verdict["findings"]


def test_an_attribute_the_change_says_it_adds_is_reachable():
    """Bug caught: every wait on what the change adds read as one nothing sets, so a correct
    proposal is refused."""
    criterion = _criterion(
        "S1",
        "contains",
        "in 3",
        _GOOD,
        wait={"kind": "attribute", "path": "@player", "name": "Tide"},
    )
    record = _record(
        criterion,
        _HEADLESS,
        prd_delta=[{"id": "d", "op": "add", "text": "The server keeps a Tide attribute"}],
    )

    assert _judged(record)["verdict"] == MET


def test_the_lobby_half_alone_is_named_twice():
    """Bug caught (the window's B-1 v1): a request that reads only the half a play reaches passes,
    since every check it has is a good one."""
    verdict = _judged(_record(_criterion("S1", "contains", "in 3", _GOOD)))

    assert verdict["findings"] == [
        "no criterion reads the item's sentence 'At sea the sign is hidden'",
        "no criterion is headless, and part of the item is a state no play reaches",
    ]


def test_a_headless_criterion_that_hides_what_it_left_unplayed_is_named():
    headless = {
        **_HEADLESS,
        "observable": "Headless. SignRules.shows('sea') is false at sea. Fails on: one that shows.",
    }
    verdict = _judged(_record(_criterion("S1", "contains", "in 3", _GOOD), headless))

    assert verdict["findings"] == ["P1: a headless criterion doesn't say what no play reached"]


def test_no_accepted_request_is_a_finding_not_a_pass():
    assert _judged({"success": False, "error": "refused", "artifacts": []})["findings"] == [
        "the handler refused the answer: refused",
        "no change_request.yaml was accepted",
    ]


@pytest.mark.parametrize(
    ("rules", "says"),
    [
        ({}, "names the facts"),
        ({"headless_half": "yes"}, "headless_half is true"),
        ({"sentences": [{"says": "x"}]}, "sentence 1 is"),
        ({"changing": [{"colour": "red"}]}, "changing 1 matches by"),
        (
            {"named": [{"match": _TIMER, "fails_on": ["x"]}]},
            "named 1 lists the readings correct builds show",
        ),
        ({"reachable": []}, "unknown reachable"),
        # A product's code stays in its repository: the names are never written in the cases.
        ({"baseline_attributes": ["Stamina"]}, "read from the product's checkout"),
    ],
)
def test_a_cases_file_with_misstated_rules_is_refused(rules, says):
    """Bug caught: a rule written wrong in the cases file silently checking nothing."""
    text = _CASES.replace(
        'expect: {stop: "no scenario:"}',
        "expect: " + __import__("json").dumps({"scenario_rules": rules}),
    )

    with pytest.raises(SkillCasesError, match=says):
        read_cases(text)


def test_with_no_checkout_the_attribute_rule_is_not_judged_never_met():
    """Bug caught: a replay run with no product checkout reading the attribute rule as met, so a
    wait on an attribute nothing sets passes unread."""
    wait = {"kind": "attribute", "path": "@player", "name": "Tide"}
    verdict = judge(
        {"scenario_rules": _RULES},
        _record(_criterion("S1", "contains", "in 3", _GOOD, wait=wait), _HEADLESS),
    )

    assert verdict == {
        "verdict": NOT_JUDGED,
        "findings": [
            "scenario_rules: the baseline's attributes were not read (no product checkout)"
        ],
    }
