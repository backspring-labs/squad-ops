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
