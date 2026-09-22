"""SIP-0108 §4.1 — LLM usage accounted at the one seam and carried to the run's durable summary.

Each test names what it catches: a call that raised dropped from the count (the worse arm of a
comparison reads cheaper), a missing token figure read as zero, a reply with no usage read as a
free task, or a timed-out task whose calls vanish with it.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.cycles.llm_usage import (
    RunUsage,
    RunUsageAccumulator,
    UsageLedger,
    UsageTotals,
)
from squadops.cycles.run_loop_summary import RunLoopSummary
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_orchestration]


def _response(prompt=None, completion=None, reasoning=None):
    return MagicMock(prompt_tokens=prompt, completion_tokens=completion, reasoning_tokens=reasoning)


class TestTheLedger:
    def test_a_generation_counts_its_tokens_and_a_missing_figure_is_unreported(self):
        ledger = UsageLedger()
        ledger.record_generation(_response(1200, 300, 40), 1500.0)
        ledger.record_generation(_response(900, None, None), 500.0)
        assert ledger.totals == UsageTotals(
            calls=2,
            prompt_tokens=2100,
            completion_tokens=300,
            reasoning_tokens=40,
            duration_ms=2000.0,
            unreported_completion=1,
            unreported_reasoning=1,
        )

    def test_a_call_that_raised_is_a_call(self):
        """Bug caught: counting only responses — a provider timeout costs wall-clock and
        possibly tokens, and dropping it makes the arm that fails more read cheaper."""
        ledger = UsageLedger()
        ledger.record_failed_call(30000.0)
        assert (ledger.totals.calls, ledger.totals.failed_calls) == (1, 1)
        assert ledger.totals.duration_ms == 30000.0

    @pytest.mark.parametrize(
        "raw",
        [None, "calls=1", {"calls": -1}, {"calls": True}, {"prompt_tokens": "100"}],
    )
    def test_malformed_usage_off_the_wire_is_unreadable_not_zero(self, raw):
        assert UsageTotals.from_dict(raw) is None

    def test_unknown_keys_from_a_newer_agent_are_dropped(self):
        assert UsageTotals.from_dict({"calls": 2, "cache_hits": 7}) == UsageTotals(calls=2)


class TestTheRunSum:
    def test_replies_sum_per_task_type_and_a_reply_without_usage_is_named(self):
        acc = RunUsageAccumulator()
        acc.record("development.develop", "t1", UsageTotals(calls=2, prompt_tokens=10).to_dict())
        acc.record(
            "development.develop", "t1-retry", UsageTotals(calls=1, failed_calls=1).to_dict()
        )
        acc.record("qa.test", "t2", UsageTotals(calls=1, completion_tokens=5).to_dict())
        acc.record("qa.test", "t3", None)  # a reply timeout
        acc.record("qa.test", "t4", {"calls": "x"})  # unreadable
        usage = acc.summary()
        assert usage.by_task_type["development.develop"] == UsageTotals(
            calls=3, failed_calls=1, prompt_tokens=10
        )
        assert usage.total == UsageTotals(
            calls=4, failed_calls=1, prompt_tokens=10, completion_tokens=5
        )
        assert (usage.tasks_reported, usage.tasks_unreported) == (3, ("t3", "t4"))

    def test_the_summary_round_trips_through_its_stored_shape(self):
        usage = RunUsage(
            by_task_type={"qa.test": UsageTotals(calls=3, reasoning_tokens=9, duration_ms=12.5)},
            tasks_reported=2,
            tasks_unreported=("t9",),
        )
        from squadops.cycles.run_loop_summary import MovementRecord, RefundedRound

        summary = RunLoopSummary(
            run_id="run_1",
            usage=usage,
            refunded_rounds=(RefundedRound("t1", 0, "empty_repair_emission", ("cap_exhausted",)),),
            movements=(MovementRecord("t1", 0, "new"), MovementRecord("t1", 1, "shifted")),
        )
        assert RunLoopSummary.from_dict(summary.to_dict()) == summary


def _llm_handler(*, raise_second: bool, sleep_after_first: float = 0.0):
    from squadops.capabilities.handlers.base import HandlerEvidence, HandlerResult
    from squadops.capabilities.handlers.cycle.base import _CycleTaskHandler
    from squadops.llm.exceptions import LLMError
    from squadops.llm.models import ChatMessage

    class TwoCallHandler(_CycleTaskHandler):
        _handler_name = "two_call_handler"
        _task_type = "development.develop"
        _role = "dev"

        def validate_inputs(self, inputs, contract=None):
            return []

        async def handle(self, context, inputs):
            started = time.perf_counter()
            message = [ChatMessage(role="user", content="go")]
            await self._llm_call(context, message, {}, inputs=inputs, started=started, record=False)
            if sleep_after_first:
                await asyncio.sleep(sleep_after_first)
            try:
                await self._llm_call(
                    context, message, {}, inputs=inputs, started=started, record=False
                )
            except LLMError as exc:
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=HandlerEvidence.create(
                        handler_name=self._handler_name,
                        task_type=self._task_type,
                        duration_ms=1.0,
                    ),
                    error=str(exc),
                )
            raise AssertionError("the second call was meant to raise")

    responses = [
        ChatMessage(role="assistant", content="x", prompt_tokens=800, completion_tokens=120),
        LLMError("provider timed out")
        if raise_second
        else ChatMessage(role="assistant", content="y"),
    ]
    llm = MagicMock()
    llm.chat_stream_with_usage = AsyncMock(side_effect=responses)
    return TwoCallHandler(), llm


def _executor_for(handler, llm):
    from squadops.agents.base import PortsBundle
    from squadops.orchestration.handler_executor import HandlerExecutor
    from squadops.orchestration.handler_registry import HandlerRegistry

    registry = HandlerRegistry()
    registry.register(handler)
    ports = PortsBundle(
        llm=llm,
        memory=MagicMock(),
        prompt_service=MagicMock(),
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=MagicMock(),
    )
    return HandlerExecutor("exec-1", registry, ports, role="dev")


def _envelope(task_id: str = "task-run_1-m000-development.develop") -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        agent_id="neo",
        cycle_id="cyc_1",
        pulse_id="p",
        project_id="proj",
        task_type="development.develop",
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
    )


class TestTheAgentSideCarriesUsageOnEveryExit:
    async def test_a_failed_task_reports_the_call_that_raised(self):
        """SIP-0108 §5 criterion 2, the ``_llm_call`` half. Entry point: ``HandlerExecutor.
        execute`` — the agent's seam — with a handler whose second call raises. Bug caught:
        the accumulator riding only the success path, so the failed task reports nothing."""
        handler, llm = _llm_handler(raise_second=True)
        result = await _executor_for(handler, llm).execute(_envelope())

        assert result.status == "FAILED"
        assert UsageTotals.from_dict(result.llm_usage) == UsageTotals(
            calls=2,
            failed_calls=1,
            prompt_tokens=800,
            completion_tokens=120,
            duration_ms=UsageTotals.from_dict(result.llm_usage).duration_ms,
            unreported_reasoning=1,
        )
        # ...and it survives the wire the runtime reads it from.
        assert TaskResult.from_dict(result.to_dict()).llm_usage == result.llm_usage

    async def test_a_timed_out_task_carries_the_calls_it_made_before_running_out(self):
        """Bug caught: the timeout path re-raises, and the entrypoint built the failed result
        from the exception alone — the calls a slow task made vanished with it."""
        handler, llm = _llm_handler(raise_second=False, sleep_after_first=5.0)
        with pytest.raises(TimeoutError) as raised:
            await _executor_for(handler, llm).execute(_envelope(), timeout_seconds=0.05)
        assert UsageTotals.from_dict(raised.value.llm_usage).calls == 1


class TestTheRuntimeSideSumsEveryDispatch:
    @pytest.fixture
    def dispatcher(self, reply_router):
        from adapters.cycles.task_dispatcher import TaskDispatcher

        queue = AsyncMock()
        return TaskDispatcher(
            queue=reply_router.bind(queue), reply_router=reply_router, task_timeout=5.0
        )

    async def test_each_reply_is_added_to_its_run_and_taken_once(self, dispatcher, reply_router):
        """Entry point: ``TaskDispatcher.dispatch_task``, the one path every dispatch takes.
        Bug caught: usage summed across runs, or never released."""
        reply_router.results["t-a"] = TaskResult(
            task_id="t-a", status="FAILED", llm_usage=UsageTotals(calls=2, failed_calls=1).to_dict()
        )
        reply_router.results["t-b"] = TaskResult(task_id="t-b", status="SUCCEEDED")
        with patch("adapters.cycles.task_dispatcher.asyncio.sleep", new_callable=AsyncMock):
            await dispatcher.dispatch_task(_envelope("t-a"), "run_a")
            await dispatcher.dispatch_task(_envelope("t-b"), "run_b")

        run_a = dispatcher.take_run_usage("run_a")
        assert run_a.total == UsageTotals(calls=2, failed_calls=1)
        assert dispatcher.take_run_usage("run_b").tasks_unreported == ("t-b",)
        # Taken once: a second take is an empty run, not the same sum again.
        assert dispatcher.take_run_usage("run_a").total == UsageTotals()

    async def test_a_reply_wait_that_raises_is_named_unreported(self, dispatcher, monkeypatch):
        async def _raises(envelope, run_id):
            raise RuntimeError("router stopped")

        monkeypatch.setattr(dispatcher, "_publish_and_await", _raises)
        with pytest.raises(RuntimeError):
            await dispatcher.dispatch_task(_envelope("t-x"), "run_x")
        assert dispatcher.take_run_usage("run_x").tasks_unreported == ("t-x",)
