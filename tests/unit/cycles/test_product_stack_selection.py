"""SIP-0112 H.26: a repository-backed product runs on its own stack, and its evidence says so.

Entered at ``prepare_cycle`` (the create route's and the Campaign launcher's one path), then at the
real handlers with the cycle's own ``resolved_config()``, as ``test_blueprint_conventions`` does.
The product is invented: a Node library tested by vitest, with no blueprint.

Bugs caught:
- a vitest product falling to ``python_cli``: "You are generating pytest test files", a 4,000-token
  ceiling and a ``.py`` source filter on JavaScript (#2937);
- a mixed or unknown product given one stack's advice that its runners contradict;
- an operator's profile accepted though it contradicts the product's runners;
- the qa image trying a suite only the sandbox can run, and saying what it couldn't do as if it
  were the suite's result;
- a plan-less cycle on such a product quietly back on Python;
- a profile's behaviour changing under a replay or a retry with nothing on the record.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.test_runner import run_build_validation
from squadops.capabilities.qa_prompt_contents import qa_test_prompt_contents
from squadops.cycles.models import PreflightRejectedError
from squadops.cycles.replay import check_replay_compatibility
from squadops.stacks.development_profiles import (
    DEVELOPMENT_PROFILES,
    collected_test_patterns_for,
    development_profile_drift,
    development_profile_fingerprint,
    effective_development_profile,
    matches_test_file_patterns,
)
from tests.unit.cycles.test_blueprint_conventions import (
    _PLAIN,
    _context,
    _first_call,
    _inputs,
    _no_sandbox,  # noqa: F401 - the autouse fixture
    _prepared,
)

_PYTEST = _PLAIN.runners[0]
_VITEST = dataclasses.replace(_PYTEST, runner="vitest", file_pattern="*.test.js", roots=("test",))
_JEST = dataclasses.replace(_VITEST, runner="jest")

_NODE = dataclasses.replace(_PLAIN, runners=(_VITEST,))
_MIXED = dataclasses.replace(_PLAIN, runners=(_PYTEST, _VITEST))
_NODE_VIEW = {
    "commit": "c" * 40,
    "map": "- `src/controller.js`\n- `test/contract.test.js`",
    "checks": [{"id": "contract_tests", "argv": ["npx", "vitest", "run"]}],
    "runners": [
        {"runner": "vitest", "checks": ["contract_tests"], "roots": ["test"],
         "file_pattern": "*.test.js", "covers": ["src/**"]},
    ],
    "instructions": {},
    "existing_files": {},
}  # fmt: skip
_TEST_REPLY = (
    "```javascript:test/steer.test.js\nimport { it } from 'vitest'\nit('x', () => {})\n```\n"
)


def _with_runners(*runners):
    return dataclasses.replace(_PLAIN, runners=runners)


def _selection(prepared) -> dict:
    return prepared.cycle.execution_overrides["development_profile_selection"]


@pytest.mark.parametrize(
    ("derived", "name", "origin"),
    [
        (_NODE, "node_vitest", "derived"),
        (_PLAIN, "python_cli", "derived"),
        (dataclasses.replace(_PLAIN, blueprint_stack="fullstack_fastapi_react"),
         "fullstack_fastapi_react", "blueprint"),
        (_MIXED, "product_neutral", "derived"),
        (_with_runners(_JEST), "product_neutral", "derived"),
        (_with_runners(), "product_neutral", "derived"),
    ],
    ids=["node-vitest", "no-blueprint-python", "blueprint", "mixed", "jest", "no-runner"],
)  # fmt: skip
async def test_a_products_profile_comes_from_its_derived_facts_with_its_provenance(
    derived, name, origin
):
    prepared = await _prepared(derived)

    assert effective_development_profile(prepared.cycle.resolved_config()) == name
    assert _selection(prepared) == {
        "name": name,
        "origin": origin,
        "fingerprint": development_profile_fingerprint(name),
    }


@pytest.mark.parametrize(
    ("derived", "named"),
    [(_NODE, "python_cli"), (_PLAIN, "react_app"), (_PLAIN, "fullstack_fastapi_react")],
    ids=["python-on-node", "react-on-python", "fullstack-without-vitest"],
)
async def test_a_named_profile_that_contradicts_the_products_runners_is_refused(derived, named):
    with pytest.raises(PreflightRejectedError, match="development_profile_conflict"):
        await _prepared(derived, development_profile=named)


@pytest.mark.parametrize(
    ("derived", "named"),
    [(_NODE, "product_neutral"), (_MIXED, "python_cli"), (_with_runners(), "python_cli")],
    ids=["neutral-defers", "one-of-its-runners", "nothing-to-contradict"],
)
async def test_a_named_profile_the_runners_allow_stands_as_the_operators(derived, named):
    prepared = await _prepared(derived, development_profile=named)

    assert _selection(prepared)["name"] == named
    assert _selection(prepared)["origin"] == "operator"


async def test_a_plan_less_node_product_stays_off_python_and_a_python_one_as_it_was():
    planless = {"implementation_plan": False, "typed_acceptance": False}

    node = await _prepared(_NODE, "implement", **planless)
    python = await _prepared(_PLAIN, "implement", **planless)

    assert effective_development_profile(node.cycle.resolved_config()) == "node_vitest"
    assert "development_profile" not in python.cycle.execution_overrides


@pytest.mark.parametrize(
    ("derived", "conventions"),
    [(_NODE, True), (_MIXED, False)],
    ids=["node", "mixed"],
)
async def test_the_test_author_is_never_told_python_on_a_product_that_isnt(derived, conventions):
    """The handler runs for real, its suite left to the product's runner: nothing patched."""
    prepared = await _prepared(derived)
    ctx = _context(_TEST_REPLY)

    inputs = _inputs(prepared.cycle.resolved_config(), "test/steer.test.js", view=_NODE_VIEW)
    inputs["resolved_config"]["output_validation"] = True

    result = await QATestHandler().handle(ctx, inputs)

    messages, _ = _first_call(ctx)
    prompt = messages[0].content + messages[1].content
    assert "pytest" not in prompt
    assert "test_*.py" not in prompt
    assert "a file named `*.test.js` under `test`, testing `src/**`" in prompt
    assert ("### Its stack" in prompt) is conventions

    test_result = result.outputs["test_result"]
    assert test_result["executed"] is False
    assert "pytest" not in test_result["summary"]
    assert test_result["summary"].endswith("its own runner does, in the sandbox")
    report = next(a for a in result.outputs["artifacts"] if a["type"] == "test_report")
    assert "pytest" not in report["content"]
    assert "Python" not in report["content"]
    row = next(
        c for c in result.outputs["validation_result"]["checks"] if c["check"] == "tests_pass"
    )
    assert (row["executed"], row["runner"], row["suite_broken"]) == (False, "product_runner", False)


