"""The lessons' slot at plan writing and build authoring (SIP-0110 §0.9; slice 3c, #2096).

Two properties. **A task handed no lesson renders the prompt it rendered before memory existed:**
every template that carries the slot renders byte-identical to the same template without it. **A
task handed lessons shows them,** with the statement that its requirements come first, through
each author's own ``handle()`` on the shipped templates.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from adapters.prompts.factory import create_prompt_asset_source
from squadops.capabilities.handlers.cross_cycle_lessons import cross_cycle_lessons_section
from squadops.memory.recall import LESSONS_INPUT
from squadops.prompts.asset_models import ResolvedAsset
from squadops.prompts.renderer import RequestTemplateRenderer
from tests.unit.campaigns.test_prior_cycle import _SOURCES, _author_context, _rendered

pytestmark = [pytest.mark.domain_memory]

_TEMPLATES = Path(__file__).resolve().parents[3] / "src/squadops/prompts/request_templates"
_SLOT = "{{cross_cycle_lessons_section}}"

#: Every template a plan-writing or build-authoring author renders, and the slot the lessons'
#: slot shares a line with.
_SLOTTED = {
    "request.planning_task_base": "prior_cycle_section",
    "request.development_author_manifest": "rejection_context_section",
    "request.development_propose_plan_tasks": "prior_cycle_section",
    "request.qa_propose_plan_tasks": "prior_cycle_section",
    "request.strategy_propose_plan_guidance": "prior_cycle_section",
    "request.development_develop.focused_build_task": "prior_cycle_section",
    "request.builder_assemble.build_assemble": "prior_cycle_section",
    "request.strategy_propose_increment": "prd_section",
    "request.cycle_repair_task": "disputed_checks_section",
}

_LESSONS = {
    "snapshot": "snp_0123456789abcdef",
    "lessons": [
        {"revision_id": "pat_a@1", "text": "Name the manifest element each criterion checks."},
        {"revision_id": "pat_b@2", "text": "Declare the response field the client reads."},
    ],
}
_HEADING = "## LESSONS FROM THIS PROJECT'S EARLIER CYCLES"


def _shows_the_lessons(prompt: str) -> bool:
    return (
        _HEADING in prompt
        and "1. Name the manifest element each criterion checks." in prompt
        and "2. Declare the response field the client reads." in prompt
        and "follow the requirements and leave the lesson aside" in prompt
    )


class _Text:
    """An asset source serving one template's text, whatever it is asked for."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def resolve_request_template(self, template_id: str, environment: str):
        return ResolvedAsset(template_id, self._text, "t", environment, "h")


async def _render(text: str, variables: dict[str, str]) -> str:
    return (await RequestTemplateRenderer(_Text(text)).render("t", variables)).content


def _without_the_slot(text: str) -> str:
    """The template as it was before the lessons' slot: no placeholder, no declaration. A
    placeholder on a line of its own takes its line with it, since that line came with it."""
    text = re.sub(r"^" + re.escape(_SLOT) + r"\n", "", text, flags=re.MULTILINE)
    return text.replace(_SLOT, "").replace("  - cross_cycle_lessons_section\n", "")


def _variables(text: str, which: str) -> dict[str, str]:
    _, front, _ = text.split("---", 2)
    meta = yaml.safe_load(front)
    required = list(meta.get("required_variables") or [])
    optional = [
        v for v in meta.get("optional_variables") or [] if v != "cross_cycle_lessons_section"
    ]
    chosen = {
        "sparse": required,
        "full": required + optional,
        "neighbour": required + [_SLOTTED[which.split(":")[1]]],
    }[which.split(":")[0]]
    return {name: f"<{name} text>" for name in chosen}


@pytest.mark.parametrize("template_id", sorted(_SLOTTED))
@pytest.mark.parametrize("fill", ["sparse", "full", "neighbour"])
async def test_a_task_handed_no_lesson_renders_the_prompt_it_rendered_before_memory(
    template_id, fill
):
    """§0.9's inertness, at the template. Bug caught: the slot's own line left in the prompt when
    it is empty, so every counted roll's prompt changes on the day memory ships with nothing
    approved, and the regression yardstick moves under the comparison it exists for (D12)."""
    text = (_TEMPLATES / f"{template_id}.md").read_text(encoding="utf-8")
    variables = _variables(text, f"{fill}:{template_id}")

    assert _SLOT in text
    assert await _render(text, variables) == await _render(_without_the_slot(text), variables)


