"""TensorFold's own contracts, beyond the conformance suite (SIP-0111 §5.3–§5.5, #2200).

What bug would these catch?
- A stream that failed read as a success: an ``error`` frame followed by ``[DONE]`` (which TensorFold
  sends), a stream cut before its finish frame or usage, or a frame that is not JSON skipped as
  vLLM skips one. Each would hand a half answer to a handler as whole.
- A request abandoned by a deadline or a cancellation still running when the next one is sent, so
  the retry queues behind it. Or an unconfirmed release read as quiet.
- A prompt past the served window retried as an ordinary failure, or the registry promising a
  larger window than the server serves.
- A residency read as idle from anything but the authenticated sources, an alias read as a second
  model, or the frozen recipe and the adapter's table drifting apart.
- A call that sets no seed left to the server, which keys it to the prompt, so a repeated prompt
  repeats its answer (#2281). Or the seed drawn and never named, so the call cannot be replayed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest
import yaml

import adapters.llm.tensorfold as tensorfold
from adapters.llm.tensorfold import (
    RECIPES,
    Residency,
    TensorFoldAdapter,
    TensorFoldStreamError,
)
from squadops.llm.exceptions import (
    LLMConnectionError,
    LLMContextOverflowError,
    LLMModelNotFoundError,
    LLMTimeoutError,
)
from squadops.llm.model_registry import get_model_spec
from squadops.llm.models import ChatMessage, LLMRequest
from tests.unit.llm.conformance import (
    TENSORFOLD_KEY,
    TENSORFOLD_MODELS,
    TENSORFOLD_SERVED,
    _tf_frames,
    raises,
    wire,
)

_RECIPES_DIR = Path(__file__).resolve().parents[3] / "infra" / "tensorfold" / "recipes"
_MESSAGES = [ChatMessage(role="user", content="write the routes")]
_GENERATION = "POST /v1/chat/completions"
_OVERFLOW_MESSAGE = (
    "This server's maximum context length is 65536 tokens: the rendered prompt has 70112 tokens "
    "and leaves no room for a reply in the server's 65536-token context window, which exceeds "
    "the context window; shorten the prompt"
)


@pytest.fixture(autouse=True)
def _fast_release_polls(monkeypatch):
    monkeypatch.setattr(tensorfold, "_RELEASE_POLL_SECONDS", 0.01)


class _Frames(httpx.AsyncByteStream):
    """A stream that sends ``frames`` one at a time; ``forever`` repeats the last with a pause."""

    def __init__(self, frames: list[bytes], *, forever: bool = False, pause: float = 0.0):
        self._frames, self._forever, self._pause = frames, forever, pause

    async def __aiter__(self):
        for frame in self._frames:
            await asyncio.sleep(self._pause)
            yield frame
        while self._forever:
            await asyncio.sleep(self._pause or 0.01)
            yield self._frames[-1]


def _data(frame: dict | str) -> bytes:
    body = frame if isinstance(frame, str) else json.dumps(frame)
    return f"data: {body}\n\n".encode()


class _Server:
    """One TensorFold server for one test: what each generation answers, in order, what its
    gauges read on each scrape (the last repeats), and every request it received, in order."""

    def __init__(self, *answers, in_flight=(0,), window: int = 65536, models=TENSORFOLD_MODELS):
        self.answers = list(answers)
        self.in_flight = list(in_flight)
        self.window = window
        self.models = list(models)
        self.log: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.log.append(f"{request.method} {request.url.path}")
        if request.headers.get("Authorization") != f"Bearer {TENSORFOLD_KEY}":
            return httpx.Response(
                401,
                json={
                    "error": {"message": "A valid API key is required", "code": "invalid_api_key"}
                },
            )
        if request.url.path == "/metrics":
            n = self.in_flight.pop(0) if len(self.in_flight) > 1 else self.in_flight[0]
            return httpx.Response(
                200, text=f"tensorfold:requests_running {n}\ntensorfold:requests_waiting 0\n"
            )
        if request.url.path == "/tokenize":
            return httpx.Response(
                200, json={"count": 1, "tokens": [87], "max_model_len": self.window}
            )
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": m} for m in self.models]})
        answer = self.answers.pop(0) if self.answers else _complete()
        return answer if isinstance(answer, httpx.Response) else httpx.Response(200, stream=answer)

    def generations(self) -> int:
        return self.log.count(_GENERATION)


def _complete() -> _Frames:
    return _Frames([_data(f) for f in _tf_frames()] + [_data("[DONE]")])


def _adapter(**kwargs) -> TensorFoldAdapter:
    return TensorFoldAdapter(
        base_url="http://tensorfold:8080",
        default_model=TENSORFOLD_SERVED,
        timeout_seconds=kwargs.pop("timeout_seconds", 5.0),
        api_key=kwargs.pop("api_key", TENSORFOLD_KEY),
        **kwargs,
    )


_CONTENT = {"choices": [{"index": 0, "delta": {"content": "def create(): "}}]}
_FINISH = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
_USAGE = {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}}


@pytest.mark.parametrize(
    ("frames", "said"),
    [
        (
            [_CONTENT, {"error": {"message": "CUDA error", "type": "server_error"}}, "[DONE]"],
            "server_error: CUDA error",
        ),
        ([_CONTENT, _USAGE, "[DONE]"], "usage frame arrived before the finish frame"),
        ([_CONTENT, _FINISH, "[DONE]"], "no usage frame"),
        ([_CONTENT, "[DONE]"], "usage frame arrived before|no finish frame"),
        ([_CONTENT, "{not json"], "not JSON"),
        ([_CONTENT, _FINISH], "ended before \\[DONE\\]"),
    ],
    ids=[
        "an error frame then [DONE]",
        "a usage-only final event",
        "no usage",
        "no finish frame",
        "a malformed frame",
        "cut before [DONE]",
    ],
)
async def test_a_stream_that_did_not_end_whole_raises_and_the_next_request_is_healthy(frames, said):
    """§5.4: never a partial success. What arrived is kept on the error as evidence only, and the
    next request runs once the server shows the broken one gone."""
    server = _Server(_Frames([_data(f) for f in frames]), in_flight=(0, 1, 0))
    adapter = _adapter()
    with wire(server):
        with pytest.raises(TensorFoldStreamError, match=said) as raised:
            await adapter.chat_stream_with_usage(_MESSAGES)
        message = await adapter.chat_stream_with_usage(_MESSAGES)

    assert raised.value.partial["content"] == "def create(): "
    assert message.content == "the assembled answer"
    sent = server.log.index(_GENERATION, server.log.index(_GENERATION) + 1)
    assert server.log[sent - 2 : sent] == ["GET /metrics", "GET /metrics"], (
        "the next request waited for the broken one's release"
    )


async def test_output_past_the_deadline_is_a_timeout_and_the_next_request_waits_for_its_release():
    """§5.4: a stream that keeps emitting cannot outlive the call's deadline."""
    endless = _Frames([_data(_CONTENT)], forever=True, pause=0.01)
    server = _Server(endless, in_flight=(0, 1, 1, 0))
    adapter = _adapter(timeout_seconds=0.2)
    with wire(server):
        with pytest.raises(LLMTimeoutError, match="deadline"):
            await adapter.chat_stream_with_usage(_MESSAGES)
        await adapter.chat_stream_with_usage(_MESSAGES)

    second = server.log.index(_GENERATION, server.log.index(_GENERATION) + 1)
    assert server.log[second - 3 : second] == ["GET /metrics"] * 3


