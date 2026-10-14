"""How a generation ended reaches the port in its own vocabulary (SIP-0111 §5.2).

What bug would these catch? A provider's ``length`` lost on the way to the port, so the cap is
read from a token count that may be missing; a provider-specific reason (``tool_calls``) passed
through as if it were the port's; and Ollama, which reports no termination through this port,
starting to report one and changing which rule decides its cap.
"""

from __future__ import annotations

import json

import httpx
import pytest

from adapters.llm.atlas import AtlasAdapter
from adapters.llm.ollama import OllamaAdapter
from adapters.llm.vllm import VLLMAdapter
from squadops.llm.models import ChatMessage, LLMRequest, Termination
from tests.unit.llm.conformance import ollama_ok, wire

_MESSAGES = [ChatMessage(role="user", content="hi")]


def _openai(finish_reason: str):
    """An OpenAI-shaped server whose one generation ended with ``finish_reason``."""

    def handler(request: httpx.Request) -> httpx.Response:
        usage = {"prompt_tokens": 5, "completion_tokens": 12, "total_tokens": 17}
        if json.loads(request.content).get("stream"):
            frames = [
                {"choices": [{"index": 0, "delta": {"content": "an answer"}}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]},
                {"choices": [], "usage": usage},
            ]
            body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n"
            return httpx.Response(200, text=body)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "an answer"},
                        "finish_reason": finish_reason,
                    }
                ],
                "usage": usage,
            },
        )

    return handler


async def _ended(adapter, via: str):
    if via == "generate":
        return (await adapter.generate(LLMRequest(prompt="hi"))).termination
    if via == "chat":
        return (await adapter.chat(_MESSAGES)).termination
    return (await adapter.chat_stream_with_usage(_MESSAGES)).termination


@pytest.mark.parametrize("adapter_class", [VLLMAdapter, AtlasAdapter], ids=["vllm", "atlas"])
@pytest.mark.parametrize("via", ["generate", "chat", "chat_stream_with_usage"])
@pytest.mark.parametrize(
    ("finish_reason", "termination"),
    [("stop", Termination.STOP), ("length", Termination.LENGTH), ("tool_calls", None)],
)
async def test_an_openai_finish_reason_reaches_the_port_as_its_termination(
    adapter_class, via, finish_reason, termination
):
    adapter = adapter_class(base_url="http://server", default_model="m")
    with wire(_openai(finish_reason)):
        assert await _ended(adapter, via) == termination


@pytest.mark.parametrize("via", ["generate", "chat", "chat_stream_with_usage"])
async def test_ollama_reports_no_termination_so_its_token_count_decides_the_cap(via):
    adapter = OllamaAdapter(base_url="http://server", default_model="qwen2.5:7b")
    with wire(ollama_ok):
        assert await _ended(adapter, via) is None