@pytest.mark.parametrize("template_id", sorted(_SLOTTED))
async def test_supplied_lessons_render_as_their_own_paragraph_after_their_neighbour(template_id):
    """Bug caught: the lessons run into the neighbouring slot's last line, so a model reads a
    lesson as part of the failed cycle's record or of the plan's rejection."""
    text = (_TEMPLATES / f"{template_id}.md").read_text(encoding="utf-8")
    neighbour = _SLOTTED[template_id]
    shipped = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    section = await cross_cycle_lessons_section(shipped, {LESSONS_INPUT: _LESSONS})
    variables = {
        **_variables(text, f"neighbour:{template_id}"),
        "cross_cycle_lessons_section": section,
    }

    prompt = await _render(text, variables)

    assert f"<{neighbour} text>\n\n{_HEADING}\n" in prompt
    assert _shows_the_lessons(prompt)
    last = "2. Declare the response field the client reads."
    assert prompt.rstrip("\n").endswith(last) or f"{last}\n\n" in prompt


async def test_a_lesson_input_with_no_lessons_renders_nothing():
    shipped = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))

    for inputs in (
        {},
        {LESSONS_INPUT: {"snapshot": "snp_x", "lessons": []}},
        {LESSONS_INPUT: None},
    ):
        assert await cross_cycle_lessons_section(shipped, inputs) == ""


@pytest.mark.parametrize(
    "handler_path",
    [
        "squadops.capabilities.handlers.planning.framing.DevelopmentDesignPlanHandler",
        "squadops.capabilities.handlers.planning.brief.GovernancePreparePlanAuthoringBriefHandler",
    ],
)
async def test_a_framing_author_shows_the_lessons_it_is_handed(handler_path):
    """Wiring, entered at the author's real ``handle()`` with the shipped assets. Bug caught: the
    lessons on the envelope and absent from the prompt (#1845's and #1289's shape)."""
    import importlib

    module, _, name = handler_path.rpartition(".")
    handler_cls = getattr(importlib.import_module(module), name)
    base = {"prd": "the PRD", "resolved_config": {}}

    shown = await _rendered(handler_cls(), {**base, LESSONS_INPUT: _LESSONS})
    plain = await _rendered(handler_cls(), base)

    assert _shows_the_lessons(shown)
    assert _HEADING not in plain


async def test_the_manifest_author_shows_the_lessons_it_is_handed():
    from squadops.capabilities.handlers.planning.manifest import DevelopmentAuthorManifestHandler
    from squadops.cycles.manifest_authoring import AUTHORING_INPUT_CONTRACT
    from tests.unit.capabilities.test_manifest_authoring_stage import (
        _clean_manifest,
        _context,
        _fenced,
        _inputs,
    )

    prompts = []
    for inputs in (_inputs(**{LESSONS_INPUT: _LESSONS}), _inputs()):
        ctx = _context(_fenced(_clean_manifest()))
        ctx.ports.request_renderer = RequestTemplateRenderer(
            create_prompt_asset_source("filesystem")
        )
        await DevelopmentAuthorManifestHandler().handle(ctx, inputs)
        messages = ctx.ports.llm.chat_stream_with_usage.call_args_list[0].args[0]
        prompts.append("\n".join(str(m.content) for m in messages))

    assert _shows_the_lessons(prompts[0])
    assert _HEADING not in prompts[1]
    # §5c.1: the manifest author reads only declared inputs, and the lessons are one of them.
    assert LESSONS_INPUT in AUTHORING_INPUT_CONTRACT


async def test_the_increment_proposer_shows_the_lessons_it_is_handed():
    """Proposal writing (§0.9), entered at the real ``handle()``. Bug caught: the lessons merged
    into the supervisor's revision note, or absent from the proposal prompt altogether."""
    from squadops.capabilities.handlers.planning.proposal import StrategyProposeIncrementHandler
    from tests.unit.capabilities.test_strategy_propose_increment import (
        _REFERENCE,
        _ctx,
        _fenced,
        _inputs,
    )

    prompts = []
    for extra in ({LESSONS_INPUT: _LESSONS}, {}):
        ctx = _ctx(_fenced(_REFERENCE))
        await StrategyProposeIncrementHandler().handle(ctx, {**_inputs(), **extra})
        messages = ctx.ports.llm.chat_stream_with_usage.call_args_list[0].args[0]
        prompts.append("\n".join(str(m.content) for m in messages))

    assert _shows_the_lessons(prompts[0])
    assert _HEADING not in prompts[1]


