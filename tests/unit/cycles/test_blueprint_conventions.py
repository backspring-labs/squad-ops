"""SIP-0112 H.13: a product made from a blueprint runs under that blueprint's development profile,
and is shown its conventions without the blueprint's test placement.

Entered at ``prepare_cycle`` (the create route's and the Campaign launcher's one path), then at the
task that renders the prompt: the developer's and the test author's handlers, given the cycle's
own ``resolved_config()`` (what ``generate_task_plan`` hands every task) and a repository view in
the shape the dispatch builds, rendered with the shipped assets. The products are invented: one
shaped like ``z_shelfnote`` (pytest at the root, vitest under ``frontend``), one with no blueprint.

Bugs caught:
- a product made from ``fullstack_fastapi_react`` still running under ``python_cli``: a Python
  package's prompts, a 4,000-token ceiling and a ``.py``-only source filter on a React change;
- the blueprint's profile pinned whole, so the model reads "Place tests in backend/tests/" or "All
  backend files go under backend/" beside runners that find the product's tests elsewhere;
- a product with no blueprint, or a sample application, shown anything other than what it was;
- the pin seeding a skeleton, overriding an operator's choice, or reaching a plan-less cycle, whose
  test author is never shown the product's runners.
"""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.factory import DEFAULT_TEMPLATES_PATH, create_prompt_asset_source
from squadops.api.routes.cycles.cycles import prepare_cycle
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.source_repository import (
    product_conventions_template,
    source_repository_section,
)
from squadops.cycles.models import DerivedProfileNotFoundError
from squadops.cycles.preflight import seeds_skeleton
from squadops.llm.models import ChatMessage
from squadops.projects.derived_profile import parse_profile
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.stacks.development_profiles import (
    DEVELOPMENT_PROFILES,
    blueprint_development_profile,
    effective_development_profile,
)
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.cycles.test_source_backed_recipe import _ports, _project, _request

#: The no-blueprint product's profile: the shared fixture's, which names none.
_PLAIN = parse_profile(recorded("derived_profile", "valid"))


@pytest.fixture(autouse=True)
def _no_sandbox(monkeypatch):
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


def _made_from(stack: str | None):
    return dataclasses.replace(_PLAIN, blueprint_stack=stack)


async def _prepared(derived, profile="campaign-increment-source", *, source=True, **values):
    ports = _ports(_project(source=source))
    if isinstance(derived, Exception):
        ports.project_registry.get_derived_profile.side_effect = derived
    else:
        ports.project_registry.get_derived_profile.return_value = derived
    return await prepare_cycle_with(ports, profile, **values)


async def prepare_cycle_with(ports, profile, **values):
    return await prepare_cycle(ports, "prj-tally", _request(profile, **values))


# --- the pin, at prepare_cycle ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("derived", "values", "pinned", "runs_under"),
    [
        (_made_from("fullstack_fastapi_react"), {}, "fullstack_fastapi_react",
         "fullstack_fastapi_react"),
        (_made_from("nextjs_ts"), {}, "nextjs_ts", "nextjs_ts"),
        # z_continuum's shape: imported, no blueprint. The default stands, as in 2.4.
        (_PLAIN, {}, None, "python_cli"),
        # a baseline captured before profiles: nothing to read a blueprint from
        (DerivedProfileNotFoundError("prj-tally"), {}, None, "python_cli"),
        # the operator's choice stands, as a supplied contract_ref does
        (_made_from("fullstack_fastapi_react"), {"development_profile": "python_api"}, None,
         "python_api"),
    ],
    ids=["fullstack", "nextjs", "no-blueprint", "no-profile", "operator-named"],
)  # fmt: skip
async def test_a_products_cycle_runs_under_its_blueprints_profile_and_seeds_nothing(
    derived, values, pinned, runs_under
):
    prepared = await _prepared(derived, **values)

    cycle = prepared.cycle
    assert cycle.execution_overrides.get("development_profile") == (
        pinned or values.get("development_profile")
    )
    assert effective_development_profile(cycle.resolved_config()) == runs_under
    # E.4.3's guard ran on the pinned config and passed it: a development profile seeds nothing
    assert not seeds_skeleton(cycle.resolved_config())
    assert cycle.source_context is not None