async def test_the_monolithic_test_prompt_names_vitest_not_pytest():
    """``qa_test.py``'s ``test_prompt_supplement``: under ``python_cli`` this read "You are
    generating pytest test files" on a vitest product."""
    prepared = await _prepared(_NODE)
    ctx = _context(_TEST_REPLY)
    inputs = _inputs(prepared.cycle.resolved_config(), "test/steer.test.js", view=_NODE_VIEW)
    del inputs["subtask_focus"]

    await QATestHandler().handle(ctx, inputs)

    messages, _ = _first_call(ctx)
    prompt = messages[0].content + messages[1].content
    assert "You are generating vitest test files" in prompt
    assert "pytest" not in prompt


async def test_a_retest_leaves_the_suite_to_the_product_runner_too():
    prepared = await _prepared(_NODE)
    ctx = _context("")
    inputs = _inputs(prepared.cycle.resolved_config(), "test/steer.test.js", view=_NODE_VIEW)
    inputs["retest_files"] = [{"path": "test/steer.test.js", "content": "it('x', () => {})"}]

    result = await QATestHandler().handle(ctx, inputs)

    assert result.outputs["test_result"]["executed"] is False
    assert "pytest" not in result.outputs["test_result"]["summary"]


async def test_the_developer_of_a_node_product_gets_its_stack_and_a_real_ceiling():
    prepared = await _prepared(_NODE)
    ctx = _context("```javascript:src/controller.js\nglobalThis.controller = {}\n```\n")

    await DevelopmentDevelopHandler().handle(
        ctx, _inputs(prepared.cycle.resolved_config(), "src/controller.js", view=_NODE_VIEW)
    )

    messages, kwargs = _first_call(ctx)
    user = messages[1].content
    assert "### Its stack" in user
    assert "Python" not in messages[0].content + user
    assert kwargs["max_tokens"] == 12000


