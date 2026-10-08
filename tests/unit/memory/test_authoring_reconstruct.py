"""The reconstruction proof (SIP-0110 §0.11; #2105): an envelope's own handler, re-run on its
inputs with the real prompt assets, sends exactly the messages the envelope recorded.

The envelope here is captured the way the live agent captures it, through
``HandlerExecutor.execute`` with the real proposal handler, renderer and assembler.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
from squadops.capabilities.handlers.planning.proposal import StrategyProposeIncrementHandler
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.prompts.assembler import PromptAssembler
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.task_types import TaskType
from tests.unit.capabilities.test_authoring_capture import _dispatched, _executor
from tests.unit.capabilities.test_strategy_propose_increment import (
    _REFERENCE,
    _ctx,
    _fenced,
    _inputs,
)

pytestmark = [pytest.mark.domain_memory]

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "authoring_reconstruct.py"
_spec = importlib.util.spec_from_file_location("authoring_reconstruct", _SCRIPT)
_module = importlib.util.module_from_spec(_spec)
sys.modules["authoring_reconstruct"] = _module
_spec.loader.exec_module(_module)
reconstruct = _module.reconstruct


async def _captured_envelope() -> dict:
    ports = _ctx(_fenced(_REFERENCE)).ports
    result = await _executor(StrategyProposeIncrementHandler(), ports).execute(
        _dispatched(TaskType.STRATEGY_PROPOSE_INCREMENT, _inputs())
    )
    assert result.authoring_envelope is not None
    return result.authoring_envelope


def _tools():
    registry = HandlerRegistry()
    registry.register(StrategyProposeIncrementHandler())
    return (
        registry,
        PromptAssembler(create_prompt_repository("filesystem")),
        RequestTemplateRenderer(create_prompt_asset_source("filesystem")),
    )


async def test_a_captured_proposal_reconstructs_byte_for_byte():
    """Bug caught: an envelope missing an input the prompt depends on, so the replay's baseline
    arm authors from a different prompt than the one the model saw (#2106's validity check)."""
    envelope = await _captured_envelope()

    verdict = await reconstruct(envelope, *_tools())

    assert verdict["byte_exact"] is True, verdict
    assert verdict["chat_kwargs_equal"] is True
    assert verdict["seam"] == "proposal_writing" and verdict["envelope_bytes"] > 0


async def test_an_envelope_whose_inputs_changed_is_caught_at_the_first_difference():
    """Bug caught: a proof that reports exact when the inputs no longer produce the prompt, which
    would certify a replay that changed more than the intervention."""
    envelope = copy.deepcopy(await _captured_envelope())
    envelope["inputs"]["prd"] = "## Expansion Tier 1\n1. Something else entirely"

    verdict = await reconstruct(envelope, *_tools())

    assert verdict["byte_exact"] is False
    assert verdict["first_difference"]["field"] == "content"
    assert "Something else entirely" in verdict["first_difference"]["got"]


async def test_an_envelope_with_an_input_it_could_not_carry_is_not_replayable():
    """Bug caught: a re-run that silently authors without a port or object the original had."""
    envelope = copy.deepcopy(await _captured_envelope())
    envelope["inputs_not_captured"] = ["artifact_vault"]

    verdict = await reconstruct(envelope, *_tools())

    assert verdict["byte_exact"] is False
    assert verdict["reason"] == "inputs not captured" and verdict["paths"] == ["artifact_vault"]


async def test_a_build_authored_with_lessons_records_them_apart_and_reconstructs_byte_for_byte():
    """§0.11 with memory on. Entered at ``HandlerExecutor.execute`` with the real build author,
    renderer and assembler. Bugs caught: the lessons left among the task's own inputs, so a
    replay's no-memory arm still carries them; or the memory block not restored on the re-run, so
    an envelope that was supplied lessons can never be reproduced."""
    from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
    from squadops.memory.recall import LESSONS_INPUT
    from tests.unit.campaigns.test_prior_cycle import _SOURCES, _author_context
    from tests.unit.capabilities.test_authoring_capture import _dispatched, _executor

    lessons = {
        "snapshot": "snp_0123456789abcdef",
        "lessons": [{"revision_id": "pat_a@1", "text": "Declare the field the client reads."}],
    }
    own = {
        "prd": "the PRD",
        "artifact_contents": _SOURCES,
        "subtask_focus": "the limit",
        "expected_artifacts": ["a.py"],
    }
    _, prompt_service, renderer = _tools()
    ports = _author_context([]).ports
    ports.prompt_service, ports.request_renderer = prompt_service, renderer

    result = await _executor(DevelopmentDevelopHandler(), ports).execute(
        _dispatched(TaskType.DEVELOPMENT_DEVELOP, {**own, LESSONS_INPUT: lessons})
    )
    envelope = result.authoring_envelope
    registry = HandlerRegistry()
    registry.register(DevelopmentDevelopHandler())

    verdict = await reconstruct(envelope, registry, prompt_service, renderer)

    assert envelope["memory"] == {
        "snapshot": lessons["snapshot"],
        "intervention": lessons["lessons"],
    }
    assert LESSONS_INPUT not in envelope["inputs"]
    assert "Declare the field the client reads." in envelope["messages"][-1]["content"]
    assert verdict["byte_exact"] is True, verdict


_PROPOSERS = {
    TaskType.DEVELOPMENT_PROPOSE_PLAN_TASKS: "_DEV_PROPOSAL_RESPONSE",
    TaskType.QA_PROPOSE_PLAN_TASKS: "_QA_PROPOSAL_RESPONSE",
    TaskType.STRATEGY_PROPOSE_PLAN_GUIDANCE: "_STRATEGY_GUIDANCE_RESPONSE",
}


@pytest.mark.parametrize("task_type", list(_PROPOSERS))
async def test_a_plan_proposal_reconstructs_byte_for_byte(task_type):
    """#2141, entered at ``HandlerExecutor.execute`` with the real proposer, renderer and assembler.
    Bug caught: a proposer that mints a random id into its prompt, so a re-run on the captured
    inputs renders another id and the envelope is never a replayable case. The live proof's
    framings never ran these three, so slice 1 shipped with them unreconstructable."""
    from squadops.capabilities.handlers.planning_tasks import (
        DevelopmentProposePlanTasksHandler,
        QaProposePlanTasksHandler,
        StrategyProposePlanGuidanceHandler,
    )
    from tests.unit.capabilities import test_propose_plan_tasks as fixtures

    handler = {
        TaskType.DEVELOPMENT_PROPOSE_PLAN_TASKS: DevelopmentProposePlanTasksHandler,
        TaskType.QA_PROPOSE_PLAN_TASKS: QaProposePlanTasksHandler,
        TaskType.STRATEGY_PROPOSE_PLAN_GUIDANCE: StrategyProposePlanGuidanceHandler,
    }[task_type]
    reply = getattr(fixtures, _PROPOSERS[task_type])
    result = await _executor(handler(), _ctx(reply).ports).execute(
        _dispatched(task_type, fixtures._seeded_inputs())
    )
    registry = HandlerRegistry()
    registry.register(handler())
    _, prompt_service, renderer = _tools()

    verdict = await reconstruct(result.authoring_envelope, registry, prompt_service, renderer)

    assert verdict["byte_exact"] is True, verdict


def test_the_proposers_answering_one_brief_get_distinct_ids():
    """The id is derived, not drawn, so it must still tell the run's proposals apart: the merge
    records them by id. Bug caught: a derivation from the brief alone, giving the development and
    qa proposals of one run the same id."""
    from squadops.capabilities.handlers.planning_tasks import (
        DevelopmentProposePlanTasksHandler,
        QaProposePlanTasksHandler,
        StrategyProposePlanGuidanceHandler,
    )
    from tests.unit.capabilities.test_propose_plan_tasks import _seeded_inputs

    inputs = _seeded_inputs()
    prior = inputs["prior_outputs"]
    dev = DevelopmentProposePlanTasksHandler()._build_render_variables("PRD", prior, inputs)
    qa = QaProposePlanTasksHandler()._build_render_variables("PRD", prior, inputs)
    strat = StrategyProposePlanGuidanceHandler()._build_render_variables("PRD", prior, inputs)
    again = DevelopmentProposePlanTasksHandler()._build_render_variables("PRD", prior, inputs)

    assert dev["proposal_id"] == again["proposal_id"]
    assert len({dev["proposal_id"], qa["proposal_id"], strat["proposal_id"]}) == 3
    assert strat["guidance_id"].startswith("guid-") and dev["proposal_id"].startswith("prop-")
