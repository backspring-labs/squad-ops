"""``refuse_undecidable`` against the registry it reads ahead of (SIP-0109 §24da).

The registry is the one enforcement point for a gate decision (T11). The preflight answers the same
question without recording, so a caller can write its audit row first. If the two disagree, a
delegated answer's row says something happened that didn't.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.gate_decisions import refuse_undecidable
from squadops.cycles.models import Cycle, Gate, GateDecision, Run, TaskFlowPolicy

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _decision(gate: str = "plan", decision: str = "approved") -> GateDecision:
    return GateDecision(gate_name=gate, decision=decision, decided_by="operator", decided_at=NOW)


async def _registry(status: str = "completed") -> MemoryCycleRegistry:
    registry = MemoryCycleRegistry()
    await registry.create_cycle(
        Cycle(
            cycle_id="cyc",
            project_id="p",
            created_at=NOW,
            created_by="launcher",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential", gates=(Gate("plan", "d", ()),)),
            build_strategy="fresh",
        )
    )
    await registry.create_run(
        Run(
            run_id="run",
            cycle_id="cyc",
            run_number=1,
            status=status,
            initiated_by="system",
            resolved_config_hash="cfg",
        )
    )
    return registry


@pytest.mark.parametrize(
    ("status", "already", "decision", "run_id"),
    [
        ("completed", None, _decision(), "run"),
        ("completed", "approved", _decision(), "run"),
        ("completed", "rejected", _decision(), "run"),
        ("completed", None, _decision(gate="not_in_the_policy"), "run"),
        ("failed", None, _decision(), "run"),
        ("cancelled", None, _decision(), "run"),
        ("completed", None, _decision(), "no_such_run"),
    ],
    ids=["open", "same-again", "decided", "unknown-gate", "failed", "cancelled", "unknown-run"],
)
async def test_the_preflight_answers_as_the_registry_does(status, already, decision, run_id):
    """Bug caught: a rule added to, or changed in, ``record_gate_decision`` and not here, so a
    delegated answer records an applied row for a decision the registry then refuses."""
    registry = await _registry()
    if already is not None:
        await registry.record_gate_decision("run", _decision(decision=already))
    registry._runs["run"]["status"] = status

    async def outcome(call) -> tuple[type, str] | None:
        try:
            await call
        except Exception as e:  # noqa: BLE001 - the comparison is of whatever each raises
            return type(e), str(e)
        return None

    ahead = await outcome(refuse_undecidable(registry, run_id, decision))
    actual = await outcome(registry.record_gate_decision(run_id, decision))

    assert ahead == actual
