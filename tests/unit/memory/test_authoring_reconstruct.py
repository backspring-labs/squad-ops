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