async def test_a_release_never_confirmed_is_unknown_and_nothing_more_is_sent():
    """Unconfirmed is unknown, never quiet: the call raises before anything is sent, and the
    one after it waits again."""
    endless = _Frames([_data(_CONTENT)], forever=True, pause=0.01)
    server = _Server(endless, in_flight=(0, 1))
    adapter = _adapter(timeout_seconds=0.2, release_seconds=0.1)
    with wire(server):
        with pytest.raises(LLMTimeoutError):
            await adapter.chat_stream_with_usage(_MESSAGES)
        for _ in range(2):
            with pytest.raises(LLMConnectionError, match="state is unknown"):
                await adapter.chat_stream_with_usage(_MESSAGES)

    assert server.generations() == 1


async def test_a_call_cancelled_while_reasoning_is_confirmed_released_before_the_next():
    """The caller's cancellation closes the stream, which TensorFold hears as a disconnect; the
    adapter cannot wait inside a cancelled task, so the next call confirms it first."""
    reasoning = {"choices": [{"index": 0, "delta": {"reasoning_content": "thinking "}}]}
    server = _Server(_Frames([_data(reasoning)], forever=True, pause=0.01), in_flight=(0, 1, 0))
    adapter = _adapter()
    with wire(server):
        call = asyncio.create_task(adapter.chat_stream_with_usage(_MESSAGES))
        await asyncio.sleep(0.1)
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        message = await adapter.chat_stream_with_usage(_MESSAGES)

    assert message.reasoning_text == "thought through, in reasoning_content"
    second = server.log.index(_GENERATION, server.log.index(_GENERATION) + 1)
    assert server.log[second - 2 : second] == ["GET /metrics", "GET /metrics"]


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(
            400,
            json={
                "error": {
                    "message": _OVERFLOW_MESSAGE,
                    "type": "invalid_request_error",
                    "param": "messages",
                    "code": "context_length_exceeded",
                }
            },
        ),
        _Frames(
            [
                _data({"error": {"message": _OVERFLOW_MESSAGE, "code": "context_length_exceeded"}}),
                _data("[DONE]"),
            ]
        ),
    ],
    ids=["refused before the stream", "an error frame in the stream"],
)
async def test_a_prompt_past_the_window_is_a_context_overflow_with_its_numbers(answer):
    """§5.2: typed, so the task is held rather than retried with the same prompt."""
    with wire(_Server(answer)), pytest.raises(LLMContextOverflowError) as raised:
        await _adapter().chat_stream_with_usage(_MESSAGES)

    assert (raised.value.served_window, raised.value.prompt_tokens) == (65536, 70112)


