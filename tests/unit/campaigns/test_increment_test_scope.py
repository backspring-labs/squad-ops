"""#1884 (the owner's rule): a test in an increment asserts only what something accepted requires.

The rule reaches every author of an increment's tests through one asset
(``request.increment_test_scope_appendix``). These tests enter where the live cycle does:
``generate_task_plan`` (what a run's provisioning calls), then each author's real ``handle()`` on
the envelope it produced. The repair's half, which the correction loop builds, is in
``tests/unit/cycles/test_correction_runner.py`` (``TestOwnArtifactLocusRouting``).
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.campaigns.change_request import ChangeKind, content_hash, stored_change_request
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.models import Run
from squadops.cycles.task_plan import generate_task_plan
from squadops.llm.models import ChatMessage
from squadops.prompts.renderer import RequestTemplateRenderer
from tests.unit.cycles.test_increment_evaluation_wiring import (
    _PLAN,
    _REQUEST,
    CANDIDATE,
    PROFILE,
    STORED,
    _cycle,
)

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_RULE = "## What this increment's tests may assert"
#: As ``_freeze_bundles`` pins a promoted criterion (#1938): its statement beside its bundle.
_FROZEN_T1 = {
    "criterion_id": "T1",
    "test_path": "backend/tests/criteria/test_T1.py",
    "bundle_ref": "art_bundle_t1",
    "bundle_address": "sha-t1",
    "statement": "Runs are listed in ascending order of their date",
    "surface": "GET /runs",
}


def _increment_cycle():
    """An increment as the campaign launches one: the ``campaign-increment`` profile's own
    defaults, and the criteria earlier increments froze pinned on its launch block."""
    cycle = _cycle(True)
    block = {**cycle.execution_overrides["campaign_proposal"], "frozen_criteria": [_FROZEN_T1]}
    return dataclasses.replace(
        cycle,
        applied_defaults={
            **dict(load_profile("campaign-increment").defaults),
            "build_profile": "fullstack_fastapi_react",
            "implementation_plan": True,
        },
        execution_overrides={**cycle.execution_overrides, "campaign_proposal": block},
    )


def _refactor() -> str:
    """A refactor: no criteria. #1886's rule rode the criteria appendix, which it never rendered."""
    request = dataclasses.replace(_REQUEST, kind=ChangeKind.REFACTOR, criteria=(), prd_delta=())
    return stored_change_request(dataclasses.replace(request, content_hash=content_hash(request)))


def _qa_context(sent: list):
    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content="no fences", completion_tokens=4)

    ctx = MagicMock()
    ctx.task_id = "task-run_i-m001-qa.test"
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=_chat)
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    ctx.correlation_context = None
    ctx.disputed_checks = []
    return ctx


async def _qa_prompt(envelope, monkeypatch) -> str:
    monkeypatch.setattr(
        "squadops.capabilities.handlers.test_runner.run_generated_tests",
        AsyncMock(return_value=RunTestsResult(executed=True, exit_code=0, stdout="1 passed")),
    )
    sent: list = []
    inputs = {**envelope.inputs, "prd": "Runs API", "artifact_contents": {}}
    await QATestHandler().handle(_qa_context(sent), inputs)
    return sent[0][-1].content


def _implementation(cycle, change_request):
    run = Run("run_i", "cyc_inc", 3, "running", "system", "cfg", workload_type="implementation")
    return generate_task_plan(
        cycle, run, PROFILE, plan=_PLAN, interface_manifest=CANDIDATE, change_request=change_request
    )


async def test_an_increments_qa_test_is_shown_what_its_tests_may_assert(monkeypatch, caplog):
    """Bug caught: the rule and the criteria never reaching the author who writes the suite.
    Today an implementation run's ``qa.test`` is handed nothing of the change request, so the
    2.0 set's T1 tie order and T4 non-mutation were written by an author never told either."""
    [qa] = [e for e in _implementation(_increment_cycle(), STORED) if e.task_type == "qa.test"]

    with caplog.at_level(logging.WARNING):
        prompt = await _qa_prompt(qa, monkeypatch)

    assert _RULE in prompt
    for c in _REQUEST.criteria:
        assert f"- {c.id} (this change): {c.statement}. Observable: {c.observable}" in prompt
    assert (
        "- T1 (frozen by an earlier increment): Runs are listed in ascending order of their date"
        in prompt
    )


