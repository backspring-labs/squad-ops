"""The composer's count of a prompt against the prompt its handler renders (#2681).

The composer decides, before dispatch, whether a task's binding sections fit and how much lesson
text is left (``squadops.capabilities.prompt_budget``). The handler's guard then refuses a rendered
prompt over the window. Measured live, the composer counted a develop prompt 1,244 tokens short, so
a task it admitted was refused at the guard.

Each case renders a seam's prompt through its own handler, with the shipped fragments and
templates and inputs the size of a real dispatch's, and holds the composer's count at or above
the rendered prompt as the guard measures it. The margin is stated, so a declaration that grows it
past use is seen.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.prompt_budget import prompt_without_memory_tokens

pytestmark = [pytest.mark.domain_memory]

#: How far above the rendered prompt the composer's count may sit: the templates a path doesn't
#: render and the system prompt's largest variants, counted anyway as an upper bound.
_MARGIN = 10000

_PRD = (
    "# Shelfnote\n\n" + "A shared reading list: a person adds a book and leaves notes on it.\n" * 60
)
_CODE = "def handler(request):\n    return {'ok': True, 'items': list(range(10))}\n\n" * 40
_FILES = {f"backend/module_{i}.py": _CODE for i in range(6)}
_REPOSITORY = {
    "commit": "433f6c51d8041151b20233f28194ddb4af937c63",
    "map": "\n".join(f"backend/module_{i}.py" for i in range(30)),
    "checks": [{"id": "backend_tests", "argv": [".venv/bin/python", "-m", "pytest", "-q"]}],
    "instructions": {"CONTRIBUTING.md": "Run the tests before a change.\n" * 20},
    "existing_files": {"backend/routes.py": _CODE},
}


def _context(sent: list, role: str):
    from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
    from squadops.llm.models import ChatMessage
    from squadops.prompts.assembler import PromptAssembler
    from squadops.prompts.renderer import RequestTemplateRenderer

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content="```python:a.py\nx = 1\n```\n")

    context = MagicMock()
    context.role_id = role
    context.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=_chat)
    context.ports.llm.default_model = "qwen2.5:14b"
    context.ports.prompt_service = PromptAssembler(create_prompt_repository("filesystem"))
    context.ports.llm_observability = None
    context.ports.request_renderer = RequestTemplateRenderer(
        create_prompt_asset_source("filesystem")
    )
    context.correlation_context = None
    context.disputed_checks = []
    context.task_id = "task-1"
    return context


def _rendered(messages) -> int:
    """The prompt as the guard measures it (``prompt_guard._estimate_tokens``)."""
    return len("\n\n".join(str(m.content) for m in messages)) // 4


async def _develop(inputs):
    from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler

    sent: list = []
    await DevelopmentDevelopHandler().handle(_context(sent, "dev"), inputs)
    return sent[0]


async def _qa_test(inputs, monkeypatch):
    from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
    from squadops.capabilities.handlers.test_runner import RunTestsResult

    monkeypatch.setattr(
        "squadops.capabilities.handlers.test_runner.run_generated_tests",
        AsyncMock(return_value=RunTestsResult(executed=True, exit_code=0, stdout="1 passed")),
    )
    sent: list = []
    await QATestHandler().handle(_context(sent, "qa"), inputs)
    return sent[0]


#: #2805: a product of three top-level packages, the suite's own the smallest. Outside the suite's
#: package it holds more than the margin, so a count of the whole tree where the handler shows a
#: part of it fails the margin, and a count of a part where the handler shows it whole fails the
#: floor.
_PRODUCT = {
    **{f"orbit/module_{i}.py": _CODE for i in range(8)},
    **{f"console/src/view_{i}.jsx": _CODE for i in range(12)},
    **{f"tests/test_area_{i}.py": _CODE for i in range(4)},
}

_BUILD = {
    "prd": _PRD,
    "agent_model": "qwen2.5:14b",
    "resolved_config": {"build_profile": "python_cli_builder", "generation_timeout": 300},
    "artifact_contents": _FILES,
    "source_repository": _REPOSITORY,
    "acceptance_workspace_files": {f"backend/tree_{i}.py": _CODE for i in range(20)},
    "workspace_revision_id": "wsr_0123456789abcdef",
    "artifact_refs": [f"art_{i:012x}" for i in range(40)],
}


async def _builder(inputs):
    from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler

    sent: list = []
    await BuilderAssembleHandler().handle(_context(sent, "builder"), inputs)
    return sent[0]


async def _design_plan(inputs):
    from squadops.capabilities.handlers.planning.framing import DevelopmentDesignPlanHandler

    sent: list = []
    await DevelopmentDesignPlanHandler().handle(_context(sent, "dev"), inputs)
    return sent[0]


async def _proposer(task_type, inputs):
    from squadops.capabilities.handlers.planning_tasks import (
        DevelopmentProposePlanTasksHandler,
        QaProposePlanTasksHandler,
        StrategyProposePlanGuidanceHandler,
    )

    handler, role = {
        "development.propose_plan_tasks": (DevelopmentProposePlanTasksHandler, "dev"),
        "qa.propose_plan_tasks": (QaProposePlanTasksHandler, "qa"),
        "strategy.propose_plan_guidance": (StrategyProposePlanGuidanceHandler, "strat"),
    }[task_type]
    sent: list = []
    await handler().handle(_context(sent, role), inputs)
    return sent[0]


async def _increment_proposer(inputs):
    """The increment proposal's own test context (its campaign block and baseline), with the
    shipped fragments and templates in place of its stand-ins."""
    from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
    from squadops.capabilities.handlers.planning.proposal import StrategyProposeIncrementHandler
    from squadops.prompts.assembler import PromptAssembler
    from squadops.prompts.renderer import RequestTemplateRenderer
    from tests.unit.capabilities.test_strategy_propose_increment import _REFERENCE, _ctx, _fenced

    ctx = _ctx(_fenced(_REFERENCE))
    ctx.role_id = "strat"
    ctx.ports.prompt_service = PromptAssembler(create_prompt_repository("filesystem"))
    ctx.ports.request_renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    await StrategyProposeIncrementHandler().handle(ctx, inputs)
    return ctx.ports.llm.chat_stream_with_usage.call_args_list[0].args[0]


def _proposer_inputs() -> dict:
    from tests.unit.capabilities.test_propose_plan_tasks import _seeded_inputs

    return {**_seeded_inputs(), "agent_model": "qwen2.5:14b", "source_repository": _REPOSITORY}


def _proposal_inputs() -> dict:
    """The increment proposal's inputs with the evidence it is shown (SIP-0113 §4.5), so the
    sections that render it are in the prompt measured."""
    from squadops.outcomes.proposal_evidence import PROPOSAL_EVIDENCE_INPUT
    from tests.unit.capabilities.test_strategy_propose_increment import _EVIDENCE, _inputs

    return {**_inputs(), "agent_model": "qwen2.5:14b", PROPOSAL_EVIDENCE_INPUT: _EVIDENCE}


@pytest.mark.parametrize(
    "task_type",
    ["development.propose_plan_tasks", "qa.propose_plan_tasks", "strategy.propose_plan_guidance"],
)
async def test_the_composers_count_covers_each_plan_proposer(task_type):
    """#2681, entered at each plan proposer's ``handle``: the plan-authoring appendices are the
    largest templates any seam declares, so a miss here would be the largest."""
    inputs = _proposer_inputs()
    rendered = _rendered(await _proposer(task_type, inputs))
    estimate = prompt_without_memory_tokens(SimpleNamespace(task_type=task_type, inputs=inputs))

    assert rendered <= estimate <= rendered + _MARGIN, (task_type, estimate, rendered)


async def test_the_composers_count_covers_the_increment_proposal():
    """#2681, entered at the increment proposer's ``handle``, its campaign block and evidence on
    its inputs (SIP-0113 §4.5): what the proposal is shown is counted as its own."""
    inputs = _proposal_inputs()
    rendered = _rendered(await _increment_proposer(inputs))
    estimate = prompt_without_memory_tokens(
        SimpleNamespace(task_type="strategy.propose_increment", inputs=inputs)
    )

    assert rendered <= estimate <= rendered + _MARGIN, (estimate, rendered)


def _real_prompts(ctx, role: str):
    """A handler test's context with the shipped fragments and templates in place of its
    stand-ins."""
    from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
    from squadops.prompts.assembler import PromptAssembler
    from squadops.prompts.renderer import RequestTemplateRenderer

    ctx.role_id = role
    ctx.ports.prompt_service = PromptAssembler(create_prompt_repository("filesystem"))
    ctx.ports.request_renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    return ctx


async def test_the_composers_count_covers_a_correction_repair():
    """#2681, entered at a correction repair's ``handle``: the seam declaring the most templates,
    and the one carrying the accepted tree it repairs."""
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
    )
    from tests.unit.capabilities.test_repair_decision_section import _EDIT, _context, _inputs

    ctx = _real_prompts(_context(_EDIT, _EDIT, _EDIT, _EDIT), "dev")
    inputs = {
        **_inputs({}),
        "agent_model": "qwen2.5:14b",
        "prd": _PRD,
        "failure_evidence": {"failed_checks": [{"id": "T1", "detail": _CODE[:2000]}]},
        "artifact_contents": _FILES,
        "acceptance_workspace_files": {**_FILES, "backend/routes.py": _CODE},
        "source_repository": _REPOSITORY,
    }
    await DevelopmentCorrectionRepairHandler().handle(ctx, inputs)
    rendered = _rendered(ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0])
    estimate = prompt_without_memory_tokens(
        SimpleNamespace(task_type="development.correction_repair", inputs=inputs)
    )

    assert rendered <= estimate <= rendered + _MARGIN, (estimate, rendered)


#: #2810: a qa suite's failing case, on the line of the product's suite its repair is shown.
_FAILING_CASES = {
    "validation_result": {
        "summary": "1 failed",
        "checks": [
            {
                "check": "tests_pass",
                "passed": False,
                "failing_cases": [
                    {"file": "tests/test_area_1.py", "title": "test_area", "failing_line": 5}
                ],
            }
        ],
    }
}


@pytest.mark.parametrize(
    ("task_type", "role", "named", "evidence"),
    [
        ("development.correction_repair", "dev", "orbit/module_1.py", {"error": "a 500"}),
        ("qa.test_repair", "qa", "tests/test_area_1.py", _FAILING_CASES),
    ],
    ids=["dev", "qa"],
)
async def test_the_composers_count_covers_a_repair_on_a_product_it_shows_one_file_of(
    task_type, role, named, evidence
):
    """#2810, entered at each repair's ``handle``: the repair carries a product of three packages
    as its tree and the failed task's own file over it, and its prompt shows the one file it may
    revise, its edit form and, for the qa repair, the failing case's frame. Outside that file the
    product holds more than the margin, so a count of the whole tree fails the margin and holds a
    repair that fits, and a count short of what the three sections show fails the floor."""
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
        QATestRepairHandler,
    )
    from tests.unit.capabilities.test_repair_decision_section import _EDIT, _context

    handler = {"dev": DevelopmentCorrectionRepairHandler, "qa": QATestRepairHandler}[role]()
    ctx = _real_prompts(_context(_EDIT, _EDIT), role)
    inputs = {
        "prd": _PRD,
        "agent_model": "qwen2.5:14b",
        "failed_task_type": "qa.test" if role == "qa" else "development.develop",
        "failure_evidence": evidence,
        "correction_decision": {"correction_path": "patch", "decision_rationale": "patch it"},
        "expected_artifacts": [named],
        "acceptance_workspace_files": _PRODUCT,
        "failed_task_artifacts": [{"name": named, "content": _CODE.replace("10", "11")}],
    }
    await handler.handle(ctx, inputs)
    rendered = _rendered(ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0])
    estimate = prompt_without_memory_tokens(SimpleNamespace(task_type=task_type, inputs=inputs))

    assert rendered <= estimate <= rendered + _MARGIN, (estimate, rendered)


async def test_the_composers_count_covers_the_manifest_author():
    """#2681, entered at the manifest author's ``handle``, which renders the longest rules."""
    from squadops.capabilities.handlers.planning.manifest import DevelopmentAuthorManifestHandler
    from tests.unit.capabilities.test_manifest_authoring_stage import (
        _clean_manifest,
        _context,
        _fenced,
        _inputs,
    )

    ctx = _real_prompts(_context(_fenced(_clean_manifest())), "dev")
    inputs = {**_inputs(), "agent_model": "qwen2.5:14b"}
    await DevelopmentAuthorManifestHandler().handle(ctx, inputs)
    rendered = _rendered(ctx.ports.llm.chat_stream_with_usage.call_args_list[0].args[0])
    estimate = prompt_without_memory_tokens(
        SimpleNamespace(task_type="development.author_manifest", inputs=inputs)
    )

    assert rendered <= estimate <= rendered + _MARGIN, (estimate, rendered)