@pytest.mark.parametrize("proposer", ["dev", "qa", "strat"])
async def test_each_proposer_shows_the_lessons_it_is_handed(proposer):
    from squadops.capabilities.handlers.planning_tasks import (
        DevelopmentProposePlanTasksHandler,
        QaProposePlanTasksHandler,
        StrategyProposePlanGuidanceHandler,
    )
    from tests.unit.capabilities.test_propose_plan_tasks import (
        _DEV_PROPOSAL_RESPONSE,
        _QA_PROPOSAL_RESPONSE,
        _STRATEGY_GUIDANCE_RESPONSE,
        _make_context,
        _seeded_inputs,
    )

    handler_cls, response = {
        "dev": (DevelopmentProposePlanTasksHandler, _DEV_PROPOSAL_RESPONSE),
        "qa": (QaProposePlanTasksHandler, _QA_PROPOSAL_RESPONSE),
        "strat": (StrategyProposePlanGuidanceHandler, _STRATEGY_GUIDANCE_RESPONSE),
    }[proposer]
    prompts = []
    for extra in ({LESSONS_INPUT: _LESSONS}, {}):
        context = _make_context(response)
        context.ports.request_renderer = RequestTemplateRenderer(
            create_prompt_asset_source("filesystem")
        )
        await handler_cls().handle(context, {**_seeded_inputs(), **extra})
        messages = context.ports.llm.chat_stream_with_usage.call_args.args[0]
        prompts.append("\n".join(str(m.content) for m in messages))

    assert _shows_the_lessons(prompts[0])
    assert _HEADING not in prompts[1]


@pytest.mark.parametrize(
    ("handler", "inputs"),
    [
        ("develop", {"subtask_focus": "the limit", "expected_artifacts": ["a.py"]}),
        (
            "qa_test",
            {
                "artifact_contents": _SOURCES,
                "subtask_focus": "the limit suite",
                "expected_artifacts": ["tests/test_limit.py"],
            },
        ),
        (
            "builder",
            {
                "resolved_config": {"build_profile": "python_cli_builder"},
                "artifact_contents": _SOURCES,
            },
        ),
    ],
)
async def test_each_build_author_shows_the_lessons_it_is_handed(handler, inputs, monkeypatch):
    """Build authoring is where a correction-round lesson is front-loaded (§0.9). Bug caught: the
    lessons reaching the dev and not the author of the suite whose check failed, or a template
    slot no handler fills."""
    from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler
    from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
    from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
    from squadops.capabilities.handlers.test_runner import RunTestsResult

    monkeypatch.setattr(
        "squadops.capabilities.handlers.test_runner.run_generated_tests",
        AsyncMock(return_value=RunTestsResult(executed=True, exit_code=0, stdout="1 passed")),
    )
    author = {
        "develop": DevelopmentDevelopHandler,
        "qa_test": QATestHandler,
        "builder": BuilderAssembleHandler,
    }[handler]
    base = {"prd": "the PRD", **inputs}
    shown: list = []
    plain: list = []

    await author().handle(_author_context(shown), {**base, LESSONS_INPUT: _LESSONS})
    await author().handle(_author_context(plain), base)

    assert _shows_the_lessons("\n".join(str(m.content) for m in shown[0]))
    assert _HEADING not in "\n".join(str(m.content) for m in plain[0])


async def test_a_correction_repair_shows_the_lessons_it_is_handed_after_its_failure_evidence():
    """Repair (§0.9), entered at the real ``handle()`` on the shipped templates. Bugs caught: the
    lessons absent from the repair prompt; or placed among the failure evidence, so a lesson reads
    as part of why this attempt failed."""
    from squadops.capabilities.handlers.impl.repair_handlers import (
        DevelopmentCorrectionRepairHandler,
    )
    from tests.unit.capabilities.test_repair_decision_section import (
        _EDIT,
        _context,
        _inputs,
        _user_prompt,
    )

    prompts = []
    for extra in ({LESSONS_INPUT: _LESSONS}, {}):
        ctx = _context(_EDIT)
        await DevelopmentCorrectionRepairHandler().handle(ctx, {**_inputs({}), **extra})
        prompts.append(_user_prompt(ctx))

    assert _shows_the_lessons(prompts[0])
    assert prompts[0].index("### Why the Prior Attempt Failed") < prompts[0].index(_HEADING)
    assert prompts[0].index(_HEADING) < prompts[0].index("### Product Requirements Document")
    assert _HEADING not in prompts[1]