async def test_a_registry_window_larger_than_the_served_one_refuses_every_generation():
    """§5.3: the prompt-size guard reads the registry, so a larger registry window lets through
    prompts the server refuses. Read once; a server that agrees is not asked again."""
    narrow = _Server(window=32768)
    with wire(narrow), pytest.raises(LLMConnectionError, match="65536-token window.*serves 32768"):
        await _adapter().chat_stream_with_usage(_MESSAGES)
    assert narrow.generations() == 0

    agreeing = _Server()
    adapter = _adapter()
    with wire(agreeing):
        await adapter.chat_stream_with_usage(_MESSAGES)
        await adapter.chat_stream_with_usage(_MESSAGES)
    assert agreeing.log.count("POST /tokenize") == 1


async def test_an_id_without_a_frozen_recipe_is_refused_before_anything_is_sent():
    server = _Server()
    with wire(server), pytest.raises(LLMModelNotFoundError, match="no frozen TensorFold recipe"):
        await _adapter().chat_stream_with_usage(_MESSAGES, model="qwen3.8:27b")
    assert server.log == []


@pytest.mark.parametrize(
    ("server", "key", "state"),
    [
        (_Server(in_flight=(0,)), TENSORFOLD_KEY, Residency.IDLE),
        (_Server(in_flight=(1,)), TENSORFOLD_KEY, Residency.BUSY),
        (_Server(), "a-wrong-key", Residency.UNAUTHORIZED),
        (raises(httpx.ConnectError("refused")), TENSORFOLD_KEY, Residency.UNREACHABLE),
        (_Server(models=["some-other-model"]), TENSORFOLD_KEY, Residency.UNKNOWN),
        (
            lambda r: httpx.Response(200, text="") if r.url.path == "/metrics" else _Server()(r),
            TENSORFOLD_KEY,
            Residency.UNKNOWN,
        ),
    ],
    ids=["idle", "busy", "unauthorized", "unreachable", "a foreign model", "no gauges"],
)
async def test_residency_is_read_only_from_authenticated_sources(server, key, state):
    """§5.5: only ``idle`` is safe to launch on. A bad key fails visibly, as unauthorized."""
    adapter = _adapter(api_key=key)
    with wire(server):
        health = await adapter.health()

    assert health["state"] == state
    assert health["healthy"] is (state in (Residency.IDLE, Residency.BUSY))


async def test_an_alias_is_the_same_resident_model():
    """§5.5: ``/v1/models`` lists the served id and its aliases; they are one model, so the
    quiet-box check sees no foreign one."""
    with wire(_Server()):
        loaded = await _adapter().list_loaded_models()
    assert [m.name for m in loaded] == [TENSORFOLD_SERVED]


