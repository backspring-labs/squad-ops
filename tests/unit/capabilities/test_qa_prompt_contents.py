"""What a ``qa.test`` prompt shows of ``artifact_contents``, rendered and counted by one function
(#2805).

The handler renders the files through ``qa_prompt_contents`` and the composer counts them through
it (``prompt_budget.rendered_input_tokens``), where the task type's contract names the rendering.

What bugs would these catch?
- **The extraction changing the prompt:** the handler's rendering on both paths, pinned on inputs
  captured from the handler before #2805 moved its scoping, so a refactor that reorders, drops or
  re-fences a file is seen.
- **The composer counting a part where the handler shows the whole,** or the reverse: the focused
  prompt's fallbacks (no expected artifact, no package matching one) show every file and must be
  counted whole, and a task type that renders ``artifact_contents`` whole keeps today's count.
- **A rendering declared with no function to count it,** read as the whole tree or as nothing.
"""

from __future__ import annotations

import dataclasses
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from squadops.capabilities import prompt_budget
from squadops.capabilities.context_assembly import (
    CONTEXT_CONTRACTS,
    REPAIR_CONTEXT_CONTRACT,
)
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.prompt_budget import rendered_input_tokens
from squadops.capabilities.qa_prompt_contents import (
    CODE_UNDER_TEST_MAX_CHARS,
    code_under_test,
    qa_test_prompt_contents,
)
from squadops.memory.lessons import _tokens
from squadops.stacks.development_profiles import get_development_profile

pytestmark = [pytest.mark.domain_capabilities]

_TREE = {
    "orbit/app.py": "def start():\n    return 'orbit'\n",
    "orbit/store.py": "ROWS = []\n",
    "console/src/Panel.jsx": "export const Panel = () => null;\n",
    "console/package.json": '{"name": "console"}\n',
    "tests/conftest.py": "import pytest\n",
    "tests/test_orbit.py": "def test_start():\n    assert True\n",
    "docs/guide.md": "# Guide\n",
    "plans/validation_plan.md": "Check that the orbit starts.\n",
}
_PROFILE = "fullstack_fastapi_react"
_FOCUSED = {"subtask_focus": "the orbit suite"}

#: The focused prompt's section for a suite in ``tests/``, as the handler rendered it before #2805.
_TESTS_PACKAGE_SECTION = (
    "**tests/conftest.py:**\n```python\nimport pytest\n\n```\n"
    "**tests/test_orbit.py:**\n```python\ndef test_start():\n    assert True\n\n```\n"
)
#: The monolithic prompt up to the stack's test supplement, as the handler rendered it before #2805:
#: the validation plan, then the source and support files, never a test or a document.
_MONOLITHIC_HEAD = (
    "## Product Requirements Document\n\nOrbit tracks moons.\n\n\n"
    "## Validation Plan\n\nCheck that the orbit starts.\n\n\n\n"
    "## Source Files to Test\n\n\n"
    "### orbit/app.py\n```python\ndef start():\n    return 'orbit'\n\n```\n\n\n"
    "### orbit/store.py\n```python\nROWS = []\n\n```\n\n\n"
    "### console/src/Panel.jsx\n```javascript\nexport const Panel = () => null;\n\n```\n\n\n"
    '### console/package.json\n```json\n{"name": "console"}\n\n```\n\n\n'
    "### tests/conftest.py\n```python\nimport pytest\n\n```\n\n"
)
#: The tree the suite runs against, on both paths, as the handler selected it before #2805.
_SUITE_TREE = [
    "orbit/app.py",
    "orbit/store.py",
    "console/src/Panel.jsx",
    "console/package.json",
    "tests/conftest.py",
]


def _inputs(**extra) -> dict:
    return {
        "prd": "Orbit tracks moons.",
        "resolved_config": {"build_profile": _PROFILE},
        "artifact_contents": _TREE,
        **extra,
    }