@pytest.mark.parametrize(
    ("derived", "path", "is_test"),
    [
        (_NODE, "test/steer.test.js", True),
        (_NODE, "test/steer.spec.mjs", True),
        (_NODE, "src/controller.js", False),
        (_MIXED, "tests/test_api.py", True),
        (_MIXED, "web/view.test.tsx", True),
        (_MIXED, "src/api.py", False),
    ],
)
async def test_a_products_files_are_classified_by_their_own_language(derived, path, is_test):
    prepared = await _prepared(derived)
    patterns = collected_test_patterns_for(prepared.cycle.resolved_config())

    assert matches_test_file_patterns(path, patterns) is is_test


async def test_the_test_author_of_a_node_product_is_shown_its_javascript_source():
    """``.py`` was the only source filter, so a test author saw no JavaScript at all."""
    prepared = await _prepared(_NODE)
    inputs = _inputs(prepared.cycle.resolved_config(), "test/steer.test.js", view=_NODE_VIEW)
    inputs["artifact_contents"] = {"src/controller.js": "1", "test/steer.test.js": "2"}
    del inputs["subtask_focus"]  # the monolithic prompt shows source; a focused one, its package

    shown = qa_test_prompt_contents(inputs)

    assert "src/controller.js" in shown
    assert "test/steer.test.js" not in shown


async def test_the_image_runs_nothing_for_a_product_left_to_its_runner():
    """No suite, and no build or boot check: both would read the image, not the product."""
    source = [{"path": "src/controller.js", "content": "syntax error ("}]
    tests = [{"path": "test/a.test.js", "content": "it('x', () => {})"}]

    result = await run_build_validation("product_runner", source, tests)

    assert (result.executed, result.suite_broken) == (False, False)
    assert result.frontend_build is None


async def test_no_test_files_stays_the_own_artifact_verdict_for_a_product_too():
    result = await run_build_validation("product_runner", [], [])

    assert (result.executed, result.suite_broken, result.error) == (
        False, True, "no test files provided"
    )  # fmt: skip


def test_a_replay_across_a_changed_profile_is_refused_by_name():
    source = {"prd_ref": "p", "development_profile_fingerprint": "aaaa"}
    target = {"prd_ref": "p", "development_profile_fingerprint": "bbbb"}

    assert check_replay_compatibility(source, source) == []
    assert check_replay_compatibility(source, target) == [
        "replay_incompatible: development_profile_fingerprint differs "
        "(source='aaaa', target='bbbb')"
    ]


async def test_a_retry_names_a_profile_that_changed_since_it_was_selected(monkeypatch):
    prepared = await _prepared(_NODE)
    overrides = prepared.cycle.execution_overrides
    selected = overrides["development_profile_selection"]["fingerprint"]

    assert development_profile_drift(overrides) is None

    changed = dataclasses.replace(DEVELOPMENT_PROFILES["node_vitest"], max_completion_tokens=1)
    monkeypatch.setitem(DEVELOPMENT_PROFILES, "node_vitest", changed)

    assert development_profile_drift(overrides) == {
        "name": "node_vitest",
        "selected": selected,
        "current": development_profile_fingerprint("node_vitest"),
    }


@pytest.mark.parametrize(
    "overrides",
    [None, {}, {"development_profile_selection": {"name": "gone", "fingerprint": "x"}}],
    ids=["none", "an-older-cycle", "a-profile-no-longer-registered"],
)
def test_a_cycle_with_no_readable_selection_has_no_drift(overrides):
    assert development_profile_drift(overrides) is None
