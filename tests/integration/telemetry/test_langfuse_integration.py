"""End-to-end integration tests: execute a minimal cycle (SIP-0061).

Gated behind @pytest.mark.langfuse — skipped unless all env vars are set.
"""

from __future__ import annotations

import os

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
class TestLangFuseIntegration:
    """End-to-end: execute a minimal cycle and verify LangFuse data."""

    @pytest.fixture(autouse=True)
    def setup_adapter(self):
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

    def test_cycle_produces_trace(self):
        """Full cycle lifecycle: start → events → end → flush."""
        ctx = CorrelationContext.for_cycle(cycle_id="integ-cycle-001")
        self.adapter.start_cycle_trace(ctx)
        self.adapter.record_event(
            ctx, StructuredEvent(name="cycle.started", message="Integration cycle started")
        )
        self.adapter.record_event(
            ctx, StructuredEvent(name="cycle.completed", message="Integration cycle done")
        )
        self.adapter.end_cycle_trace(ctx)
        self.adapter.flush()

    def test_pulse_and_task_spans_exist(self):
        """Cycle → Pulse → Task hierarchy."""
        ctx_cycle = CorrelationContext.for_cycle(cycle_id="integ-cycle-002")
        ctx_pulse = CorrelationContext.for_pulse(cycle_id="integ-cycle-002", pulse_id="pulse-001")
        ctx_task = CorrelationContext(
            cycle_id="integ-cycle-002",
            pulse_id="pulse-001",
            task_id="task-001",
            agent_id="dev-001",
            agent_role="dev",
        )

        self.adapter.start_cycle_trace(ctx_cycle)
        self.adapter.start_pulse_span(ctx_pulse)
        self.adapter.record_event(
            ctx_pulse, StructuredEvent(name="pulse.started", message="Pulse started")
        )

        self.adapter.start_task_span(ctx_task)
        self.adapter.record_event(
            ctx_task, StructuredEvent(name="task.started", message="Task started")
        )
        self.adapter.record_event(
            ctx_task, StructuredEvent(name="task.completed", message="Task done")
        )
        self.adapter.end_task_span(ctx_task)

        self.adapter.record_event(
            ctx_pulse, StructuredEvent(name="pulse.completed", message="Pulse done")
        )
        self.adapter.end_pulse_span(ctx_pulse)
        self.adapter.end_cycle_trace(ctx_cycle)
        self.adapter.flush()

    def test_generation_has_prompt_layers(self):
        """Generation recording with prompt layer metadata."""
        ctx_cycle = CorrelationContext.for_cycle(cycle_id="integ-cycle-003")
        ctx_task = CorrelationContext(
            cycle_id="integ-cycle-003",
            pulse_id="pulse-001",
            task_id="task-001",
        )

        self.adapter.start_cycle_trace(ctx_cycle)
        self.adapter.start_task_span(ctx_task)

        record = GenerationRecord(
            generation_id="gen-integ-001",
            model="llama3",
            prompt_text="Integration test prompt",
            response_text="Integration test response",
            prompt_tokens=10,
            completion_tokens=8,
            total_tokens=18,
            latency_ms=55.0,
        )
        layers = PromptLayerMetadata(
            prompt_layer_set_id="PLS-integ",
            layers=(
                PromptLayer(layer_type="system", layer_id="sys-integ", layer_version="1.0"),
                PromptLayer(layer_type="task", layer_id="task-integ"),
            ),
        )
        self.adapter.record_generation(ctx_task, record, layers)

        self.adapter.end_task_span(ctx_task)
        self.adapter.end_cycle_trace(ctx_cycle)
        self.adapter.flush()