async def test_a_qa_test_outside_a_campaign_is_shown_none_of_it(monkeypatch):
    """Bug caught: the rule leaking into every cycle's suite author, where nothing is frozen and
    there is no change request to judge a test against."""
    [qa] = [e for e in _implementation(_cycle(False), None) if e.task_type == "qa.test"]

    assert "increment_test_scope" not in qa.inputs
    assert _RULE not in await _qa_prompt(qa, monkeypatch)


def _framing(cycle, change_request):
    contract = MagicMock()
    contract.criteria_index_lines.return_value = ["- C1"]
    contract.behavioral.probes = ()
    contract.frozen_files = ()
    run = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")
    # As the approval forwards it (#1840): the candidate manifest's contract rides the framing.
    cycle = dataclasses.replace(
        cycle, execution_overrides={**cycle.execution_overrides, "contract_ref": "art_contract"}
    )
    return generate_task_plan(
        cycle,
        run,
        PROFILE,
        contract=contract,
        interface_manifest=CANDIDATE,
        change_request=change_request,
    )


async def test_a_refactor_increments_plan_authors_are_shown_the_rule():
    """Entered at ``generate_task_plan``, then the qa proposer's real ``handle()`` on its own
    envelope's index. Bug caught: #1886's rule rendered only with the criteria appendix, so a
    ``refactor`` increment's plan authors were never told it. The merger receives the same index:
    its sole-author fallback hands its inputs unchanged to ``produce_plan`` (``merge.py:271``),
    whose rendering of the increment surfaces ``test_plan_authoring_service`` holds."""
    from squadops.capabilities.handlers.planning_tasks import QaProposePlanTasksHandler
    from tests.unit.capabilities.test_propose_plan_tasks import (
        _QA_PROPOSAL_RESPONSE,
        _make_context,
        _seeded_inputs,
    )

    plan = _framing(_increment_cycle(), _refactor())
    [qa] = [e for e in plan if e.task_type == "qa.propose_plan_tasks"]
    [merge] = [e for e in plan if e.task_type == "governance.merge_plan"]
    assert merge.inputs["increment_test_scope_index"] == qa.inputs["increment_test_scope_index"]
    assert "increment_criterion_files_index" not in qa.inputs  # a refactor adds no criterion

    context = _make_context(_QA_PROPOSAL_RESPONSE)
    context.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    increment = {k: v for k, v in qa.inputs.items() if k.startswith("increment_")}
    await QaProposePlanTasksHandler().handle(context, {**_seeded_inputs(), **increment})

    messages = context.ports.llm.chat_stream_with_usage.call_args.args[0]
    prompt = "\n".join(str(m.content) for m in messages)
    assert _RULE in prompt
    assert "- T1 (frozen by an earlier increment): Runs are listed" in prompt


def test_a_framing_outside_a_campaign_carries_no_scope():
    plan = _framing(_cycle(False), None)

    assert not any("increment_test_scope_index" in e.inputs for e in plan)


@pytest.mark.parametrize(
    ("pin", "line"),
    [
        (_FROZEN_T1, "- T1 (frozen by an earlier increment): Runs are listed"),
        # A pin from before #1938 stored no statement: named as such, never blank or dropped.
        (
            {k: v for k, v in _FROZEN_T1.items() if k != "statement"},
            "- T1 (frozen by an earlier increment): statement not recorded",
        ),
    ],
)
def test_a_frozen_criterion_is_listed_with_its_statement_or_says_it_has_none(pin, line):
    from squadops.campaigns.increment_tree import increment_test_scope, test_scope_lines

    config = {
        "campaign_proposal": {"baseline_manifest": "x", "frozen_criteria": [pin]},
        "build_profile": "fullstack_fastapi_react",
    }
    scope = increment_test_scope(config, _refactor())

    assert line in test_scope_lines(scope)
    assert scope["criteria"] == []
