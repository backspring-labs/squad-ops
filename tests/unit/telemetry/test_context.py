"""Tests for squadops.telemetry.context (SIP-0087).

Covers:
- ``get_correlation_context`` returns ``None`` outside any scope.
- ``use_correlation_context`` sets the active context and restores on exit.
- ``use_run_ids`` overlays flow/task IDs on the active ``CorrelationContext``,
  preserving every other field.
- ``use_run_ids`` raises ``RuntimeError`` when no context is active (the prior
  synthesis path leaked ``cycle_id=""`` to every other consumer).
- Contextvar copy-on-task-spawn: ``asyncio.create_task`` children see the
  overlay applied in the parent.
- Nesting: inner ``use_run_ids`` can shadow one field without losing the other.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from squadops.telemetry.context import (
    get_correlation_context,
    use_correlation_context,
    use_run_ids,
)
from squadops.telemetry.models import CorrelationContext

pytestmark = [pytest.mark.domain_telemetry]


class TestGetCorrelationContext:
    def test_default_is_none(self):
        assert get_correlation_context() is None


class TestUseCorrelationContext:
    def test_scopes_context_and_restores(self):
        ctx = CorrelationContext(cycle_id="c-1", pulse_id="p-1")
        with use_correlation_context(ctx) as scoped:
            assert scoped is ctx
            assert get_correlation_context() is ctx
        assert get_correlation_context() is None

    def test_restores_outer_context_on_inner_exit(self):
        outer = CorrelationContext(cycle_id="outer")
        inner = CorrelationContext(cycle_id="inner")
        with use_correlation_context(outer):
            with use_correlation_context(inner):
                assert get_correlation_context() is inner
            assert get_correlation_context() is outer


class TestUseRunIds:
    def test_overlay_on_active_context_preserves_other_fields(self):
        ctx = CorrelationContext(
            cycle_id="c-1",
            pulse_id="p-1",
            task_id="t-1",
            agent_id="neo",
            trace_id="tr-1",
        )
        with use_correlation_context(ctx):
            with use_run_ids(flow_run_id="flow-1", task_run_id="task-1") as merged:
                assert merged is not None
                assert merged.flow_run_id == "flow-1"
                assert merged.task_run_id == "task-1"
                # Everything else is preserved.
                assert merged.cycle_id == "c-1"
                assert merged.pulse_id == "p-1"
                assert merged.task_id == "t-1"
                assert merged.agent_id == "neo"
                assert merged.trace_id == "tr-1"
            # Overlay cleared; base context restored.
            restored = get_correlation_context()
            assert restored is ctx
            assert restored.flow_run_id is None
            assert restored.task_run_id is None

    def test_overlay_without_active_context_raises(self):
        # Previously synthesized an empty CorrelationContext (cycle_id="") which
        # leaked to other consumers like the LangFuse adapter. Now it must fail
        # loudly so callers enter use_correlation_context first.
        assert get_correlation_context() is None
        with pytest.raises(RuntimeError, match="active CorrelationContext"):
            with use_run_ids(flow_run_id="flow-2", task_run_id="task-2"):
                pass
        assert get_correlation_context() is None

    def test_partial_overlay_leaves_untouched_field(self):
        base = CorrelationContext(cycle_id="c-1", flow_run_id="flow-base", task_run_id="task-base")
        with use_correlation_context(base):
            # Only overlay task_run_id; flow_run_id should remain the base value.
            with use_run_ids(task_run_id="task-overlay") as merged:
                assert merged is not None
                assert merged.flow_run_id == "flow-base"
                assert merged.task_run_id == "task-overlay"

    def test_nested_overlay_shadows_outer(self):
        base = CorrelationContext(cycle_id="c-1")
        with use_correlation_context(base):
            with use_run_ids(flow_run_id="flow-A", task_run_id="task-A"):
                with use_run_ids(task_run_id="task-B") as inner:
                    assert inner is not None
                    # flow_run_id inherited from outer overlay.
                    assert inner.flow_run_id == "flow-A"
                    assert inner.task_run_id == "task-B"
                outer = get_correlation_context()
                assert outer is not None
                assert outer.flow_run_id == "flow-A"
                assert outer.task_run_id == "task-A"

    async def test_spawned_task_inherits_overlay_snapshot(self):
        seen: dict[str, Any] = {}

        async def child() -> None:
            ctx = get_correlation_context()
            seen["flow"] = ctx.flow_run_id if ctx else None
            seen["task"] = ctx.task_run_id if ctx else None

        base = CorrelationContext(cycle_id="c-1")
        with use_correlation_context(base):
            with use_run_ids(flow_run_id="flow-42", task_run_id="task-42"):
                await asyncio.create_task(child())
        assert seen == {"flow": "flow-42", "task": "task-42"}
        # Parent context reset after both with-blocks.
        assert get_correlation_context() is None

    async def test_spawned_task_does_not_leak_child_overlay_back_to_parent(self):
        base = CorrelationContext(cycle_id="c-1", flow_run_id="flow-parent")

        async def child() -> None:
            # Child's own overlay should be invisible to the parent's frame.
            with use_run_ids(task_run_id="child-only"):
                pass

        with use_correlation_context(base):
            await asyncio.create_task(child())
            parent = get_correlation_context()
            assert parent is base
            assert parent.task_run_id is None
