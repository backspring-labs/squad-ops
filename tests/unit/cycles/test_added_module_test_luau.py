"""A criterion's test for a module the change adds, on a Luau product (#3143).

The #3041 capture's increment was refused though its build was right: its spec required the new
module at the top of the file, the accepted product has no such module, the runner reported the
file ``[setup]``, and §24ci (a) read ``only_setup_failures``. The plan had asked for that shape.

Two things are held here: that the idiom the Roblox QA skill shows does discriminate, read from
the product's own runner's lines (run under Lune on z_tower-ascension at ``0beaac0``), and that
every author of such a spec or of its plan is told, through one asset.
"""

from __future__ import annotations

import pytest

from squadops.sandbox.findings import LUAU, read

pytestmark = [pytest.mark.domain_capabilities]

_HEADING = "### A criterion's test for a module this change adds"
_LUAU_REPOSITORY = {
    "commit": "0beaac09c60662b41779f9b262dd3e6f18db1cdd",
    "map": "- `src/` (137 files)",
    "runners": [
        {
            "runner": "luau",
            "checks": ["luau_tests"],
            "roots": ["tests"],
            "file_pattern": "*.spec.luau",
        }
    ],
}
_PYTEST_REPOSITORY = {
    **_LUAU_REPOSITORY,
    "runners": [{"runner": "pytest", "roots": ["tests"], "file_pattern": "test_*.py"}],
}
_SCOPE = {
    "criteria": [
        {"id": "T1", "statement": "a streak pays a bonus", "observable": "Bonus(3) == 30"}
    ],
    "frozen": [],
    "route_criteria": [],
    "page_criteria": [],
    "stack": "",
}

# The runner's own lines for the skill's example spec, module absent and present, and for a spec
# that requires the module at the top of its file, module absent.
_IDIOM_BEFORE = (
    "FAIL tests/Streak.spec.luau > a streak of three kills pays a bonus of thirty [assertion] "
    "Shared.Modules.StreakRules exists: got nil\n"
    "Tests: 0 passed, 1 failed, 0 errored, 0 setup, 1 total\n"
)
_FILE_LEVEL_BEFORE = (
    "FAIL tests/Streak.spec.luau [setup] StreakRules is not a valid member of Folder "
    '"ReplicatedStorage.Shared.Modules"\n'
    "Tests: 0 passed, 0 failed, 0 errored, 1 setup, 1 total\n"
)
_AFTER = (
    "PASS tests/Streak.spec.luau > a streak of three kills pays a bonus of thirty\n"
    "Tests: 1 passed, 0 failed, 0 errored, 0 setup, 1 total\n"
)


def _renderer():
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.prompts.renderer import RequestTemplateRenderer

    return RequestTemplateRenderer(create_prompt_asset_source("filesystem"))


@pytest.mark.parametrize(
    ("before", "reason", "tests"),
    [
        (
            _IDIOM_BEFORE,
            "discriminates",
            ("tests/Streak.spec.luau > a streak of three kills pays a bonus of thirty",),
        ),
        (_FILE_LEVEL_BEFORE, "only_setup_failures", ()),
    ],
    ids=["looked-up-inside-the-test", "required-at-the-top-of-the-file"],
)
def test_a_spec_for_an_added_module_discriminates_only_when_its_absence_is_an_assertion(
    before, reason, tests
):
    """Entered at ``discrimination_on_runner`` with the framework's own reading of each run. Bug
    caught: the skill teaching an idiom the reader doesn't credit, found only when a counted
    increment is refused."""
    from squadops.campaigns.acceptance import discrimination_on_runner

    found = discrimination_on_runner(
        "T1", LUAU, read(LUAU, before, "", 1), read(LUAU, _AFTER, "", 0)
    )

    assert (str(found.reason), found.discriminating) == (reason, tests)


def test_the_skills_own_example_is_the_spec_those_lines_came_from():
    """The lines above are evidence only for the example the skill shows. Bug caught: the skill's
    example edited away from what was run."""
    from squadops.capabilities.skillsets import load_skillsets

    files = load_skillsets()["roblox-studio-qa"].skill_files["luau-test-loader"]
    body = next(text for name, text in dict(files).items() if name.endswith("SKILL.md"))

    section = body.split("## A module the change adds", 1)[1].split("\n## ", 1)[0]
    assert 'local found = Shared.Modules:FindFirstChild("StreakRules")' in section
    assert 'check.truthy(found, "Shared.Modules.StreakRules exists")' in section
    assert 'test("a streak of three kills pays a bonus of thirty", function()' in section
    assert "return require(found)" in section