async def _composed(inputs: dict, profile: str = _PROFILE):
    """The handler's step 1a (``_compose_user_prompt``), with no renderer, so the prompt is the
    handler's own text."""
    context = MagicMock()
    context.ports.request_renderer = None
    return await QATestHandler()._compose_user_prompt(
        context, inputs, get_development_profile(profile), profile, inputs["prd"], None, 0.0
    )


def _shown_section(prompt: str) -> str | None:
    if "### Source Artifacts to Test\n" not in prompt:
        return None
    return prompt.split("### Source Artifacts to Test\n", 1)[1].split("\nProduce ONLY", 1)[0]


def _section_names(section: str) -> list[str]:
    return [
        line[2:-3] for line in section.split("\n") if line.startswith("**") and line.endswith(":**")
    ]


@pytest.mark.parametrize(
    ("expected", "shown"),
    [
        (["tests/test_moons.py"], ["tests/conftest.py", "tests/test_orbit.py"]),
        # No expected artifact, or none in a package the tree has: every file (never starve).
        ([], list(_TREE)),
        (["notes/handoff.md"], list(_TREE)),
    ],
    ids=["one-package", "no-expected-artifacts", "no-package-match"],
)
async def test_the_focused_prompt_shows_what_it_showed_and_the_composer_counts_the_same(
    expected, shown
):
    """Characterization, entered at the handler's step 1a. Bug caught: the extraction changing
    which files the prompt shows or how, or the composer's count disagreeing with the prompt on a
    fallback (the whole set shown, a part counted)."""
    inputs = _inputs(**_FOCUSED, expected_artifacts=expected)

    prompt = await _composed(inputs)
    section = _shown_section(prompt.user_prompt)

    assert _section_names(section) == shown
    if expected == ["tests/test_moons.py"]:
        assert section == _TESTS_PACKAGE_SECTION
    assert list(qa_test_prompt_contents(inputs)) == shown
    assert list(prompt.run_tree) == _SUITE_TREE


async def test_an_empty_tree_shows_no_section_and_counts_nothing():
    """Edge: the executor resolved no artifact. Bug caught: a scoping that reads an empty mapping
    as "no match" and falls back to something, or a section heading over nothing."""
    inputs = _inputs(**_FOCUSED, expected_artifacts=["tests/test_moons.py"], artifact_contents={})

    prompt = await _composed(inputs)

    assert _shown_section(prompt.user_prompt) is None
    assert qa_test_prompt_contents(inputs) == {}
    assert list(prompt.run_tree) == []


async def test_the_monolithic_prompt_shows_what_it_showed_and_the_composer_counts_the_same():
    """Characterization of the other path (no ``subtask_focus``), entered at step 1a. Bug caught:
    the source selection's extraction changing what the prompt or the suite's tree holds, or the
    composer counting files the monolithic prompt never shows (a test, a document)."""
    inputs = _inputs()

    prompt = await _composed(inputs)

    assert prompt.user_prompt.startswith(_MONOLITHIC_HEAD)
    assert list(prompt.run_tree) == _SUITE_TREE
    assert sorted(qa_test_prompt_contents(inputs)) == sorted(
        [*_SUITE_TREE, "plans/validation_plan.md"]
    )


#: A repository-backed product's run: the task carries the product's repository (SIP-0112 E.4.3).
_REPOSITORY = {"source_repository": {"commit": "c" * 40, "map": "orbit/app.py", "runners": []}}