async def test_a_plan_less_cycle_and_a_sample_application_are_never_pinned():
    """A plan-less task isn't shown the product's runners (the monolithic qa prompt has no
    repository view), so the profile's skeleton prose would place its tests. A sample application
    has no pin to read a blueprint from: the registry isn't asked."""
    blueprint = _made_from("fullstack_fastapi_react")

    planless = await _prepared(
        blueprint, "implement", implementation_plan=False, typed_acceptance=False
    )
    ports = _ports(_project(source=False))
    ports.project_registry.get_derived_profile.return_value = blueprint
    sample = await prepare_cycle_with(ports, "implement")

    assert "development_profile" not in planless.cycle.execution_overrides
    assert "development_profile" not in sample.cycle.execution_overrides
    ports.project_registry.get_derived_profile.assert_not_awaited()


@pytest.mark.parametrize(
    ("blueprint", "profile"),
    [
        ("fullstack_fastapi_react", "fullstack_fastapi_react"),
        ("nextjs_ts", "nextjs_ts"),
        (None, ""),
        ("", ""),
        # a development profile, not a blueprint: no scaffold stack binds it
        ("python_cli", ""),
        ("vue_rails", ""),
    ],
)
def test_only_a_blueprint_whose_profile_speaks_to_a_product_is_pinned(blueprint, profile):
    assert blueprint_development_profile(blueprint) == profile


def test_a_blueprint_profile_with_nothing_for_a_product_is_not_pinned(monkeypatch):
    """Bug caught: a blueprint added without its product conventions, pinned anyway, so its
    skeleton prose reaches the product's tasks."""
    bare = dataclasses.replace(DEVELOPMENT_PROFILES["nextjs_ts"], product_conventions_template="")
    monkeypatch.setitem(DEVELOPMENT_PROFILES, "nextjs_ts", bare)

    assert blueprint_development_profile("nextjs_ts") == ""


# --- what reaches the model --------------------------------------------------------------------

_SHELFNOTE_VIEW = {
    "commit": "c" * 40,
    "map": "- `backend/main.py`\n- `frontend/src/views/BookList.jsx`\n- `tests/test_books.py`",
    "checks": [
        {"id": "backend_tests", "argv": ["python", "-m", "pytest", "-q"]},
        {"id": "frontend_tests", "argv": ["npm", "--prefix", "frontend", "test"]},
    ],
    "runners": [
        {"runner": "pytest", "checks": ["backend_tests"], "roots": ["."],
         "file_pattern": "test_*.py", "covers": ["backend/**"]},
        {"runner": "vitest", "checks": ["frontend_tests"], "roots": ["frontend"],
         "file_pattern": "*.test.*", "covers": ["frontend/**"]},
    ],
    "instructions": {},
    "existing_files": {},
}  # fmt: skip

#: Every way the blueprint's skeleton prose places a file or a test.
_SKELETON_PLACEMENT = (
    "backend/tests",
    "frontend/src/__tests__",
    "All backend files go under backend/",
    "__tests__/",
)
_CONVENTIONS_HEADING = "### The blueprint it was made from"
_RUNNER_LINES = (
    "a file named `test_*.py` under `.`, testing `backend/**`",
    "a file named `*.test.*` under `frontend`, testing `frontend/**`",
)


def _renderer() -> RequestTemplateRenderer:
    return RequestTemplateRenderer(
        asset_source=create_prompt_asset_source(
            provider="filesystem", templates_path=DEFAULT_TEMPLATES_PATH
        )
    )


def _context(reply: str) -> MagicMock:
    ctx = MagicMock()
    ctx.role_id = "dev"
    answer = ChatMessage(role="assistant", content=reply)
    ctx.ports.llm.chat = AsyncMock(return_value=answer)
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(return_value=answer)
    ctx.ports.llm.default_model = "m"
    ctx.ports.llm_observability = None
    ctx.correlation_context = None
    assembled = MagicMock(content="System prompt", assembly_hash="sha256:x")
    ctx.ports.prompt_service.get_system_prompt = MagicMock(return_value=assembled)
    ctx.ports.prompt_service.assemble = MagicMock(return_value=assembled)
    ctx.ports.request_renderer = _renderer()
    return ctx


def _first_call(ctx: MagicMock) -> tuple[list, dict]:
    llm = ctx.ports.llm
    call = (llm.chat_stream_with_usage.await_args_list or llm.chat.await_args_list)[0]
    return call.args[0], call.kwargs


def _inputs(resolved_config: dict, expected: str, *, view: dict | None = _SHELFNOTE_VIEW) -> dict:
    inputs = {
        "prd": "Readers can mark a book as read.",
        "resolved_config": {**resolved_config, "output_validation": False},
        "subtask_focus": "Mark a book read",
        "subtask_description": "Add the read toggle.",
        "expected_artifacts": [expected],
        "artifact_contents": {},
    }
    if view is not None:
        inputs["source_repository"] = view
    return inputs


