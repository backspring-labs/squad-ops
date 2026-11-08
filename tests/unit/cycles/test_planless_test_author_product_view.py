"""SIP-0112 H.29: a plan-less product cycle's test author is shown the product.

A plan's ``qa.test`` takes the focused prompt, which shows the product's repository view: its map,
its conventions, how it is checked and where its runners find a test (H.11, H.13). A plan-less
cycle's takes the monolithic prompt (``request.qa_test.test_validate``), which showed none of it:
its author wrote a suite for a product it had never been shown the layout or the runners of, under
a harness paragraph about a scaffold the product doesn't have.

Entered at ``prepare_cycle`` on the ``implement`` profile with no plan (``implementation_plan`` and
``typed_acceptance`` off), then at ``QATestHandler.handle`` with the cycle's own ``resolved_config()``
and a repository view in the shape the dispatch builds, rendered with the shipped assets. The
products are invented, as in ``test_blueprint_conventions`` and ``test_product_stack_selection``.

Bugs caught:
- the plan-less test author of a product shown no map and no runners, so it places its suite by
  guesswork;
- the scaffold's harness paragraph shown to a product, or taken from a sample application;
- the profile's prose for a skeleton shown where the view shows the stack's conventions for a
  product in its place, as the developer's never is (H.13).
"""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest

from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.stacks.development_profiles import (
    DEVELOPMENT_PROFILES,
    effective_development_profile,
)
from tests.unit.cycles.test_blueprint_conventions import (
    _PLAIN,
    _SKELETON_PLACEMENT,
    _context,
    _first_call,
    _made_from,
    _no_sandbox,  # noqa: F401 - the autouse fixture
    _prepared,
)
from tests.unit.cycles.test_product_stack_selection import _NODE, _NODE_VIEW

_PLANLESS = {"implementation_plan": False, "typed_acceptance": False}
_PRODUCT_HEADING = "## THE PRODUCT YOU ARE CHANGING"
_HARNESS_HEADING = "## Test boundary — consume the scaffold-provided harness"

#: Tally's view: unittest under ``checks`` (the shared fixture's profile).
_TALLY_VIEW = {
    "commit": "c" * 40,
    "map": "- `tally/ledger.py`\n- `checks/check_ledger.py`",
    "checks": [{"id": "ledger", "argv": ["python3", "-m", "unittest", "discover", "-s", "checks"]}],
    "runners": [
        {"runner": "unittest", "checks": ["ledger"], "roots": ["checks"],
         "file_pattern": "check_*.py", "covers": ["tally/**"]},
    ],
    "instructions": {},
    "existing_files": {},
}  # fmt: skip
_TALLY_RUNNER = "a file named `check_*.py` under `checks`, testing `tally/**`"
_NODE_RUNNER = "a file named `*.test.js` under `test`, testing `src/**`"


@pytest.fixture(autouse=True)
def _no_run(monkeypatch):
    """The qa image's own run is not what is under test here."""

    async def _not_run(*_a, **_k):
        return MagicMock(executed=False, tests_passed=False, exit_code=None, summary="not run")

    monkeypatch.setattr(
        "squadops.capabilities.handlers.cycle.qa_test.run_build_validation", _not_run
    )


async def _monolithic_prompt(resolved_config: dict, view: dict | None, contents: dict) -> str:
    """The plan-less test author's user prompt, as the model is sent it."""
    inputs = {
        "prd": "Readers can mark a ledger entry as settled.",
        "resolved_config": {**resolved_config, "output_validation": False},
        "artifact_contents": contents,
    }
    if view is not None:
        inputs["source_repository"] = view
    ctx = _context("```python:checks/check_settle.py\ndef test_settle():\n    assert True\n```\n")

    await QATestHandler().handle(ctx, inputs)

    messages, _ = _first_call(ctx)
    return messages[1].content