@pytest.mark.parametrize(
    "path",
    [{**_FOCUSED, "expected_artifacts": ["tests/test_moons.py"]}, {}],
    ids=["focused", "monolithic"],
)
async def test_a_products_prompt_shows_what_it_showed_and_its_suite_runs_on_its_tree(path):
    """#2815 splits the suite's tree from the prompt's files. Entered at step 1a on a product's
    inputs. Bug caught: the product's tree shown in the prompt, which the composer doesn't count
    (``qa_test_prompt_contents``), so a binding it admitted would overflow; or the suite's tree
    left at the prompt's files, where a product's data and its docs never reach the run."""
    sample, product = _inputs(**path), _inputs(**path, **_REPOSITORY)

    sample_prompt, product_prompt = await _composed(sample), await _composed(product)

    assert product_prompt.user_prompt == sample_prompt.user_prompt
    assert qa_test_prompt_contents(product) == qa_test_prompt_contents(sample)
    assert list(product_prompt.run_tree) == [
        *_SUITE_TREE[:4],
        "tests/conftest.py",
        "docs/guide.md",
        "plans/validation_plan.md",
    ]


def _without_contents(envelope) -> int:
    return rendered_input_tokens(
        SimpleNamespace(
            task_type=envelope.task_type,
            inputs={k: v for k, v in envelope.inputs.items() if k != "artifact_contents"},
        )
    )


@pytest.mark.parametrize(
    ("task_type", "inputs", "counted"),
    [
        (
            "qa.test",
            _inputs(**_FOCUSED, expected_artifacts=["tests/test_moons.py"]),
            ["tests/conftest.py", "tests/test_orbit.py"],
        ),
        ("qa.test", _inputs(**_FOCUSED, expected_artifacts=[]), list(_TREE)),
        ("qa.test", _inputs(**_FOCUSED, expected_artifacts=["notes/handoff.md"]), list(_TREE)),
        (
            "qa.test",
            _inputs(**_FOCUSED, expected_artifacts=["tests/a.py"], artifact_contents={}),
            [],
        ),
        ("qa.test", _inputs(), [*_SUITE_TREE, "plans/validation_plan.md"]),
        # The develop handler renders its artifact_contents whole: today's count, unchanged.
        (
            "development.develop",
            _inputs(**_FOCUSED, expected_artifacts=["tests/test_moons.py"]),
            list(_TREE),
        ),
    ],
    ids=[
        "qa-one-package",
        "qa-no-expected",
        "qa-no-match",
        "qa-empty",
        "qa-monolithic",
        "develop-whole",
    ],
)
def test_the_composer_counts_artifact_contents_as_the_handler_shows_it(task_type, inputs, counted):
    """Entered at ``rendered_input_tokens``, the count ``prompt_budget`` takes. Bug caught: the whole
    tree counted where ``qa.test`` shows a package (#2805), or a part counted where a handler shows
    it whole, which admits a binding its guard then refuses."""
    envelope = SimpleNamespace(task_type=task_type, inputs=inputs)
    shown = {name: _TREE[name] for name in counted} if inputs["artifact_contents"] else {}

    assert rendered_input_tokens(envelope) == _without_contents(envelope) + _tokens(
        json.dumps(shown, sort_keys=True)
    )


def test_a_repair_never_counts_artifact_contents():
    """A ``qa.test`` repair never shows its curated context (``REPAIR_CONTEXT_CONTRACT``): unchanged
    by #2805, and by #2810, whose repair rendering covers its tree, never ``artifact_contents``.
    Bug caught: the qa rendering reaching the repair through its task type's name."""
    envelope = SimpleNamespace(
        task_type="qa.test_repair", inputs=_inputs(**_FOCUSED, expected_artifacts=["tests/a.py"])
    )

    assert rendered_input_tokens(envelope) == _without_contents(envelope)


