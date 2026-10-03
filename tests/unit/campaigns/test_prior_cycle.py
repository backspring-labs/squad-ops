"""The prior-cycle brief (#1692; SIP-0109 §10a): a retry or a repair is told what the failed
cycle before it recorded — from its typed assessment, never a narrative — and every authoring stage
handed it shows it."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.campaigns.prior_cycle import brief_lines, prior_cycle_brief
from squadops.cycles.cycle_assessment import (
    AssessorIdentity,
    AttributionReading,
    CycleEvidence,
    IndicatorState,
    RunRecord,
    assess,
)
from squadops.cycles.failure_attribution import Attribution, AttributionClass
from squadops.cycles.verification_integrity import CycleOutcome, RunVerdict

NOW = datetime(2026, 10, 2, tzinfo=UTC)


def _failed(cycle_id="cyc_inc"):
    run = RunRecord("run_impl", 2, "implementation", "completed", NOW, NOW)
    latest = assess(
        CycleOutcome(
            verdict=RunVerdict.REJECTED,
            verified=("frontend_build",),
            failed=("tests_pass",),
            unverified=(),
            run_count=1,
            criteria_verified=(),
            criteria_total=(),
        ),
        CycleEvidence(cycle_id=cycle_id, runs=(run,), verification_summary_runs=("run_impl",)),
        assessor=AssessorIdentity("2.0.0", None),
    )
    return dataclasses.replace(
        latest,
        attribution=AttributionReading(
            IndicatorState.OBSERVED,
            Attribution(
                primary=AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE, contributing=()
            ),
        ),
    )


def test_the_brief_is_the_failed_cycles_own_record():
    """Bugs caught: the successor told nothing (as blind as the cycle that failed), or told a
    failed check that never failed; an unaskable indicator read as "nothing failed"."""
    brief = prior_cycle_brief(_failed())

    assert brief["cycle_id"] == "cyc_inc"
    assert brief["verdict"] == "rejected"
    assert brief["failed_checks"] == ["tests_pass"]
    assert brief["primary_cause"] == str(AttributionClass.ENVIRONMENT_OR_INFRASTRUCTURE_FAILURE)
    assert brief["correction_movements"].startswith("unaskable: ")  # no run summary stored
    lines = brief_lines(brief)
    assert "- failed checks: `tests_pass`" in lines
    assert "why_failed" not in brief  # no stored reason: none is invented
    assert "- correction movements: not recorded (no_run_summary: run_impl)" in lines
    assert brief_lines(None) == "" and brief_lines({}) == ""


def test_why_each_check_failed_is_its_latest_runs_own_reason():
    """Bugs caught: an earlier run's superseded reason shown as the cause; a reason for a check
    the cycle did not fail (it passed in a later run) shown as a failure; a disputed check shown
    as an undisputed one; a whole runner log pasted in unbounded; reason text that closes the
    fence it is shown in."""
    from squadops.campaigns.prior_cycle import REASON_LIMIT
    from squadops.cycles.verification_integrity import Contest, FailedCheck

    log = "```\n" + "E" * (REASON_LIMIT + 50)
    brief = prior_cycle_brief(
        _failed(),
        [
            FailedCheck("tests_pass", "an earlier run's reason", True),
            FailedCheck("frontend_build", "failed once, passed later", True),
            FailedCheck(
                "tests_pass",
                log,
                True,
                contested=Contest(by="development", reason="the test is wrong"),
            ),
        ],
    )

    (why,) = brief["why_failed"]
    assert (why["check_id"], why["contested"]) == ("tests_pass", True)
    assert why["reason"].endswith(f"(cut at {REASON_LIMIT} of {len(log)} characters)")
    lines = brief_lines(brief)
    assert "`tests_pass`:\n````\n" in lines  # a longer fence than any backtick run inside
    assert "Its producer disputed `tests_pass`." in lines
    assert "an earlier run's reason" not in lines and "frontend_build" not in lines


async def _rendered(handler, inputs):
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.prompts.renderer import RequestTemplateRenderer

    sent: list[str] = []

    async def _llm_call(context, messages, chat_kwargs, **_):
        sent.append(messages[-1].content)
        return MagicMock(), "the document"

    handler._llm_call = _llm_call
    context = MagicMock()
    context.ports.request_renderer = RequestTemplateRenderer(
        create_prompt_asset_source("filesystem")
    )
    context.ports.prompt_service.assemble.return_value = MagicMock(content="sys", assembly_hash="h")
    await handler.handle(context, inputs)
    return sent[0]


async def test_a_retrys_framing_is_shown_the_failed_cycle():
    """Wiring, entered at the technical design's real ``handle()`` with the shipped assets. Bug
    caught: the brief carried on the envelope and absent from the prompt (#1845's shape)."""
    from squadops.capabilities.handlers.planning.framing import DevelopmentDesignPlanHandler

    prompt = await _rendered(
        DevelopmentDesignPlanHandler(),
        {
            "prd": "the PRD",
            "resolved_config": {},
            "prior_cycle_brief": brief_lines(prior_cycle_brief(_failed())),
        },
    )

    assert "THIS INCREMENT WAS ATTEMPTED BEFORE, AND FAILED" in prompt
    assert "- failed checks: `tests_pass`" in prompt


#: The authors a retry or a repair runs, and the template each one's brief renders into
#: (``None``: the qa author appends its sections to the focused prompt it builds).
_AUTHORS = {
    "development.design_plan": "request.planning_task_base",
    "qa.define_test_strategy": "request.planning_task_base",
    "governance.prepare_plan_authoring_brief": "request.planning_task_base",
    "development.propose_plan_tasks": "request.development_propose_plan_tasks",
    "qa.propose_plan_tasks": "request.qa_propose_plan_tasks",
    "strategy.propose_plan_guidance": "request.strategy_propose_plan_guidance",
    "development.develop": "request.development_develop.focused_build_task",
    "qa.test": None,
    "builder.assemble": "request.builder_assemble.build_assemble",
}


def test_the_registry_names_exactly_the_authors_handed_the_brief():
    """Entered at ``generate_task_plan``'s composer, keyed by the registry. Bugs caught: a brief
    handed to a task that does not author (the evaluator, the merger — prompt noise), or an
    author the registry forgot, which is never told."""
    from squadops.capabilities.context_assembly import CONTEXT_CONTRACTS
    from squadops.cycles.task_plan import _prior_cycle_inputs

    brief = prior_cycle_brief(_failed())
    bound = {"campaign_proposal": {"proposal_id": "p", "prior_cycle": brief}}
    flagged = {str(t) for t, c in CONTEXT_CONTRACTS.items() if c.prior_cycle_brief}

    assert flagged == set(_AUTHORS)
    for task_type in (*_AUTHORS, "qa.evaluate_increment", "governance.merge_plan"):
        handed = _prior_cycle_inputs(bound, task_type)
        assert handed == (
            {"prior_cycle_brief": brief_lines(brief)} if task_type in _AUTHORS else {}
        )
    assert _prior_cycle_inputs({"campaign_proposal": {"proposal_id": "p"}}, "qa.test") == {}
    assert _prior_cycle_inputs({}, "qa.test") == {}


@pytest.mark.parametrize("template_id", sorted({t for t in _AUTHORS.values() if t}))
def test_every_authors_template_declares_and_places_the_slot(template_id):
    """Declared and not placed, or placed and not declared, renders nothing while every
    handler-side test passes — the silent no-op this registry exists to close."""
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[3]
        / "src/squadops/prompts/request_templates"
        / f"{template_id}.md"
    )
    header, _, body = path.read_text(encoding="utf-8").partition("\n---\n")
    assert "- prior_cycle_section" in header
    assert "{{prior_cycle_section}}" in body