async def test_a_wrong_key_names_the_setting_that_holds_it():
    with wire(_Server()), pytest.raises(LLMConnectionError, match="SQUADOPS__LLM__API_KEY"):
        await _adapter(api_key="a-wrong-key").chat_stream_with_usage(_MESSAGES)


def test_each_frozen_recipe_is_the_adapters_table_and_the_registrys_window():
    """The recipe is what the gates measured (§5.7). Bug caught: a recipe re-frozen with new
    sampling or a new window while the adapter keeps sending the old, so production stops
    matching what passed, with nothing failing."""
    frozen = [
        doc
        for path in sorted(_RECIPES_DIR.glob("*.yaml"))
        if str((doc := yaml.safe_load(path.read_text())).get("status", "")).startswith("frozen")
    ]
    assert {doc["served_id"] for doc in frozen} == set(RECIPES)
    for doc in frozen:
        recipe = RECIPES[doc["served_id"]]
        assert recipe.parity_effort == doc["parity_effort"]
        assert {
            "temperature": recipe.temperature,
            "top_p": recipe.top_p,
            "top_k": recipe.top_k,
            "min_p": recipe.min_p,
        } == doc["sampling"]
        assert get_model_spec(doc["served_id"]).context_window == doc["context"]
        # #2561: the deploy record's digest for the served id is the checkpoint the recipe pins.
        checkpoint = doc["checkpoint"]
        assert recipe.weights == f"hf:{checkpoint['repo']}@{checkpoint['revision']}"


@pytest.mark.parametrize(
    ("level", "fields"),
    [
        (None, {"reasoning_effort": "medium"}),
        ("none", {"chat_template_kwargs": {"enable_thinking": False}}),
        ("low", {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_effort": "medium"}),
        ("high", {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_effort": "medium"}),
    ],
    ids=["no level", "none", "low", "high"],
)
async def test_every_level_reaches_tensorfold_as_ollamas_prompt(level, fields):
    """§9c: thinking on or off, with the recipe's parity effort, never the port's level. Bug
    caught: a level (or no level, which the template reads as ``xhigh``) sent through, so the
    prompt carries an effort line Ollama's never had and production stops being what G0 measured."""
    sent: dict = {}
    server = _Server()

    def capture(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/chat/completions":
            sent.update(json.loads(request.content))
        return server(request)

    with wire(capture):
        await _adapter().chat_stream_with_usage(_MESSAGES, reasoning=level)

    assert {k: sent[k] for k in ("chat_template_kwargs", "reasoning_effort") if k in sent} == fields


async def _call(adapter: TensorFoldAdapter, method: str, seed: int | None) -> None:
    if method == "generate":
        await adapter.generate(LLMRequest(prompt="write the routes", seed=seed))
    elif method == "chat_stream":
        async for _ in adapter.chat_stream(_MESSAGES, seed=seed):
            pass
    else:
        await getattr(adapter, method)(_MESSAGES, seed=seed)


@pytest.mark.parametrize("method", ["chat_stream_with_usage", "chat", "generate", "chat_stream"])
async def test_every_call_sends_a_seed_fresh_unless_the_call_sets_one(method, caplog):
    """§9j, #2281. Entered at ``chat_stream_with_usage``, the call every handler makes, without a
    seed, as no handler sets one. Bug caught: the seed left to TensorFold, which keys it to the
    prompt, so G3's two rolls on a stack planned identically; a replay's seed replaced, or a seed
    of 0 read as none; or the drawn seed named nowhere, so the call cannot be replayed."""
    sent: list[int] = []
    server = _Server()

    def capture(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/chat/completions":
            sent.append(json.loads(request.content)["seed"])
        return server(request)

    adapter = _adapter()
    with wire(capture), caplog.at_level(logging.INFO, logger=tensorfold.__name__):
        for seed in (None, None, 0, 1001):
            await _call(adapter, method, seed)

    fresh, again, zero, replay = sent
    assert fresh != again
    assert all(0 <= s < 2**63 for s in (fresh, again))
    assert (zero, replay) == (0, 1001)
    lines = [r.getMessage() for r in caplog.records]
    named = [line.rsplit("seed=", 1)[1] for line in lines if "seed=" in line]
    assert named == [str(s) for s in sent]