def test_every_declared_rendering_is_counted_through_its_function(monkeypatch):
    """Bug caught: a contract naming a rendering the composer has no function for, read silently as
    the whole tree (the over-count #2805 removed) or as nothing (an under-count the guard refuses).
    It fails instead, and every rendering declared today has its function. A rendering covering an
    input its contract declares unrendered is a contradiction, and none does (#2810)."""
    contracts = [*CONTEXT_CONTRACTS.values(), REPAIR_CONTEXT_CONTRACT]
    declared = {c.scoped_rendering for c in contracts} - {""}

    assert declared == set(prompt_budget._RENDERINGS)
    for contract in contracts:
        if contract.scoped_rendering:
            covered = prompt_budget._RENDERINGS[contract.scoped_rendering].of
            assert covered.isdisjoint(contract.unrendered_inputs), contract.scoped_rendering
    monkeypatch.setitem(
        CONTEXT_CONTRACTS,
        "qa.test",
        dataclasses.replace(CONTEXT_CONTRACTS["qa.test"], scoped_rendering="unknown"),
    )
    with pytest.raises(KeyError, match="unknown"):
        rendered_input_tokens(SimpleNamespace(task_type="qa.test", inputs=_inputs()))


async def test_the_monolithic_plan_is_the_first_of_its_name_shown_and_counted_alike():
    """#2809 item 3. Two files carry the plan's name. The handler showed the first and the budget
    counted both, through two copies of the rule. Bug caught: the count and the prompt choosing
    different plans, or the budget over-counting a plan the prompt never shows."""
    contents = {**_TREE, "plans/validation_plan_old.md": "An older plan, never shown.\n"}
    inputs = _inputs(artifact_contents=contents)

    prompt = await _composed(inputs)

    assert "Check that the orbit starts." in prompt.user_prompt
    assert "An older plan, never shown." not in prompt.user_prompt
    counted = qa_test_prompt_contents(inputs)
    assert "plans/validation_plan_old.md" not in counted
    assert counted["plans/validation_plan.md"] == "Check that the orbit starts.\n"


async def test_a_plan_that_is_also_a_source_is_counted_as_often_as_it_is_shown():
    """#2809 item 1. A source file whose name carries the plan's is shown twice, as the plan and
    among the sources. Bug caught: the dict merge counting it once, so the budget is short by
    the file."""
    plan_source = "orbit/validation_plan.py"
    text = "STEPS = ['the orbit starts']\n"
    contents = {plan_source: text, **{k: v for k, v in _TREE.items() if "validation" not in k}}
    inputs = _inputs(artifact_contents=contents)

    prompt = await _composed(inputs)
    counted = qa_test_prompt_contents(inputs)

    assert prompt.user_prompt.count(text.strip()) == 2
    assert [content for content in counted.values() if content == text] == [text, text]


_SPLIT_TREE = {
    "test/play.test.js": 'import { play } from "../tools/play.mjs";\n',
    "test/fixtures/hello.json": "{}\n",
    "tools/play.mjs": "export const play = () => ({ shots: 3 });\n",
    "tools/viewer.mjs": "export const view = 1;\n",
    "src/engine.js": "export const run = 1;\n",
}
_SPLIT_SUITE = {
    "subtask_focus": "shot count",
    "expected_artifacts": ["test/criterion_T1.test.js"],
    "artifact_contents": _SPLIT_TREE,
    "resolved_config": {"build_profile": "node_vitest"},
}


async def test_a_focused_suite_is_shown_the_code_its_package_imports_from_outside_it():
    """Entered at ``_compose_user_prompt``, the handler's own step. Bug caught: scoping to the
    suite's package hides the helper the suite calls, so qa guesses its field names and a test of
    a real count reads 0 (``cyc_8e691eb2bccf``)."""
    prompt = (await _composed({**_SPLIT_SUITE, "prd": "A tank game."})).user_prompt

    names = _section_names(_shown_section(prompt))
    assert "tools/play.mjs" in names
    assert "{ shots: 3 }" in prompt
    assert "tools/viewer.mjs" not in names  # nothing imports it: pf-33's scoping still holds
    assert "src/engine.js" not in names


