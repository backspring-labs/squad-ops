"""The ``qa.test`` system prompt names only the product's runner (#3147; the 2.8.1 plan's item 7).

Entered at ``QATestHandler._generation_request``, the step that assembles the system message a
suite's author is sent, with the real prompt assembler over the shipped fragments.

The task type's fragment states its rules in pytest's and vitest's terms, with FastAPI, Next.js and
JSX examples. A Luau product's author was shown all of it beside the product's own runner. The
change gives a product that tests only with Luau runners a fragment written for its runner, on
one condition: every existing stack's system prompt is byte for byte what it was.
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock

import pytest

from adapters.prompts.factory import create_prompt_repository
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.prompts.assembler import PromptAssembler
from squadops.stacks.development_profiles import get_development_profile
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_capabilities]

#: The task type's own fragment as 2.8.0 shipped it (its file's sha256, front matter included).
#: An edit to it moves every existing stack's ``qa.test`` prompt: make it with a replay that reads
#: those stacks, and move this pin in the same change.
_FRAGMENT_AS_SHIPPED = "4918b9e0f53a4315dffc31f87813dacabe99feb91e68455c68e7fc0311e3e9e8"
#: What the task type's fragment says of other stacks' runners and examples.
_OTHER_STACKS = (
    "pytest", "vitest", "FastAPI", "TestClient", "Next.js", "jsx", "MemoryRouter",
    "requirements.txt", "package.json", "```python", "```js", "__tests__", "jsdom",
)  # fmt: skip


def _repository(*runners: str) -> dict:
    """A product's repository as a task is handed it, testing with ``runners``."""
    patterns = {"luau": "*.spec.luau", "pytest": "test_*.py", "vitest": "*.test.ts"}
    return {
        "commit": "0beaac09c60662b41779f9b262dd3e6f18db1cdd",
        "map": "- `src/` (137 files)",
        "runners": [
            {"runner": r, "checks": [f"{r}_tests"], "roots": ["tests"], "file_pattern": patterns[r]}
            for r in runners
        ],
    }


async def _system_prompt(profile: str, inputs: dict) -> str:
    """The system message ``qa.test`` sends for ``inputs``, from the handler's own step."""
    context = MagicMock()
    context.role_id = "qa"
    context.ports.prompt_service = PromptAssembler(create_prompt_repository("filesystem"))
    context.ports.llm.default_model = "qwen2.5:7b"
    context.ports.request_renderer = None
    request = await QATestHandler()._generation_request(
        context,
        {"resolved_config": {"build_profile": profile}, **inputs},
        get_development_profile(profile),
        {},
        "Write the suite.",
        0.0,
    )
    [system, user] = request.messages
    assert (system.role, user.role, system.content) == ("system", "user", request.system_prompt)
    return system.content


def _as_shipped() -> str:
    """The prompt every ``qa.test`` was sent before #3147: the task type's own fragment, last."""
    return (
        PromptAssembler(create_prompt_repository("filesystem"))
        .assemble("qa", "agent_start", task_type=TaskType.QA_TEST)
        .content
    )


@pytest.mark.parametrize(
    ("profile", "inputs"),
    [
        ("fullstack_fastapi_react", {}),
        ("nextjs_ts", {}),
        ("node_vitest", {"source_repository": _repository("vitest")}),
        ("fullstack_fastapi_react", {"source_repository": _repository("pytest", "vitest")}),
        ("product_neutral", {"source_repository": _repository("pytest", "luau")}),
        ("product_neutral", {"source_repository": {**_repository(), "runners": []}}),
    ],
    ids=["fastapi-react", "nextjs", "a-vitest-product", "a-pytest-and-vitest-product",
         "a-product-with-luau-and-pytest", "a-product-with-no-runner"],
)  # fmt: skip
async def test_every_existing_stacks_prompt_is_byte_for_byte_what_it_was(profile, inputs):
    """The condition #3147 is in 2.8.1 on: with the same bytes, no existing stack's behaviour can
    move. Bugs caught:
    - the new fragment sent to a stack that isn't Luau-only: a sample application, a JavaScript
      product, one with runners of two languages, or one with none;
    - the task type's own fragment edited in the split, so every stack's prompt moves with no
      replay behind it."""
    from pathlib import Path

    import squadops.prompts

    fragment = (
        Path(squadops.prompts.__file__).parent / "fragments/shared/task_type/task_type.qa.test.md"
    )

    sent = await _system_prompt(profile, inputs)

    assert sent == _as_shipped()
    assert hashlib.sha256(fragment.read_bytes()).hexdigest() == _FRAGMENT_AS_SHIPPED
    assert "pytest or vitest" in sent and "MemoryRouter" in sent


@pytest.mark.parametrize("profile", ["game_dev_roblox", "product_neutral"])
async def test_a_luau_products_prompt_names_no_other_stacks_runner(profile):
    """#3147, under the Roblox profile and under ``product_neutral``, which the skills replay
    captures its tasks under (SIP-0116 §17p): the two must render one prompt. Bugs caught:
    - a Luau product's suite author told its suite runs under "pytest or vitest", with FastAPI,
      Next.js and JSX examples, beside the product's own Luau runner;
    - the rules that hold on every stack lost with the idioms: no server, discovery by the
      runner's own pattern, declared dependencies only, isolation, and a test per criterion;
    - the task-type layer dropped, so the author gets no rule at all."""
    sent = await _system_prompt(profile, {"source_repository": _repository("luau")})

    assert [word for word in _OTHER_STACKS if word in sent] == []
    assert sent != _as_shipped() and sent.startswith(_as_shipped().split("# Task:")[0])
    for rule in (
        "## Execution Environment (hard rule)",
        "the product's own test runner",
        "nothing you write can start one",
        "## Discovery Contract (hard rule)",
        "## Dependency Constraint (hard rule)",
        "## Test Isolation (hard rule)",
        "**Each acceptance criterion your task carries still gets its test,**",
        "```luau",
    ):
        assert rule in sent, rule


def test_a_variant_no_fragment_is_registered_for_is_refused_by_name():
    """The owner's ruling against silent fallbacks. Bug caught: a product kind asked for by name
    and given the task type's own fragment, or no task-type rules at all, with nothing said."""
    assembler = PromptAssembler(create_prompt_repository("filesystem"))

    with pytest.raises(ValueError, match="no prompt fragment task_type.qa.test.godot"):
        assembler.assemble("qa", "agent_start", task_type=TaskType.QA_TEST, variant="godot")
