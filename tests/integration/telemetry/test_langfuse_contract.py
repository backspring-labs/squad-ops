"""Contract tests: submit telemetry to a running LangFuse instance (SIP-0061).

Gated behind @pytest.mark.langfuse — skipped unless all env vars are set.
"""

from __future__ import annotations

import asyncio

import pytest

from squadops.telemetry.models import (
    CorrelationContext,
    GenerationRecord,
    PromptLayer,
    PromptLayerMetadata,
    StructuredEvent,
)


@pytest.mark.integration
@pytest.mark.langfuse
class TestLangFuseContract:
    """Contract tests: submit telemetry to a running LangFuse instance."""

    @pytest.fixture(autouse=True)
    def setup_adapter(self):
        """Create a real LangFuseAdapter from env vars."""
        import os

        from squadops.config.schema import LangFuseConfig

        config = LangFuseConfig(
            enabled=True,
            host=os.environ["SQUADOPS__LANGFUSE__HOST"],
            public_key=os.environ["SQUADOPS__LANGFUSE__PUBLIC_KEY"],
            secret_key=os.environ["SQUADOPS__LANGFUSE__SECRET_KEY"],
            buffer_max_size=100,
            flush_interval_seconds=1,
            shutdown_flush_timeout_seconds=5,
        )

        from adapters.telemetry.langfuse.adapter import LangFuseAdapter

        self.adapter = LangFuseAdapter(config)
        yield
        self.adapter.close()

    def test_submit_trace(self):
        ctx = CorrelationContext.for_cycle(cycle_id="contract-cycle-001")
        self.adapter.start_cycle_trace(ctx)
        self.adapter.end_cycle_trace(ctx)
        self.adapter.flush()

    def test_submit_spans(self):
        ctx_cycle = CorrelationContext.for_cycle(cycle_id="contract-cycle-002")
        ctx_pulse = CorrelationContext.for_pulse(
            cycle_id="contract-cycle-002", pulse_id="pulse-001"
        )
        self.adapter.start_cycle_trace(ctx_cycle)
        self.adapter.start_pulse_span(ctx_pulse)
        self.adapter.end_pulse_span(ctx_pulse)
        self.adapter.end_cycle_trace(ctx_cycle)
        self.adapter.flush()

    def test_submit_generation_with_prompt_layers(self):
        ctx_cycle = CorrelationContext.for_cycle(cycle_id="contract-cycle-003")
        ctx_task = CorrelationContext(
            cycle_id="contract-cycle-003",
            pulse_id="pulse-001",
            task_id="task-001",
        )
        self.adapter.start_cycle_trace(ctx_cycle)
        self.adapter.start_task_span(ctx_task)

        record = GenerationRecord(
            generation_id="gen-contract-001",
            model="test-model",
            prompt_text="Hello from contract test",
            response_text="Contract response",
            prompt_tokens=5,
            completion_tokens=3,
            total_tokens=8,
            latency_ms=42.0,
        )
        layers = PromptLayerMetadata(
            prompt_layer_set_id="PLS-contract",
            layers=(
                PromptLayer(layer_type="system", layer_id="sys-contract"),
                PromptLayer(layer_type="task", layer_id="task-contract"),
            ),
        )
        self.adapter.record_generation(ctx_task, record, layers)
        self.adapter.end_task_span(ctx_task)
        self.adapter.end_cycle_trace(ctx_cycle)
        self.adapter.flush()

    def test_submit_event(self):
        ctx = CorrelationContext.for_cycle(cycle_id="contract-cycle-004")
        self.adapter.start_cycle_trace(ctx)
        self.adapter.record_event(
            ctx, StructuredEvent(name="task.assigned", message="Contract test event")
        )
        self.adapter.end_cycle_trace(ctx)
        self.adapter.flush()

    def test_health_returns_ok(self):
        result = asyncio.get_event_loop().run_until_complete(self.adapter.health())
        assert result["status"] == "ok"
        assert result["backend"] == "langfuse"
