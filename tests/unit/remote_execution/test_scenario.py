"""A frozen scenario's declaration, digest and baseline rule (SIP-0117 R5.8; #3044)."""

from __future__ import annotations

import copy

import pytest

from adapters.remote_execution.fixture_operation_runner import VOCABULARY
from squadops.remote_execution.models import AssertionOutcome
from squadops.remote_execution.scenario import (
    ABSENT,
    BaselineVerdict,
    Expectation,
    ExpectOp,
    ScenarioRefused,
    ScenarioVocabulary,
    baseline_verdict,
    expectation_met,
    frozen_scenario,
    parse_text,
    read_declaration,
)
from tests.unit.remote_execution.scenario_fixture import DOOR_OPENS

P, F = AssertionOutcome.PASSED, AssertionOutcome.FAILED


def test_the_digest_is_pinned_to_the_canonical_text():
    """Bug caught: a change to the canonical form (key order, separators, escaping). Every
    scenario frozen before it would digest differently, and no stored reading would be
    credited again."""
    frozen = frozen_scenario(DOOR_OPENS, VOCABULARY)

    assert frozen.document.startswith('{"assertions":[{"expect":{"op":"greater_than","value":0}')
    assert frozen.digest == (
        "sha256:2c8f53632b8c32de82bcf9e5c180d21e944b14edd2ae5e3667fe0b0eeaec324f"
    )
    assert (frozen.assertions, frozen.named_assertion) == (("spawned", "door-open"), "door-open")


def _with(change):
    document = copy.deepcopy(DOOR_OPENS)
    change(document)
    return document


@pytest.mark.parametrize(
    ("change", "defect"),
    [
        (lambda d: d.update(code="print(1)"), "keys outside squadops.scenario/1: ['code']"),
        (
            lambda d: d["steps"].append({"action": "execute_luau", "code": "x"}),
            "steps[2]: action 'execute_luau' is outside fixture/1's vocabulary",
        ),
        (
            lambda d: d["assertions"][1]["observe"].update(kind="script_source"),
            "assertions[1].observe: observation 'script_source' is outside",
        ),
        (
            lambda d: d["assertions"][1]["observe"].update(context="studio"),
            "assertions[1].observe: 'context' is 'studio'",
        ),
        (lambda d: d.update(named_assertion="door-closed"), "which no assertion declares"),
        (
            lambda d: d["assertions"].append(copy.deepcopy(d["assertions"][0])),
            "assertion 'spawned' is declared twice",
        ),
        (lambda d: d.update(assertions=[]), "a scenario that asserts nothing verifies nothing"),
        (
            lambda d: d["steps"][0].update(deadline_s=600),
            "steps[0].deadline_s is a number of seconds above 0, at most 60",
        ),
        (lambda d: d["steps"][0].update(point=[1, 2]), "steps[0].point is three finite numbers"),
        (
            lambda d: d["assertions"][0]["expect"].update(value="many"),
            "greater_than compares with a number",
        ),
        (
            lambda d: d["assertions"][1]["expect"].update(op="absent"),
            "'absent' takes no value",
        ),
        (lambda d: d.update(reader="studio/1"), "'reader' is 'studio/1'"),
        (lambda d: d["steps"][1].pop("path"), "missing arguments ['path']"),
    ],
)
def test_a_declaration_outside_the_vocabulary_or_the_schema_is_refused_by_name(change, defect):
    """Bug caught: a declaration frozen with an action the harness doesn't execute, a key the
    reader ignores, or a value it would coerce. Each is refused when it is frozen, and
    nothing in it is dropped or filled in."""
    with pytest.raises(ScenarioRefused) as refused:
        read_declaration(_with(change), VOCABULARY)

    assert any(defect in d for d in refused.value.defects), refused.value.defects


def test_every_defect_is_named_at_once():
    """Bug caught: the author shown only the first defect, and refused again for the next."""
    with pytest.raises(ScenarioRefused) as refused:
        read_declaration(
            _with(lambda d: d.update(schema="v0", named_assertion="nope", extra=1)), VOCABULARY
        )

    assert len(refused.value.defects) == 3


@pytest.mark.parametrize(
    ("text", "defect"),
    [
        ('{"a": 1, "a": 2}', "repeats the keys ['a']"),
        ('{"a": NaN}', "holds NaN"),
        ("{", "isn't JSON"),
    ],
)
def test_a_text_with_a_repeated_key_or_nan_is_refused_rather_than_read(text, defect):
    """Bug caught: json.loads keeping the last of two keys, or reading NaN, so the scenario
    run is not the one its author's text shows."""
    with pytest.raises(ScenarioRefused, match=defect.replace("[", r"\[").replace("]", r"\]")):
        parse_text(text)


