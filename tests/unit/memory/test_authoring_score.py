"""The answer scorer (SIP-0111 §4's G1, #2199), entered at ``score`` with a proposal envelope captured as
the live agent captures it, the real handler and prompt assets, and a recorded answer.

What bugs would these catch? A handler's second call, its retry with the failure's fact, taken as a pass;
a handler that raised on the answer counted as anything but a failure; a record that cannot say whether
today's handler asks the question the answer was written for.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.capabilities.test_strategy_propose_increment import _REFERENCE, _fenced
from tests.unit.memory.test_authoring_reconstruct import _captured_envelope, _tools

pytestmark = [pytest.mark.domain_memory]

_DEV = Path(__file__).resolve().parents[3] / "scripts" / "dev"
sys.path.insert(0, str(_DEV))
_spec = importlib.util.spec_from_file_location("authoring_score", _DEV / "authoring_score.py")
_module = importlib.util.module_from_spec(_spec)
sys.modules["authoring_score"] = _module
_spec.loader.exec_module(_module)


def _answer(content: str, completion_tokens: int = 900) -> dict:
    return {
        "key": "arm|round1|e",
        "content": content,
        "reasoning_text": None,
        "prompt_tokens": 4000,
        "completion_tokens": completion_tokens,
    }


async def test_a_valid_answer_passes_on_the_question_it_was_written_for():
    envelope = await _captured_envelope()

    record = await _module.score(envelope, _answer(_fenced(_REFERENCE)), *_tools())

    assert record["verdict"] == "pass", record
    assert record["first_call_is_the_capture"] is True
    assert record["artifacts"] == ["change_request.yaml"]


async def test_an_answer_the_handler_asks_again_for_is_scored_with_the_reason():
    """The proposal handler re-asks with the parse error instead of failing; the overnight run's Ollama
    answer did exactly this, and only the stop at the second call shows it."""
    envelope = await _captured_envelope()

    record = await _module.score(envelope, _answer(_fenced("title: [unclosed")), *_tools())

    assert record["verdict"] == "asked_again", record
    assert "not valid YAML" in record["asked"]


@pytest.mark.parametrize("termination, verdict", [("stop", "pass"), (None, "asked_again")])
async def test_an_answer_that_finished_past_the_envelopes_cap_is_read_by_how_it_ended(
    termination, verdict
):
    """#2253's raised-cap arm: an answer that finished past the envelope's own cap, its last fence left
    open as #431 allows. Handed TensorFold's termination, as production's adapter hands it on, the
    handler keeps the answer, as it would at the raised cap. Without one, the token count against the
    envelope's cap reads it as cut, and every such answer would be scored as asked again."""
    envelope = copy.deepcopy(await _captured_envelope())
    # The QA role's profile budget, as every #2253 envelope carries it.
    envelope["inputs"]["agent_config_overrides"] = {"max_completion_tokens": 12288}
    open_fence = _fenced(_REFERENCE).rstrip().removesuffix("```")
    answer = _answer(open_fence, completion_tokens=14000) | {"termination": termination}

    record = await _module.score(envelope, answer, *_tools())

    assert record["verdict"] == verdict, record


async def test_a_handler_that_raises_on_the_answer_is_never_a_pass():
    class _Raises:
        async def handle(self, context, inputs):
            await context.ports.llm.chat_stream_with_usage([])
            raise ValueError("bad shape")

    envelope = await _captured_envelope()
    _, prompt_service, renderer = _tools()
    registry = SimpleNamespace(get=lambda task_type: _Raises())

    record = await _module.score(envelope, _answer("x"), registry, prompt_service, renderer)

    assert (record["verdict"], record["error"]) == ("raised", "ValueError: bad shape")
    assert record["first_call_is_the_capture"] is False