@pytest.mark.parametrize(
    ("extra", "shown"),
    [
        ({"subtask_description": "Test src/engine.js as it stands."}, "src/engine.js"),
        ({"acceptance_criteria": ["tools/viewer.mjs draws a match"]}, "tools/viewer.mjs"),
        (
            {
                "retake_current_files": {
                    "test/criterion_T1.test.js": 'import { view } from "../tools/viewer.mjs";\n'
                }
            },
            "tools/viewer.mjs",
        ),
    ],
)
def test_the_task_naming_a_file_or_its_retaken_suite_importing_one_shows_it(extra, shown):
    """Bug caught: a first test beside no other, or a re-take whose own suite is the only one
    importing the module, left blind to it."""
    assert shown in qa_test_prompt_contents({**_SPLIT_SUITE, **extra})


def test_a_file_too_large_to_show_is_named_with_its_size_and_never_cut():
    """Bug caught: a vendored engine a suite imports costing the prompt its whole text, or dropped
    with no word, so qa reads a helper as absent."""
    big = "x" * (CODE_UNDER_TEST_MAX_CHARS + 1)
    inputs = {**_SPLIT_SUITE, "artifact_contents": {**_SPLIT_TREE, "tools/play.mjs": big}}

    assert qa_test_prompt_contents(inputs)["tools/play.mjs"] == (
        f"(not shown: {len(big)} characters, too large for this prompt)"
    )


def test_an_import_of_nothing_in_the_tree_and_a_file_with_no_imports_add_nothing():
    """Edge: an installed package, a broken relative import, a fixture that reads like one."""
    assert (
        code_under_test(
            {
                "test/a.test.js": 'import x from "vitest";\nimport y from "./gone.js";\n',
                "test/notes.md": 'import z from "../tools/play.mjs"\n',
            },
            _SPLIT_TREE,
        )
        == {}
    )


def test_the_composer_counts_the_imported_code_the_handler_shows():
    """Entered at ``rendered_input_tokens``. Bug caught: the prompt showing a helper the budget
    never counted, so a binding is admitted that the window can't hold."""
    without = {k: v for k, v in _SPLIT_TREE.items() if k != "tools/play.mjs"}
    bare = {**_SPLIT_SUITE, "artifact_contents": without}

    counted = rendered_input_tokens(SimpleNamespace(task_type="qa.test", inputs=_SPLIT_SUITE))
    fewer = rendered_input_tokens(SimpleNamespace(task_type="qa.test", inputs=bare))

    assert counted > fewer


#: A Luau product's first spec, as the #3041 capture's ``qa.test`` task was handed it: the plan
#: names the module by its instance path, and no suite beside the new spec requires it.
_LUAU_TREE = {
    "run_report.md": "# Run\n",
    "src/Shared/Modules/SalePricing.luau": "return { computeSaleTotal = function() end }\n",
    "src/Shared/Modules/LivesRules.luau": "return { New = function() end }\n",
    "src/Shared/Modules/Sale.luau": "return {}\n",
    "src/Shared/Util/init.luau": "return { clamp = math.clamp }\n",
    "tests/LivesRules.spec.luau": "local Rules = require(Shared.Modules.LivesRules)\n",
    "tests/run.luau": "-- the product's runner\n",
}
_LUAU_SUITE = {
    "prd": "",
    "subtask_focus": "criterion T1 spec suite",
    "subtask_description": (
        "Author tests/criterion_T1.spec.luau, a Lune spec that requires\n"
        "Shared.Modules.SalePricing and asserts the three T1 observables."
    ),
    "expected_artifacts": ["tests/criterion_T1.spec.luau"],
    "implementation_artifacts": ["src/Shared/Modules/SalePricing.luau"],
    "acceptance_criteria": ["M1: The spec begins with require(Shared.Modules.SalePricing)."],
    "artifact_contents": _LUAU_TREE,
    "resolved_config": {"development_profile": "product_neutral"},
}