@pytest.mark.parametrize(
    ("op", "value", "observed", "met"),
    [
        (ExpectOp.EQUALS, False, False, True),
        # True == 1 in Python: a declaration expecting true is never met by the number 1.
        (ExpectOp.EQUALS, True, 1, False),
        (ExpectOp.EQUALS, 1, 1.0, True),
        (ExpectOp.NOT_EQUALS, True, 1, True),
        (ExpectOp.EQUALS, "absent", ABSENT, False),
        (ExpectOp.NOT_EQUALS, False, ABSENT, True),
        (ExpectOp.ABSENT, None, ABSENT, True),
        (ExpectOp.ABSENT, None, "absent", False),
        (ExpectOp.GREATER_THAN, 0, 100, True),
        (ExpectOp.GREATER_THAN, 0, "100", False),
        (ExpectOp.LESS_THAN, 5, ABSENT, False),
        (ExpectOp.CONTAINS, "Open", "Door Open", True),
        (ExpectOp.CONTAINS, "1", 10, False),
    ],
)
def test_an_expectation_compares_values_of_its_own_kind_and_never_coerces(op, value, observed, met):
    """Bug caught: a coerced comparison ("100" > 0, True == 1) or an absent instance read as a
    property whose text happens to be "absent"."""
    assert expectation_met(Expectation(op, value), observed) is met


@pytest.mark.parametrize(
    ("outcomes", "verdict"),
    [
        ({"spawned": P, "door-open": F}, BaselineVerdict.MAY_START),
        ({"spawned": P, "door-open": P}, BaselineVerdict.PASSES_ON_BASELINE),
        ({"spawned": F, "door-open": F}, BaselineVerdict.PRECONDITION_FAILS),
        # A gap is judged first: a pass beside an unexecuted precondition still blocks.
        ({"spawned": AssertionOutcome.SETUP_FAILED, "door-open": P}, BaselineVerdict.BLOCKED),
        ({"spawned": P, "door-open": AssertionOutcome.WRONG_CONTEXT}, BaselineVerdict.BLOCKED),
        # The named assertion with no record is missing, never a failure.
        ({"spawned": P}, BaselineVerdict.BLOCKED),
        # A pass beside a failed precondition is a pass: the scenario proves nothing.
        ({"spawned": F, "door-open": P}, BaselineVerdict.PASSES_ON_BASELINE),
    ],
)
def test_the_baseline_rule_blocks_a_gap_first_then_refuses_a_pass_then_a_failed_precondition(
    outcomes, verdict
):
    """Bug caught: development started on a scenario that didn't run, or that passes on the
    baseline, or whose world isn't the baseline's; or the order differing from Campaign
    acceptance's reading of the same record (#3053)."""
    assert baseline_verdict(outcomes, "door-open")[0] is verdict


def test_the_baseline_verdict_names_what_didnt_execute():
    """Bug caught: a blocked increment whose reason doesn't say which assertion, or why."""
    verdict, why = baseline_verdict({"spawned": AssertionOutcome.SETUP_FAILED}, "door-open")

    assert verdict is BaselineVerdict.BLOCKED
    assert why == "not executed on the baseline: door-open (missing), spawned (setup_failed)"


@pytest.mark.parametrize(
    ("document", "defect"),
    [
        (["property", "value"], "is an object"),
        ({"reader": "x/1"}, "missing keys"),
        (
            {"reader": "x/1", "contexts": [], "actions": {"a": {}}, "observations": {"o": {}}},
            "'contexts' is a non-empty list",
        ),
        (
            {
                "reader": "x/1",
                "contexts": ["server"],
                "actions": {"a": {"path": "string"}},
                "observations": {"o": {}},
            },
            "actions.a",
        ),
        (
            {"reader": "x/1", "contexts": ["server"], "actions": {}, "observations": {"o": {}}},
            "'actions' is a non-empty object",
        ),
    ],
)
def test_a_vocabulary_document_that_cant_be_read_is_refused(document, defect):
    """Bug caught: a provider's vocabulary with an argument kind no validator checks, so a
    declaration's argument is accepted unchecked."""
    with pytest.raises(ValueError, match=defect):
        ScenarioVocabulary.from_document(document)
