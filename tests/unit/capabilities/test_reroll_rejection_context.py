"""#669 — the prior framing's rejection reaches the re-rolled plan authors.

A #522 re-roll previously granted fresh dice with zero context: the validator's
teaching message persisted in gate_decisions where no model ever read it, so the
re-roll was free to re-emit the exact rejected shape (fay-10 tripped the same
ownership class on all three framings; fay-15's framing-1 #658 rejection named
the file, the rule, and the consequence — to nobody). These cover the transport
end to end: the dispatch-side injection that puts the rejection on the authoring
envelopes, the handler section that renders it, and a live render of the managed
assets proving the teaching message and the rejected plan survive the templates.

The rejection fixture is fay-15 framing-1's real defect shape (cyc_6c185cba4811:
dev task claimed the frozen backend/store.py, #658-netted, blind re-roll).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.planning_tasks import (
    DevelopmentProposePlanTasksHandler,
    GovernancePreparePlanAuthoringBriefHandler,
    QaProposePlanTasksHandler,
    StrategyProposePlanGuidanceHandler,
)
from squadops.cycles.task_plan import _inject_rejection_context

pytestmark = [pytest.mark.domain_capabilities]

_FAY15_REJECTION = (
    "Task 2 (Backend store): development.develop declares expected artifact "
    "'backend/store.py', which is frozen (scaffold-owned) — no task may claim a "
    "frozen file as a deliverable; scaffold enforcement restores frozen bytes at "
    "emission, so the task cannot satisfy its expected artifacts and a repair "
    "scoped to it would target the wrong files"
)
_REJECTED_PLAN = "version: 1\ntasks:\n  - task_index: 2\n    focus: Backend store\n"

_AUTHORING_TASK_TYPES = (
    "governance.prepare_plan_authoring_brief",
    "development.propose_plan_tasks",
    "qa.propose_plan_tasks",
    "strategy.propose_plan_guidance",
)


# --- dispatch-side injection --------------------------------------------------- #


@pytest.mark.parametrize("task_type", _AUTHORING_TASK_TYPES)
def test_authoring_tasks_receive_the_rejection_context(task_type):
    inputs: dict = {}
    _inject_rejection_context(
        inputs,
        {"rejection_reasons": [_FAY15_REJECTION], "rejected_plan_yaml": _REJECTED_PLAN},
        task_type,
    )

    assert inputs["rejection_reasons"] == [_FAY15_REJECTION]
    assert inputs["rejected_plan_yaml"] == _REJECTED_PLAN


@pytest.mark.parametrize(
    "task_type",
    ["development.develop", "qa.test", "governance.merge_plan", "data.research_context"],
)
def test_non_authoring_tasks_do_not(task_type):
    """The merger's normal path is deterministic (no prompt) and build tasks
    author no plans — leaking a stale rejection there is pure prompt noise."""
    inputs: dict = {}
    _inject_rejection_context(inputs, {"rejection_reasons": [_FAY15_REJECTION]}, task_type)

    assert inputs == {}


def test_first_roll_injects_nothing():
    inputs: dict = {}
    _inject_rejection_context(inputs, None, "development.propose_plan_tasks")

    assert inputs == {}


def test_reasonless_context_injects_nothing():
    """A context with no usable reasons must not inject the plan alone — the
    appendix leads with the reasons; a plan without them is an instruction to
    copy the rejected shape."""
    inputs: dict = {}
    _inject_rejection_context(
        inputs,
        {"rejection_reasons": ["", "  "], "rejected_plan_yaml": _REJECTED_PLAN},
        "development.propose_plan_tasks",
    )

    assert inputs == {}


# --- handler section ----------------------------------------------------------- #


@pytest.mark.parametrize(
    "handler_cls",
    [
        DevelopmentProposePlanTasksHandler,
        QaProposePlanTasksHandler,
        StrategyProposePlanGuidanceHandler,
        GovernancePreparePlanAuthoringBriefHandler,
    ],
)
async def test_every_authoring_handler_renders_the_section(handler_cls):
    renderer = AsyncMock()
    renderer.render.side_effect = lambda template_id, variables: MagicMock(
        content=f"RENDERED:{template_id}"
    )

    out = await handler_cls()._rejection_context_section(
        renderer,
        {"rejection_reasons": [_FAY15_REJECTION], "rejected_plan_yaml": _REJECTED_PLAN},
    )

    assert out == "RENDERED:request.plan_reroll_rejection_appendix"
    calls = {c.args[0]: c.args[1] for c in renderer.render.await_args_list}
    # stripped: the appendix wraps the plan in a fenced block, so surrounding
    # whitespace would only add blank lines inside the fence
    assert calls["request.plan_reroll_rejected_plan_appendix"] == {
        "rejected_plan_yaml": _REJECTED_PLAN.strip()
    }
    main_vars = calls["request.plan_reroll_rejection_appendix"]
    assert main_vars["rejection_reasons"].startswith("- Task 2 (Backend store)")
    assert (
        main_vars["rejected_plan_section"] == "RENDERED:request.plan_reroll_rejected_plan_appendix"
    )


async def test_reasons_only_renders_without_the_plan_block():
    """An unreadable rejected-plan artifact degrades to reasons-only — the
    appendix must still render rather than dropping the teaching message."""
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="REJECTION BLOCK")

    out = await DevelopmentProposePlanTasksHandler()._rejection_context_section(
        renderer, {"rejection_reasons": [_FAY15_REJECTION]}
    )

    assert out == "REJECTION BLOCK"
    (template_id, variables) = renderer.render.await_args.args
    assert template_id == "request.plan_reroll_rejection_appendix"
    assert "rejected_plan_section" not in variables


async def test_absent_input_renders_nothing():
    renderer = AsyncMock()

    out = await DevelopmentProposePlanTasksHandler()._rejection_context_section(renderer, {})

    assert out == ""
    renderer.render.assert_not_awaited()


# --- the real assets ----------------------------------------------------------- #


async def test_real_assets_carry_the_teaching_message_and_the_plan():
    """A live render — the rejection must survive the templates, not just the
    function: the fay-15 teaching line, the revise-don't-repeat instruction,
    and the rejected plan body all present in the final section."""
    from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
    from squadops.prompts.renderer import RequestTemplateRenderer

    templates_dir = (
        Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "request_templates"
    )
    renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(
            fragments_path=templates_dir.parent / "fragments",
            templates_path=templates_dir,
        )
    )

    section = await DevelopmentProposePlanTasksHandler()._rejection_context_section(
        renderer,
        {"rejection_reasons": [_FAY15_REJECTION], "rejected_plan_yaml": _REJECTED_PLAN},
    )

    assert "PRIOR ATTEMPT REJECTED" in section
    assert "backend/store.py" in section
    assert "frozen (scaffold-owned)" in section
    assert "focus: Backend store" in section  # the rejected plan body
    assert "revise" in section.lower()


# --- #686: the plan-shape rules reach the same four authoring prompts ----------- #


@pytest.mark.parametrize(
    "handler_cls",
    [
        DevelopmentProposePlanTasksHandler,
        QaProposePlanTasksHandler,
        StrategyProposePlanGuidanceHandler,
        GovernancePreparePlanAuthoringBriefHandler,
    ],
)
async def test_every_authoring_handler_renders_the_plan_shape_rules(handler_cls):
    """Unlike the rejection appendix there is no input to key on — these rules hold for
    every plan on every roll, so a handler that renders them only sometimes would leave
    the first framing (the one shk-1 lost) exactly as uninformed as before."""
    renderer = AsyncMock()
    renderer.render.side_effect = lambda template_id, variables: MagicMock(
        content=f"RENDERED:{template_id}"
    )

    out = await handler_cls()._authoring_rules_section(renderer)

    assert out == "RENDERED:request.plan_authoring_rules_appendix"
    (template_id, variables) = renderer.render.await_args.args
    assert template_id == "request.plan_authoring_rules_appendix"
    assert variables == {}  # prose-only asset: no data to inject (#448)


async def test_real_asset_states_the_shk1_rule_in_the_rendered_section():
    """A live render through the real template, so a malformed asset header or a
    frontmatter typo fails here rather than silently rendering nothing into the prompt
    that was supposed to carry the teaching."""
    from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
    from squadops.prompts.renderer import RequestTemplateRenderer

    templates_dir = (
        Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "request_templates"
    )
    renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(
            fragments_path=templates_dir.parent / "fragments",
            templates_path=templates_dir,
        )
    )

    section = await DevelopmentProposePlanTasksHandler()._authoring_rules_section(renderer)

    assert "PLAN SHAPE RULES" in section
    assert "one-file-one-owner" in section  # the class that cost shk-1 a re-roll
    assert "expected_artifacts: []" in section  # the legitimate alternative
    assert "no-frozen-claims" in section  # #658
    assert "imports-must-exist" in section  # #671


@pytest.mark.parametrize(
    "template_id",
    [
        "request.planning_task_base",
        "request.development_propose_plan_tasks",
        "request.qa_propose_plan_tasks",
        "request.strategy_propose_plan_guidance",
    ],
)
def test_every_authoring_template_declares_and_places_the_slot(template_id):
    """Declaring the variable without placing it, or vice versa, renders nothing into
    the prompt while every handler-side test still passes — the silent-no-op shape this
    patch line keeps closing."""
    path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "squadops"
        / "prompts"
        / "request_templates"
        / f"{template_id}.md"
    )
    header, _, body = path.read_text(encoding="utf-8").partition("\n---\n")
    assert "- authoring_rules_section" in header
    assert "{{authoring_rules_section}}" in body