async def test_a_luau_products_first_spec_is_shown_the_module_it_tests_in_luau_fences():
    """Entered at ``_compose_user_prompt``, the handler's own step, on the #3041 capture's shape.
    Bugs caught: the module under test shown nowhere, so the spec is written from the criterion's
    words alone (#3139); and the product's Luau fenced, and its spec asked for, as Python
    (#3136)."""
    prompt = (await _composed(_LUAU_SUITE, "product_neutral")).user_prompt

    section = _shown_section(prompt)
    assert _section_names(section) == [
        "tests/LivesRules.spec.luau",
        "tests/run.luau",
        "src/Shared/Modules/SalePricing.luau",
    ]
    assert (
        "**src/Shared/Modules/SalePricing.luau:**\n```luau\n"
        "return { computeSaleTotal = function() end }\n\n```\n"
    ) in section
    assert "```python" not in prompt
    assert "```luau:tests/criterion_T1.spec.luau```" in prompt


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        ("require(Shared.Modules.SalePricing)", ["src/Shared/Modules/SalePricing.luau"]),
        (
            "game.ReplicatedStorage.Shared.Modules.SalePricing.computeSaleTotal(lines)",
            ["src/Shared/Modules/SalePricing.luau"],
        ),
        # As the product's own comments write an instance path.
        ("Lives in Shared > Modules > SalePricing.", ["src/Shared/Modules/SalePricing.luau"]),
        ("the module src.Shared.Modules.LivesRules", ["src/Shared/Modules/LivesRules.luau"]),
        # A package's init file is its folder's module.
        ("require(Shared.Util).clamp", ["src/Shared/Util/init.luau"]),
        # Each names nothing: a tail below the source root, one word, a longer name, a shorter
        # name inside this one, and a name the tree doesn't hold.
        ("Modules.SalePricing and Modules.LivesRules", []),
        ("SalePricing computes the total", []),
        ("require(Shared.Modules.SalePricingV2)", []),
        ("require(Shared.Modules.Sal)", []),
        ("require(Shared.Modules.Pricing)", []),
        ("", []),
    ],
    ids=[
        "require",
        "full-instance-path",
        "arrow-separated",
        "from-the-root",
        "package-init",
        "tail-below-the-root",
        "bare-word",
        "longer-name",
        "shorter-name-inside",
        "absent",
        "no-text",
    ],
)
def test_a_task_names_code_under_test_by_its_dotted_module_path(text, shown):
    """Bug caught (#3139): a module the task names as the product's code does left out, or a
    loose match pulling in a file the task never named, which costs pf-33's scoping."""
    assert list(code_under_test({}, _LUAU_TREE, text)) == shown


def test_a_longer_modules_name_does_not_show_the_shorter_one_inside_it():
    """``Sale.luau`` sits beside ``SalePricing.luau``. Bug caught: a name matched as a prefix, so
    a task about SalePricing is shown Sale too."""
    assert list(code_under_test({}, _LUAU_TREE, "require(Shared.Modules.SalePricing)")) == [
        "src/Shared/Modules/SalePricing.luau"
    ]
    assert list(code_under_test({}, _LUAU_TREE, "require(Shared.Modules.Sale)")) == [
        "src/Shared/Modules/Sale.luau"
    ]


def test_a_python_module_is_named_by_its_import_path():
    """The same rule on another stack: a plan writes ``app.services.pricing``."""
    tree = {"backend/app/services/pricing.py": "def total(): ...\n", "backend/app/main.py": ""}

    assert list(code_under_test({}, tree, "Test app.services.pricing.total for a bulk sale.")) == [
        "backend/app/services/pricing.py"
    ]


def test_the_composer_counts_the_module_a_task_names_by_its_module_path():
    """Entered at ``rendered_input_tokens``. Bug caught: the prompt showing the module while the
    budget counts the suite's package alone."""
    unnamed = {**_LUAU_SUITE, "subtask_description": "Author the spec.", "acceptance_criteria": []}

    named = rendered_input_tokens(SimpleNamespace(task_type="qa.test", inputs=_LUAU_SUITE))
    fewer = rendered_input_tokens(SimpleNamespace(task_type="qa.test", inputs=unnamed))

    assert list(qa_test_prompt_contents(unnamed)) == [
        "tests/LivesRules.spec.luau",
        "tests/run.luau",
    ]
    assert named > fewer


