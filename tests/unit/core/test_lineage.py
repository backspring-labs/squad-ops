"""Lineage ids carry their entropy and their trace is inherited, never derived (#575).

Before: ``trace_id`` / ``span_id`` were the literal strings ``trace-placeholder-{task_id}``
and ``span-placeholder-{task_id}`` — always present, never joinable — and task, cycle,
pulse and project ids were ``uuid4().hex[:8]`` / ``[:12]``, 80–96 of 122 random bits
thrown away. Each test names the regression it catches.
"""

from __future__ import annotations

import re

import pytest

from squadops.core.lineage import LineageGenerator, new_id, new_span_id, new_trace_id

pytestmark = [pytest.mark.unit]


def test_ids_are_full_width_and_never_placeholders():
    fields = LineageGenerator.ensure_lineage_fields(cycle_id="cyc_1", task_id="task-1")
    assert re.fullmatch(r"[0-9a-f]{32}", fields["trace_id"]), fields
    assert re.fullmatch(r"[0-9a-f]{16}", fields["span_id"]), fields
    assert "placeholder" not in fields["trace_id"] and "task-1" not in fields["trace_id"]
    assert re.fullmatch(r"task-[0-9a-f]{32}", new_id("task"))


def test_a_child_joins_its_parents_trace_and_takes_a_fresh_span():
    """The bug this catches: a trace id derived from the task id gives every envelope in
    one causal chain a different trace, so nothing downstream can join them."""
    parent = LineageGenerator.ensure_lineage_fields(cycle_id="cyc_1", task_id="task-1")
    child = LineageGenerator.ensure_lineage_fields(
        cycle_id="cyc_1",
        task_id="task-2",
        parent_task_id="task-1",
        parent_trace_id=parent["trace_id"],
    )
    assert child["trace_id"] == parent["trace_id"]
    assert child["span_id"] != parent["span_id"]
    assert child["causation_id"] == "cause-task-task-1"


def test_supplied_ids_win_and_generated_ones_differ_per_call():
    kept = LineageGenerator.ensure_lineage_fields(
        cycle_id="cyc_1", task_id="t", trace_id="given-trace", span_id="given-span"
    )
    assert (kept["trace_id"], kept["span_id"]) == ("given-trace", "given-span")
    assert new_trace_id() != new_trace_id() and new_span_id() != new_span_id()
    assert new_id("cycle") != new_id("cycle")