@pytest.mark.parametrize(
    ("derived", "conventions", "supplement", "ceiling"),
    [
        (_made_from("fullstack_fastapi_react"), True, None, 12000),
        # no blueprint: python_cli, its supplement and ceiling, exactly as in 2.4
        (_PLAIN, False, "python_cli", 4000),
    ],
    ids=["shelfnote-shaped", "no-blueprint"],
)
async def test_the_developer_of_a_product_is_shown_its_blueprints_conventions_never_its_layout(
    derived, conventions, supplement, ceiling
):
    prepared = await _prepared(derived)
    ctx = _context("```javascript:frontend/src/views/BookList.jsx\nexport default 1\n```\n")

    await DevelopmentDevelopHandler().handle(
        ctx, _inputs(prepared.cycle.resolved_config(), "frontend/src/views/BookList.jsx")
    )

    messages, kwargs = _first_call(ctx)
    system, user = messages[0].content, messages[1].content
    assert system == (
        "System prompt"
        if supplement is None
        else "System prompt\n\n" + DEVELOPMENT_PROFILES[supplement].system_prompt_supplement
    )
    assert (_CONVENTIONS_HEADING in user) is conventions
    assert ("`fullstack_fastapi_react` blueprint" in user) is conventions
    assert all(line in user for line in _RUNNER_LINES)
    if conventions:
        assert [p for p in _SKELETON_PLACEMENT if p in system + user] == []
    assert kwargs["max_tokens"] == ceiling


@pytest.mark.parametrize(
    ("derived", "conventions", "framework"),
    [
        (_made_from("fullstack_fastapi_react"), True, "both"),
        (_PLAIN, False, "pytest"),
    ],
    ids=["shelfnote-shaped", "no-blueprint"],
)
async def test_the_test_author_of_a_product_places_tests_by_its_runners(
    derived, conventions, framework, monkeypatch
):
    """The qa container's own run takes the blueprint's frameworks too: pytest and vitest for
    FastAPI and React, where python_cli ran pytest over a React change."""
    ran: list[str] = []

    async def _no_run(test_framework, *_a, **_k):
        ran.append(test_framework)
        return MagicMock(executed=False, tests_passed=False, exit_code=None, summary="not run")

    monkeypatch.setattr(
        "squadops.capabilities.handlers.cycle.qa_test.run_build_validation", _no_run
    )
    prepared = await _prepared(derived)
    ctx = _context("```javascript:frontend/src/views/BookList.test.jsx\ntest('x', () => {})\n```\n")

    await QATestHandler().handle(
        ctx, _inputs(prepared.cycle.resolved_config(), "frontend/src/views/BookList.test.jsx")
    )

    messages, _ = _first_call(ctx)
    user = messages[1].content
    assert (_CONVENTIONS_HEADING in user) is conventions
    assert all(line in user for line in _RUNNER_LINES)
    assert [p for p in _SKELETON_PLACEMENT if p in messages[0].content + user] == []
    assert ran == [framework]


async def test_a_sample_application_under_the_same_profile_keeps_its_skeleton_prose():
    """Bug caught: the conventions keyed on the profile alone, so a sample application filling the
    fullstack skeleton loses the supplement that describes it."""
    ctx = _context("```python:backend/routes.py\nx = 1\n```\n")

    await DevelopmentDevelopHandler().handle(
        ctx,
        _inputs({"build_profile": "fullstack_fastapi_react"}, "backend/routes.py", view=None),
    )

    messages, _ = _first_call(ctx)
    fullstack = DEVELOPMENT_PROFILES["fullstack_fastapi_react"].system_prompt_supplement
    assert messages[0].content == "System prompt\n\n" + fullstack
    assert _CONVENTIONS_HEADING not in messages[1].content


async def test_the_conventions_sit_between_the_map_and_the_checks_that_place_tests():
    """The order the appendix renders them in: the blueprint's conventions, then the runners,
    which say where a test is found. An unresolvable profile renders the view as before."""
    config = {"development_profile": "fullstack_fastapi_react"}
    shown = await source_repository_section(
        _renderer(), {"resolved_config": config, "source_repository": _SHELFNOTE_VIEW}
    )
    unknown = {"resolved_config": {"development_profile": "cobol"}, "source_repository": {}}

    assert (
        shown.index("`tests/test_books.py`")
        < shown.index(_CONVENTIONS_HEADING)
        < shown.index("### How the product is checked")
        < shown.index(_RUNNER_LINES[0])
    )
    assert product_conventions_template(unknown) == ""
    assert product_conventions_template({"resolved_config": config}) == ""