@pytest.mark.parametrize(
    ("derived", "view", "runner", "contents", "profile"),
    [
        # Tally: Python, no blueprint, so not pinned (H.26), and python_cli's supplement stays
        (_PLAIN, _TALLY_VIEW, _TALLY_RUNNER, {"tally/ledger.py": "def settle(): ...\n"},
         "python_cli"),
        # a Node product, pinned to node_vitest (H.26 point 5): its conventions in the supplement's
        # place
        (_NODE, _NODE_VIEW, _NODE_RUNNER, {"src/controller.js": "export const steer = 1\n"},
         "node_vitest"),
        # made from a blueprint: a plan-less cycle isn't pinned to it (H.13 point 3)
        (_made_from("fullstack_fastapi_react"), _TALLY_VIEW, _TALLY_RUNNER,
         {"tally/ledger.py": "def settle(): ...\n"}, "python_cli"),
    ],
    ids=["python-product", "node-product", "blueprint-product"],
)  # fmt: skip
async def test_a_plan_less_products_test_author_is_shown_the_product(
    derived, view, runner, contents, profile
):
    prepared = await _prepared(derived, "implement", **_PLANLESS)
    config = prepared.cycle.resolved_config()
    assert effective_development_profile(config) == profile

    prompt = await _monolithic_prompt(config, view, contents)

    assert _PRODUCT_HEADING in prompt
    assert view["map"] in prompt
    assert runner in prompt
    # what the suite tests, as before
    assert all(f"### {path}" in prompt for path in contents)
    assert _HARNESS_HEADING not in prompt
    assert [p for p in _SKELETON_PLACEMENT if p in prompt] == []
    supplement = DEVELOPMENT_PROFILES[profile].test_prompt_supplement
    conventions = bool(DEVELOPMENT_PROFILES[profile].product_conventions_template)
    assert (supplement in prompt) is not conventions
    assert ("### Its stack" in prompt) is conventions


async def test_a_profile_with_product_conventions_never_shows_its_skeleton_prose():
    """An operator may name a blueprint's profile on a plan-less product cycle (the pin lets an
    operator's choice stand). Bug caught: its supplement, which places tests under the scaffold's
    ``__tests__/`` and calls the scaffold's ``@/lib/store``, reaching the product's test author."""
    nextjs_product = dataclasses.replace(_NODE, blueprint_stack="nextjs_ts")
    prepared = await _prepared(
        nextjs_product, "implement", development_profile="nextjs_ts", **_PLANLESS
    )
    view = {**_NODE_VIEW, "runners": [{**_NODE_VIEW["runners"][0], "file_pattern": "*.test.ts"}]}

    prompt = await _monolithic_prompt(
        prepared.cycle.resolved_config(), view, {"src/controller.ts": "export const x = 1\n"}
    )

    assert "### The blueprint it was made from" in prompt
    assert "a file named `*.test.ts` under `test`" in prompt
    assert "Place tests in __tests__/" not in prompt
    assert "@/lib/store" not in prompt


async def test_a_sample_application_keeps_its_harness_and_is_shown_no_product():
    """The monolithic prompt a sample application had: the scaffold's harness, its stack's
    supplement, no repository view (rendered byte for byte as template v5 did, the PR's evidence)."""
    prompt = await _monolithic_prompt(
        {"build_profile": "fullstack_fastapi_react"}, None, {"backend/main.py": "app = 1\n"}
    )

    assert _HARNESS_HEADING in prompt
    assert DEVELOPMENT_PROFILES["fullstack_fastapi_react"].test_prompt_supplement in prompt
    assert _PRODUCT_HEADING not in prompt
    # the harness sits between the files and the supplement, where v5 had it
    assert (
        prompt.index("### backend/main.py")
        < prompt.index(_HARNESS_HEADING)
        < prompt.index("You are generating")
    )


async def test_a_product_with_no_runner_is_shown_its_map_and_no_runner_block():
    """Edge: a product whose profile names no runner (``product_neutral``, H.26). The view still
    shows the product, and says nothing of where a runner finds a test, since none does."""
    no_runner = dataclasses.replace(_PLAIN, runners=())
    prepared = await _prepared(no_runner, "implement", **_PLANLESS)
    config = prepared.cycle.resolved_config()
    assert effective_development_profile(config) == "product_neutral"
    view = {**_TALLY_VIEW, "checks": [], "runners": []}

    prompt = await _monolithic_prompt(config, view, {"tally/ledger.py": "def settle(): ...\n"})

    assert _PRODUCT_HEADING in prompt
    assert view["map"] in prompt
    assert "a file named" not in prompt
    assert _HARNESS_HEADING not in prompt
