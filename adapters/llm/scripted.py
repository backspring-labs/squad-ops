"""The scripted LLM provider, and the port that serves it beside the deploy's engine (#2495).

**One seam.** Both classes are ``LLMPort``s. A deploy's composition roots wrap their engine in
:class:`ScriptedModelRouter` (``factory.with_scripted_model``): a call naming
:data:`~squadops.llm.script.SCRIPTED_MODEL` is answered by :class:`ScriptedLLMAdapter`, and every
other call goes to the engine exactly as before. A squad profile whose agents name ``scripted``
(``machinery``) therefore runs dispatch, emission, correction and acceptance on their normal paths,
and no handler, executor or acceptance code knows its answers were recorded. Every other profile
keeps the engine, on the same deploy.

**No fallback.** A scripted call is answered from its cycle's script or it fails, naming what it
looked for (:mod:`squadops.llm.script`'s errors). It is never sent to the engine.

**The key** is the task the call serves, read from the agent's
:func:`~squadops.llm.call_scope.current_llm_call_scope`, never from the prompt:
``(task_type, occurrence, call)``, with the occurrence and the call counted per cycle as the calls
arrive (see :mod:`squadops.llm.script`). The counts, and the script each cycle named, are kept
behind :class:`~squadops.ports.llm.script_positions.ScriptPositionsPort` (Redis on a deploy), so
an agent that restarts mid-cycle goes on from where its cycle was (#3005). Before, they lived in
this process, and a restarted agent answered a later task from an earlier task's entry.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from squadops.llm.call_scope import current_llm_call_scope
from squadops.llm.models import ChatMessage, LLMRequest, LLMResponse, ModelInfo
from squadops.llm.script import (
    LLM_SCRIPT_KEY,
    SCRIPTED_ENGINE,
    SCRIPTED_MODEL,
    AnswerKey,
    LLMScriptError,
    ScriptedAnswer,
    ScriptLibrary,
    ScriptReference,
    UnscopedScriptedCallError,
)
from squadops.ports.llm.provider import LLMCapability, LLMPort
from squadops.ports.llm.script_positions import ScriptPositionsPort


class ScriptedLLMAdapter(LLMPort):
    """Answers each call from the cycle's recorded script."""

    def __init__(
        self,
        library: ScriptLibrary,
        positions: ScriptPositionsPort,
        *,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self._library = library
        #: Each cycle's occurrences, calls and named script, kept outside this process (#3005).
        #: A step whose envelope carries no resolved config (a pulse-check repair) is answered
        #: from the script an earlier task of its cycle named; with none bound, it fails.
        self._positions = positions
        self._sleep = sleep

    @property
    def engine(self) -> str:
        return SCRIPTED_ENGINE

    @property
    def default_model(self) -> str:
        return SCRIPTED_MODEL

    @property
    def library(self) -> ScriptLibrary:
        return self._library

    def capabilities(self) -> dict[str, bool]:
        # Only the listing is real. No seed, no budget, no reasoning dial: an answer is recorded,
        # so a control that would change a generation has nothing to change, and is refused.
        return {**super().capabilities(), LLMCapability.MODEL_LISTING: True}

    async def _answer(self, model: str | None) -> ScriptedAnswer:
        if model not in (None, SCRIPTED_MODEL):
            raise ValueError(
                f"the scripted provider answers only {SCRIPTED_MODEL!r}, not {model!r}"
            )
        scope = current_llm_call_scope()
        if scope is None or not scope.task_type or not scope.task_id:
            raise UnscopedScriptedCallError(
                f"a call to {SCRIPTED_MODEL!r} outside any task: an answer is keyed by the task it "
                "serves, so there is nothing to look it up by"
            )
        bound = await self._positions.bind_script(scope.cycle_id, scope.llm_script)
        if bound is None:
            raise LLMScriptError(
                f"task {scope.task_type} ({scope.task_id}) of cycle {scope.cycle_id} runs on "
                f"{SCRIPTED_MODEL!r} but its cycle names no script: set "
                f"{LLM_SCRIPT_KEY}=<name>@<version>"
            )
        if scope.llm_script is not None and bound != scope.llm_script:
            raise LLMScriptError(
                f"cycle {scope.cycle_id} named script {bound} and now {scope.llm_script}; "
                "a cycle has one"
            )
        script = self._library.resolve(ScriptReference.parse(bound))

        occurrence, call = await self._positions.next_call(
            scope.cycle_id, scope.task_type, scope.task_id
        )
        key = AnswerKey(scope.task_type, occurrence, call)

        answer = script.answer_for(key)
        if script.replay_latency and answer.latency_seconds:
            await self._sleep(answer.latency_seconds)
        return answer

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> ChatMessage:
        self.refuse_undeclared_controls(seed=seed, thinking_budget=thinking_budget)
        answer = await self._answer(model)
        return ChatMessage(
            role="assistant",
            content=answer.content,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
            total_tokens=_total(answer),
            tokens_per_second=_rate(answer),
            reasoning_tokens=answer.reasoning_tokens,
            reasoning_text=answer.reasoning_text,
            termination=answer.termination,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> AsyncIterator[str]:
        self.refuse_undeclared_controls(seed=seed, thinking_budget=thinking_budget)
        answer = await self._answer(model)
        yield answer.content

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.refuse_undeclared_controls(seed=request.seed, thinking_budget=request.thinking_budget)
        answer = await self._answer(request.model)
        return LLMResponse(
            text=answer.content,
            model=SCRIPTED_MODEL,
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
            total_tokens=_total(answer),
            tokens_per_second=_rate(answer),
            reasoning_tokens=answer.reasoning_tokens,
            reasoning_text=answer.reasoning_text,
            termination=answer.termination,
        )

    def list_models(self) -> list[str]:
        return [SCRIPTED_MODEL]

    async def refresh_models(self) -> list[str]:
        return [SCRIPTED_MODEL]

    async def list_available_models(self) -> list[ModelInfo]:
        return [ModelInfo(name=SCRIPTED_MODEL, digest=self._library.digest())]

    async def health(self) -> dict[str, Any]:
        return {"healthy": True, "engine": SCRIPTED_ENGINE, "scripts": self._library.names()}


def _total(answer: ScriptedAnswer) -> int | None:
    if answer.prompt_tokens is None or answer.completion_tokens is None:
        return None
    return answer.prompt_tokens + answer.completion_tokens


def _rate(answer: ScriptedAnswer) -> float | None:
    """The recorded decode rate, when the script records both the tokens and the latency."""
    if not answer.completion_tokens or not answer.latency_seconds:
        return None
    return answer.completion_tokens / answer.latency_seconds


class ScriptedModelRouter(LLMPort):
    """The deploy's LLM port: :data:`SCRIPTED_MODEL` to the script, every other model to the engine.

    Everything that is not a call (health, capabilities, the loaded models, model management) is
    the engine's: the scripted provider holds nothing in memory and has no weights to manage.
    """

    def __init__(self, engine: LLMPort, scripted: ScriptedLLMAdapter) -> None:
        self._engine = engine
        self._scripted = scripted

    @property
    def engine(self) -> str:
        return self._engine.engine

    @property
    def default_model(self) -> str:
        return self._engine.default_model

    def engine_for(self, model: str | None) -> str:
        if model == SCRIPTED_MODEL:
            return self._scripted.engine
        return self._engine.engine_for(model)

    def _route(self, model: str | None) -> LLMPort:
        return self._scripted if model == SCRIPTED_MODEL else self._engine

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return await self._route(request.model).generate(request)

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> ChatMessage:
        return await self._route(model).chat(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout_seconds,
            reasoning=reasoning,
            seed=seed,
            thinking_budget=thinking_budget,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> AsyncIterator[str]:
        async for chunk in self._route(model).chat_stream(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout_seconds,
            reasoning=reasoning,
            seed=seed,
            thinking_budget=thinking_budget,
        ):
            yield chunk

    async def chat_stream_with_usage(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        timeout_seconds: float | None = None,
        reasoning: str | None = None,
        seed: int | None = None,
        thinking_budget: int | None = None,
    ) -> ChatMessage:
        return await self._route(model).chat_stream_with_usage(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout_seconds=timeout_seconds,
            reasoning=reasoning,
            seed=seed,
            thinking_budget=thinking_budget,
        )

    def list_models(self) -> list[str]:
        return [*self._engine.list_models(), SCRIPTED_MODEL]

    async def refresh_models(self) -> list[str]:
        return [*(await self._engine.refresh_models()), SCRIPTED_MODEL]

    async def health(self) -> dict[str, Any]:
        return await self._engine.health()

    def capabilities(self) -> dict[str, bool]:
        return self._engine.capabilities()

    async def list_available_models(self) -> list[ModelInfo]:
        """The engine's listing and the scripted model, whose digest is the library's version."""
        return [
            *(await self._engine.list_available_models()),
            *(await self._scripted.list_available_models()),
        ]

    async def list_loaded_models(self) -> list[ModelInfo]:
        return await self._engine.list_loaded_models()

    async def requests_in_flight(self) -> int:
        return await self._engine.requests_in_flight()

    async def pull_model(self, model_name: str) -> None:
        if model_name == SCRIPTED_MODEL:
            raise ValueError(f"{SCRIPTED_MODEL!r} has no weights to pull")
        await self._engine.pull_model(model_name)

    async def delete_model(self, model_name: str) -> None:
        if model_name == SCRIPTED_MODEL:
            raise ValueError(f"{SCRIPTED_MODEL!r} has no weights to delete")
        await self._engine.delete_model(model_name)