@pytest.mark.parametrize(
    ("task_type", "author", "inputs"),
    [
        ("builder.assemble", _builder, _BUILD),
        (
            "development.design_plan",
            _design_plan,
            {
                "prd": _PRD,
                "agent_model": "qwen2.5:14b",
                "resolved_config": {"build_profile": "python_cli_builder"},
                "prior_outputs": {"strat": _PRD[:2000], "data": _PRD[:2000]},
                "source_repository": _REPOSITORY,
            },
        ),
    ],
    ids=["builder", "design-plan"],
)
async def test_the_composers_count_covers_the_other_authors(task_type, author, inputs):
    """#2681, entered at the builder's and a plan writer's ``handle``. Bug caught: a seam whose
    declared templates or inputs miss what its handler renders, counted short."""
    rendered = _rendered(await author(inputs))
    estimate = prompt_without_memory_tokens(SimpleNamespace(task_type=task_type, inputs=inputs))

    assert rendered <= estimate <= rendered + _MARGIN, (task_type, estimate, rendered)


@pytest.mark.parametrize(
    ("seam", "inputs"),
    [
        (
            "develop, focused",
            {**_BUILD, "subtask_focus": "the books API", "expected_artifacts": ["backend/a.py"]},
        ),
        ("develop, monolithic", _BUILD),
        (
            "qa.test, focused",
            {
                **_BUILD,
                "subtask_focus": "the books API suite",
                "expected_artifacts": ["tests/test_books.py"],
            },
        ),
        ("qa.test, monolithic", {**_BUILD, "artifact_contents": {"validation_plan.md": _PRD}}),
        (
            "develop, focused, one package of a larger product",
            {
                **_BUILD,
                "artifact_contents": _PRODUCT,
                "subtask_focus": "the area API",
                "expected_artifacts": ["orbit/area.py"],
            },
        ),
        (
            "qa.test, focused, one package of a larger product",
            {
                **_BUILD,
                "artifact_contents": _PRODUCT,
                "subtask_focus": "the area suite",
                "expected_artifacts": ["tests/test_area_new.py"],
            },
        ),
        (
            "qa.test, monolithic, a product with its suites and a frontend",
            {**_BUILD, "artifact_contents": {**_PRODUCT, "validation_plan.md": _PRD}},
        ),
    ],
)
async def test_the_composers_count_is_never_below_the_rendered_prompt(seam, inputs, monkeypatch):
    """#2681, entered at each handler's ``handle``. Bug caught: the composer counting less than the
    handler renders (the envelope's JSON alone, no system prompt or template), so binding sections
    it admits overflow the window and the guard refuses the task instead of the composer holding
    it. #2805's cases put a product of several packages in ``artifact_contents``: ``qa.test`` shows
    a part of it, so a count of the whole fails the margin and holds a task that fits; develop
    shows it whole, so a count of a part fails the floor."""
    task_type = "qa.test" if seam.startswith("qa.test") else "development.develop"
    messages = await (_qa_test(inputs, monkeypatch) if task_type == "qa.test" else _develop(inputs))
    estimate = prompt_without_memory_tokens(SimpleNamespace(task_type=task_type, inputs=inputs))
    rendered = _rendered(messages)

    assert estimate >= rendered, (seam, estimate, rendered)
    assert estimate - rendered <= _MARGIN, (seam, estimate, rendered)
