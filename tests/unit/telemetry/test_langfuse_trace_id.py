"""Tests for LangFuse trace_id-based trace identity (SIP-0061 Option B).

Verifies that the adapter uses ctx.trace_id when set (cross-process trace
linking) and falls back to ctx.cycle_id when trace_id is None.

Uses the same fake langfuse SDK injection pattern as test_langfuse_adapter.py.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from squadops.config.schema import LangFuseConfig
from squadops.telemetry.models import CorrelationContext

pytestmark = [pytest.mark.langfuse]


def _make_config(**overrides) -> LangFuseConfig:
    defaults = {
        "enabled": True,
        "host": "http://localhost:3000",
        "public_key": "pk-test",
        "secret_key": "sk-test",
        "buffer_max_size": 100,
        "flush_interval_seconds": 60,
        "shutdown_flush_timeout_seconds": 2,
        "sample_rate_percent": 100,
        "redaction_mode": "standard",
    }
    defaults.update(overrides)
    return LangFuseConfig(**defaults)


def _inject_fake_langfuse():
    """Inject a fake langfuse module into sys.modules."""
    fake = types.ModuleType("langfuse")
    mock_client = MagicMock()
    mock_client.auth_check.return_value = True
    # trace() returns a mock that supports .span(), .event(), .generation()
    mock_trace = MagicMock()
    mock_client.trace.return_value = mock_trace
    fake.Langfuse = MagicMock(return_value=mock_client)
    return fake, mock_client


def _create_adapter(config=None):
    fake_mod, mock_client = _inject_fake_langfuse()
    old = sys.modules.get("langfuse")
    sys.modules["langfuse"] = fake_mod
    sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
    try:
        from adapters.telemetry.langfuse.adapter import LangFuseAdapter

        return LangFuseAdapter(config or _make_config()), mock_client, old
    except Exception:
        if old is None:
            sys.modules.pop("langfuse", None)
        else:
            sys.modules["langfuse"] = old
        sys.modules.pop("adapters.telemetry.langfuse.adapter", None)
        raise


def _cleanup(adapter, old_langfuse):
    adapter._shutdown.set()
    adapter._flush_requested.set()
    adapter._flush_thread.join(timeout=2)
    if old_langfuse is None:
        sys.modules.pop("langfuse", None)
    else:
        sys.modules["langfuse"] = old_langfuse
    sys.modules.pop("adapters.telemetry.langfuse.adapter", None)


@pytest.fixture
def setup():
    """Create adapter with fake SDK; yields (adapter, mock_client)."""
    adapter, mock_client, old = _create_adapter()
    yield adapter, mock_client
    _cleanup(adapter, old)


class TestTraceUsesTraceId:
    """When ctx.trace_id is set, adapter uses it as trace identity."""

    def test_trace_uses_trace_id_when_set(self, setup):
        adapter, mock_client = setup
        ctx = CorrelationContext(
            cycle_id="cyc_001",
            trace_id="shared-trace-abc",
        )

        adapter.start_cycle_trace(ctx)
        adapter._drain_buffer()

        mock_client.trace.assert_called_once()
        call_kwargs = mock_client.trace.call_args
        assert call_kwargs.kwargs.get("id") or call_kwargs[1].get("id") == "shared-trace-abc"

    def test_trace_falls_back_to_cycle_id(self, setup):
        adapter, mock_client = setup
        ctx = CorrelationContext(
            cycle_id="cyc_002",
            trace_id=None,
        )

        adapter.start_cycle_trace(ctx)
        adapter._drain_buffer()

        mock_client.trace.assert_called_once()
        call_kwargs = mock_client.trace.call_args
        assert call_kwargs.kwargs.get("id") or call_kwargs[1].get("id") == "cyc_002"


class TestSpanStateKeys:
    """Span state keys use resolved trace key."""

    def test_span_state_key_uses_trace_id(self, setup):
        adapter, mock_client = setup
        ctx = CorrelationContext(
            cycle_id="cyc_001",
            trace_id="shared-trace-xyz",
        )

        adapter.start_cycle_trace(ctx)
        adapter._drain_buffer()

        assert "cycle:shared-trace-xyz" in adapter._span_state
        assert "cycle:cyc_001" not in adapter._span_state

    def test_span_state_key_uses_cycle_id_when_no_trace_id(self, setup):
        adapter, mock_client = setup
        ctx = CorrelationContext(
            cycle_id="cyc_003",
            trace_id=None,
        )

        adapter.start_cycle_trace(ctx)
        adapter._drain_buffer()

        assert "cycle:cyc_003" in adapter._span_state

    def test_end_cycle_pops_correct_key(self, setup):
        adapter, mock_client = setup
        ctx = CorrelationContext(
            cycle_id="cyc_001",
            trace_id="shared-trace-end",
        )

        adapter.start_cycle_trace(ctx)
        adapter._drain_buffer()
        assert "cycle:shared-trace-end" in adapter._span_state

        adapter.end_cycle_trace(ctx)
        adapter._drain_buffer()
        assert "cycle:shared-trace-end" not in adapter._span_state


class TestTaskSpanUsesTraceKey:
    """Task spans nest under trace keyed by trace_id."""

    def test_task_span_keyed_by_trace_id(self, setup):
        adapter, mock_client = setup
        ctx = CorrelationContext(
            cycle_id="cyc_001",
            trace_id="shared-trace-task",
            task_id="task-abc",
        )

        adapter.start_cycle_trace(ctx)
        adapter._drain_buffer()

        adapter.start_task_span(ctx)
        adapter._drain_buffer()

        assert "task:shared-trace-task:task-abc" in adapter._span_state

    def test_end_task_span_pops_correct_key(self, setup):
        adapter, mock_client = setup
        ctx = CorrelationContext(
            cycle_id="cyc_001",
            trace_id="shared-trace-task2",
            task_id="task-def",
        )

        adapter.start_cycle_trace(ctx)
        adapter._drain_buffer()
        adapter.start_task_span(ctx)
        adapter._drain_buffer()
        assert "task:shared-trace-task2:task-def" in adapter._span_state

        adapter.end_task_span(ctx)
        adapter._drain_buffer()
        assert "task:shared-trace-task2:task-def" not in adapter._span_state