async def test_a_retrys_proposers_are_shown_the_failed_cycle():
    """Wiring, entered at a proposer's real ``handle()``. Bug caught: the brief handed to a
    proposer whose handler never passes it to its template (the gap this test was written on)."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers.planning_tasks import DevelopmentProposePlanTasksHandler
    from squadops.prompts.renderer import RequestTemplateRenderer
    from tests.unit.capabilities.test_propose_plan_tasks import (
        _DEV_PROPOSAL_RESPONSE,
        _make_context,
        _seeded_inputs,
    )

    context = _make_context(_DEV_PROPOSAL_RESPONSE)
    context.ports.request_renderer = RequestTemplateRenderer(
        create_prompt_asset_source("filesystem")
    )
    inputs = {**_seeded_inputs(), "prior_cycle_brief": brief_lines(prior_cycle_brief(_failed()))}

    await DevelopmentProposePlanTasksHandler().handle(context, inputs)

    messages = context.ports.llm.chat_stream_with_usage.call_args.args[0]
    prompt = "\n".join(str(m.content) for m in messages)
    assert "THIS INCREMENT WAS ATTEMPTED BEFORE, AND FAILED" in prompt
    assert "- failed checks: `tests_pass`" in prompt


_SOURCES = {"my_app/main.py": "def main():\n    print('hello')\n"}


def _author_context(sent: list) -> MagicMock:
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.llm.models import ChatMessage
    from squadops.prompts.renderer import RequestTemplateRenderer

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content="```python:a.py\nx = 1\n```\n")

    context = MagicMock()
    context.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=_chat)
    context.ports.llm.default_model = "test-model"
    context.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    context.ports.llm_observability = None
    context.ports.request_renderer = RequestTemplateRenderer(
        create_prompt_asset_source("filesystem")
    )
    context.correlation_context = None
    context.disputed_checks = []
    context.task_id = "task-1"
    return context


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
async def test_every_author_a_bound_cycle_runs_is_shown_the_failed_cycle(
    handler, inputs, monkeypatch
):
    """Wiring, entered at each implementation author's own ``handle()`` on the shipped templates,
    on the path a plan-driven task takes. A repair re-runs the approved plan, so these — not
    framing — are what it shows the brief to. Bugs caught: the brief reaching the dev and not the
    author of the suite that failed, or a template slot no handler fills (#1289's shape)."""
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

    brief = brief_lines(prior_cycle_brief(_failed()))
    await author().handle(_author_context(shown), {**base, "prior_cycle_brief": brief})
    await author().handle(_author_context(plain), base)

    prompt = "\n".join(str(m.content) for m in shown[0])
    assert "THIS INCREMENT WAS ATTEMPTED BEFORE, AND FAILED" in prompt
    assert "- failed checks: `tests_pass`" in prompt
    assert "ATTEMPTED BEFORE" not in "\n".join(str(m.content) for m in plain[0])


def test_an_indicator_asked_with_none_is_shown_as_none_not_dropped():
    """#1445's third state in the brief. Bug caught: ``asked_none`` dropped from the brief, so
    the reader cannot tell "nothing went unverified" from "never asked"."""
    from squadops.cycles.cycle_assessment import IndicatorState

    latest = _failed()
    assert latest.indicator("unverified_by_reason").state is IndicatorState.ASKED_NONE

    assert "- unverified by reason: none" in brief_lines(prior_cycle_brief(latest))
