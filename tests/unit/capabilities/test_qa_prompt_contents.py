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
from squadops.capabilities.qa_prompt_contents import qa_test_prompt_contents
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
    '### console/package.json\n```python\n{"name": "console"}\n\n```\n\n\n'
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


async def _composed(inputs: dict):
    """The handler's step 1a (``_compose_user_prompt``), with no renderer, so the prompt is the
    handler's own text."""
    context = MagicMock()
    context.ports.request_renderer = None
    return await QATestHandler()._compose_user_prompt(
        context, inputs, get_development_profile(_PROFILE), _PROFILE, inputs["prd"], None, 0.0
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