#: The second #3041 capture's shape (#3146): the plan names the module by its bare name alone.
_BARE_TREE = {
    "src/Shared/Modules/ShopDiscount.luau": "return { calcBulkDiscount = function() end }\n",
    "src/Shared/Modules/ShopRules.luau": "return {}\n",
    "src/Server/Services/Shop.luau": "return {}\n",
    "src/Shared/Util/init.luau": "return {}\n",
    "tests/LivesRules.spec.luau": "-- the product's own\n",
    "tests/run.luau": "-- the product's runner\n",
}
_BARE_SUITE = {
    "prd": "",
    "subtask_focus": "criterion T1 spec suite",
    "subtask_description": (
        "Author tests/criterion_T1.spec.luau proving criterion T1: the ShopDiscount\n"
        "module's calcBulkDiscount function, as the Shop shows it."
    ),
    "expected_artifacts": ["tests/criterion_T1.spec.luau"],
    "implementation_artifacts": [
        "src/Shared/Modules/ShopDiscount.luau",
        "src/Shared/Modules/ShopRules.luau",
    ],
    "acceptance_criteria": ["The spec does NOT require the ShopDiscount module at file top."],
    "artifact_contents": _BARE_TREE,
    "resolved_config": {"development_profile": "product_neutral"},
}


async def test_a_plan_source_the_task_names_by_its_bare_name_is_shown():
    """Entered at ``_compose_user_prompt`` on the capture's shape. Bugs caught: the module under
    test left out when the plan says "the ShopDiscount module" and nothing longer (#3146); the
    plan's other sources shown with it, which undoes the package scoping; and a file outside the
    plan's sources shown for a word the text happens to hold ("Shop")."""
    prompt = (await _composed(_BARE_SUITE, "product_neutral")).user_prompt

    assert _section_names(_shown_section(prompt)) == [
        "tests/LivesRules.spec.luau",
        "tests/run.luau",
        "src/Shared/Modules/ShopDiscount.luau",
    ]
    assert "calcBulkDiscount = function() end" in prompt


@pytest.mark.parametrize(
    ("text", "sources", "shown"),
    [
        ("the ShopDiscount module", ["src/Shared/Modules/ShopDiscount.luau"], True),
        # A longer word, another word, and no text name nothing.
        ("the ShopDiscounts table", ["src/Shared/Modules/ShopDiscount.luau"], False),
        ("the discount module", ["src/Shared/Modules/ShopDiscount.luau"], False),
        ("", ["src/Shared/Modules/ShopDiscount.luau"], False),
        # Named, and no source of the plan's: the tree's other files stay scoped out.
        ("the ShopDiscount module", [], False),
        # A plan source the tree doesn't hold yet is not shown, and nothing is raised.
        ("the Pricing module", ["src/Shared/Modules/Pricing.luau"], False),
    ],
    ids=["named", "longer-word", "another-word", "no-text", "not-a-plan-source", "not-in-the-tree"],
)
def test_a_bare_name_counts_only_for_the_plans_own_sources(text, sources, shown):
    found = code_under_test({}, _BARE_TREE, text, plan_sources=sources)

    assert ("src/Shared/Modules/ShopDiscount.luau" in found) is shown
    assert set(found) <= {"src/Shared/Modules/ShopDiscount.luau"}


def test_a_package_named_by_its_folder_is_its_init_file():
    """A plan source that is its folder's module is named by the folder."""
    found = code_under_test(
        {}, _BARE_TREE, "the Util module's clamp", plan_sources=["src/Shared/Util/init.luau"]
    )

    assert list(found) == ["src/Shared/Util/init.luau"]