async def _framing(repository) -> str:
    from squadops.capabilities.handlers.planning.framing import DevelopmentDesignPlanHandler

    return await DevelopmentDesignPlanHandler()._increment_section(
        _renderer(),
        {"increment_change_request": "criteria: []\n", "source_repository": repository},
    )


async def _brief(repository) -> str:
    from squadops.capabilities.handlers.planning.brief import (
        GovernancePreparePlanAuthoringBriefHandler,
    )

    return await GovernancePreparePlanAuthoringBriefHandler()._increment_section(
        _renderer(),
        {"increment_change_request": "criteria: []\n", "source_repository": repository},
    )


async def _qa_proposer(repository) -> str:
    from squadops.capabilities.handlers.planning_tasks import QaProposePlanTasksHandler

    return await QaProposePlanTasksHandler()._increment_sections(
        _renderer(),
        {
            "increment_criterion_files_index": "- T1: `tests/criterion_T1.spec.luau`",
            "source_repository": repository,
        },
    )


async def _development_proposer(repository) -> str:
    from squadops.capabilities.handlers.planning_tasks import DevelopmentProposePlanTasksHandler

    return await DevelopmentProposePlanTasksHandler()._increment_sections(
        _renderer(),
        {
            "increment_criterion_files_index": "- T1: `tests/criterion_T1.spec.luau`",
            "source_repository": repository,
        },
    )


async def _sole_author(repository) -> str:
    from squadops.capabilities.handlers._plan_authoring import contract_surface_sections

    return await contract_surface_sections(
        _renderer(),
        {
            "increment_criterion_files_index": "- T1: `tests/criterion_T1.spec.luau`",
            "source_repository": repository,
        },
    )


async def _suite_author(repository, scope=_SCOPE) -> str:
    from squadops.capabilities.handlers.increment_test_scope import increment_test_scope_section

    return await increment_test_scope_section(
        _renderer(), {"increment_test_scope": scope, "source_repository": repository}
    )


@pytest.mark.parametrize(
    "seam",
    [_framing, _brief, _qa_proposer, _sole_author, _suite_author],
    ids=["the-design-stage", "the-brief", "the-qa-proposer", "the-plans-sole-author", "the-suite"],
)
async def test_every_author_of_the_spec_or_its_plan_is_told_on_a_luau_product_only(seam):
    """Each entered at the handler's own section, with the real assets. Bug caught: the suite's
    author told while the plan still asks for the old shape (the capture's qa criterion M1 came
    from the design stage's draft), or the rule shown on a product it says nothing true about."""
    told = await seam(_LUAU_REPOSITORY)
    elsewhere = await seam(_PYTEST_REPOSITORY)

    assert told.count(_HEADING) == 1
    assert "`FindFirstChild`" in told
    assert _HEADING not in elsewhere
    assert elsewhere  # the seam's other sections still render


async def test_the_development_proposer_and_an_increment_no_test_proves_are_not_told():
    """The criterion files are qa's (#2795), and a change proven only by a scenario has no spec.
    Bug caught: the rule shown to an author with no spec to write, which costs its prompt."""
    scenario_only = {
        **_SCOPE,
        "criteria": [],
        "scenario_criteria": [{"id": "S1", "statement": "x"}],
    }

    assert _HEADING not in await _development_proposer(_LUAU_REPOSITORY)
    assert _HEADING not in await _suite_author(_LUAU_REPOSITORY, scenario_only)


async def test_no_renderer_and_no_repository_render_nothing():
    """Edge: a sample application's run carries no repository, and a handler with no renderer
    renders none of its sections."""
    from squadops.capabilities.handlers.source_repository import added_module_test_section

    assert await added_module_test_section(None, {"source_repository": _LUAU_REPOSITORY}) == ""
    assert await added_module_test_section(_renderer(), {}) == ""
