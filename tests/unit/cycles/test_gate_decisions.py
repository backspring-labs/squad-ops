"""#1986: every gate decision is recorded by one function, whoever decides it.

Three deciders assembled "record, promote on approval, emit gate.decided" by hand, and had
diverged twice: the pass-through promoted nothing (#854), and the event was keyed on the gate
from the route but on the run from the machine paths. Each entry point below is driven from
the caller a live cycle uses, and must produce the same row, the same promotion and the same
event.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles.runs import router
from squadops.cycles.gate_decisions import record_gate_decision
from squadops.cycles.models import (
    Cycle,
    GateDecision,
    GateDecisionValue,
    Run,
    TaskFlowPolicy,
)
from squadops.events.types import EventType

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 10, 5, 5, 0, 0, tzinfo=UTC)
_GATE = "progress_plan_review"
# SIP-0077 §7.3's fields, the one payload every decider emits.
_PAYLOAD_KEYS = {"gate_name", "decision", "decided_by", "decided_at", "notes"}

_CYCLE = Cycle(
    cycle_id="cyc_001",
    project_id="proj_001",
    created_at=NOW,
    created_by="system",
    prd_ref=None,
    squad_profile_id="full",
    squad_profile_snapshot_ref="sha256:abc",
    task_flow_policy=TaskFlowPolicy(mode="sequential"),
    build_strategy="fresh",
    applied_defaults={"workload_sequence": [{"type": "framing", "gate": _GATE}]},
)


def _run(**kw) -> Run:
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status=kw.pop("status", "completed"),
        initiated_by="api",
        resolved_config_hash="hash_abc",
        workload_type="framing",
        **kw,
    )


def _vault() -> tuple[SimpleNamespace, list[str]]:
    """A vault holding two working artifacts and one already promoted; returns what it promoted."""
    promoted: list[str] = []
    working = [
        SimpleNamespace(artifact_id="art_plan", promotion_status="working"),
        SimpleNamespace(artifact_id="art_manifest", promotion_status="working"),
        SimpleNamespace(artifact_id="art_done", promotion_status="promoted"),
    ]
    vault = SimpleNamespace(
        list_artifacts=AsyncMock(return_value=working),
        promote_artifact=AsyncMock(side_effect=lambda aid: promoted.append(aid)),
        retrieve=AsyncMock(side_effect=KeyError("none")),
        store=AsyncMock(),
    )
    return vault, promoted


def _gate_decided(bus: MagicMock) -> list[dict]:
    """Every gate.decided the bus received, as the keyword shape it was emitted with."""
    return [c.kwargs for c in bus.emit.call_args_list if c.args[0] == EventType.GATE_DECIDED]


def _assert_one_shape(bus: MagicMock, *, decision: str, decided_by: str) -> None:
    events = _gate_decided(bus)
    assert len(events) == 1
    event = events[0]
    assert (event["entity_type"], event["entity_id"]) == ("gate", _GATE)
    assert event["context"] == {
        "cycle_id": "cyc_001",
        "run_id": "run_001",
        "project_id": "proj_001",
    }
    assert set(event["payload"]) == _PAYLOAD_KEYS
    assert event["payload"]["decision"] == decision
    assert event["payload"]["decided_by"] == decided_by


# --------------------------------------------------------------------------- #
# The three entry points
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("decision", "promotes"),
    [
        ("approved", True),
        # Before #1986 the route promoted only on "approved", while the gate proceeds on a
        # refinement approval too: the next workload was admitted with nothing forwarded.
        ("approved_with_refinements", True),
        ("rejected", False),
    ],
)
def test_the_route_records_promotes_and_emits_through_the_recorder(decision, promotes):
    registry = AsyncMock()
    registry.get_run.return_value = _run()
    registry.record_gate_decision.side_effect = lambda run_id, d: _run(gate_decisions=(d,))
    vault, promoted = _vault()
    bus = MagicMock()
    app = FastAPI()
    app.include_router(router)
    register_domain_error_handlers(app)
    app.state.cycle_registry = registry
    app.state.artifact_vault = vault
    app.state.cycle_event_bus = bus

    resp = TestClient(app).post(
        f"/api/v1/projects/proj_001/cycles/cyc_001/runs/run_001/gates/{_GATE}",
        json={"decision": decision, "notes": "read it"},
    )

    assert resp.status_code == 200
    recorded = registry.record_gate_decision.await_args.args[1]
    assert (recorded.gate_name, recorded.decision, recorded.notes) == (_GATE, decision, "read it")
    assert promoted == (["art_plan", "art_manifest"] if promotes else [])
    _assert_one_shape(bus, decision=decision, decided_by=recorded.decided_by)
    assert _gate_decided(bus)[0]["payload"]["notes"] == "read it"


def _executor(bus: MagicMock, vault: SimpleNamespace, registry: AsyncMock):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    executor = DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
    )
    executor._cycle_event_bus = bus
    return executor


async def _decide(executor):
    return await executor._workload_gate.decide(
        cycle=_CYCLE,
        cycle_id="cyc_001",
        run=_run(),
        workload_entry={"type": "framing", "gate": _GATE},
        gate_name=_GATE,
        current_run_id="run_001",
        forwarding_overrides=None,
        framing_rerolls=0,
        framing_revisions=0,
        max_framing_rerolls=0,
        max_framing_revisions=0,
    )


async def test_the_question_free_pass_through_goes_through_the_recorder():
    """The executor's approval when the design asks nothing (#807), entered at the gate."""
    registry = AsyncMock()
    vault, promoted = _vault()
    bus = MagicMock()
    executor = _executor(bus, vault, registry)
    executor._reject_invalid_plan_before_workload_gate = AsyncMock(return_value=[])
    executor._design_questions_for_gate = AsyncMock(return_value=())

    await _decide(executor)

    recorded = registry.record_gate_decision.await_args.args[1]
    assert (recorded.decision, recorded.decided_by) == ("approved", "system:no_open_questions")
    assert promoted == ["art_plan", "art_manifest"]
    _assert_one_shape(bus, decision="approved", decided_by="system:no_open_questions")


async def test_the_plan_rejection_goes_through_the_recorder_and_promotes_nothing():
    """The workload gate's plan-validation rejection (#473), entered at the gate."""
    registry = AsyncMock()
    vault, promoted = _vault()
    bus = MagicMock()
    executor = _executor(bus, vault, registry)
    executor._reject_invalid_plan_before_workload_gate = AsyncMock(
        return_value=["the plan names no qa task"]
    )

    await _decide(executor)

    recorded = registry.record_gate_decision.await_args.args[1]
    assert (recorded.decision, recorded.decided_by) == ("rejected", "system:plan_validation")
    assert promoted == []
    _assert_one_shape(bus, decision="rejected", decided_by="system:plan_validation")
    assert _gate_decided(bus)[0]["payload"]["notes"] == "the plan names no qa task"


# --------------------------------------------------------------------------- #
# The recorder's own order
# --------------------------------------------------------------------------- #


async def test_a_registry_failure_promotes_and_announces_nothing():
    """A decision that was not recorded must not look decided to anyone downstream."""
    registry = AsyncMock()
    registry.record_gate_decision.side_effect = RuntimeError("db down")
    vault, promoted = _vault()
    bus = MagicMock()
    decision = GateDecision(
        gate_name=_GATE,
        decision=GateDecisionValue.APPROVED.value,
        decided_by="user:admin",
        decided_at=NOW,
    )

    with pytest.raises(RuntimeError, match="db down"):
        await record_gate_decision(
            registry,
            vault,
            bus,
            project_id="proj_001",
            cycle_id="cyc_001",
            run_id="run_001",
            decision=decision,
        )

    assert promoted == []
    assert _gate_decided(bus) == []


async def test_an_unknown_decision_value_never_promotes():
    """#466's rule, on the promotion side: only the approving set acts as an approval."""
    registry = AsyncMock()
    vault, promoted = _vault()
    bus = MagicMock()
    decision = GateDecision(
        gate_name=_GATE, decision="approved_later", decided_by="user:admin", decided_at=NOW
    )

    await record_gate_decision(
        registry,
        vault,
        bus,
        project_id="proj_001",
        cycle_id="cyc_001",
        run_id="run_001",
        decision=decision,
    )

    assert promoted == []
    assert len(_gate_decided(bus)) == 1


# --------------------------------------------------------------------------- #
# No fourth copy
# --------------------------------------------------------------------------- #

_ROOT = Path(__file__).resolve().parents[3]
_RECORDER = _ROOT / "src/squadops/cycles/gate_decisions.py"
# The registry port and its adapters define record_gate_decision; they are what the recorder
# calls, not deciders.
_REGISTRY_FILES = {
    _ROOT / "src/squadops/ports/cycles/cycle_registry.py",
    _ROOT / "adapters/cycles/memory_cycle_registry.py",
    _ROOT / "adapters/cycles/postgres_cycle_registry.py",
}


def _hand_assembled_steps(path: Path) -> list[str]:
    """Where ``path`` emits gate.decided or records a decision on the registry directly."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Attribute) and node.attr == "GATE_DECIDED":
            found.append(f"{path.relative_to(_ROOT)}:{node.lineno} EventType.GATE_DECIDED")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "record_gate_decision"
        ):
            found.append(f"{path.relative_to(_ROOT)}:{node.lineno} .record_gate_decision(")
    return found


def test_no_decider_records_or_announces_a_decision_by_hand():
    """The supervisor role (#1940) and the auto tier (#1708) are the next deciders. A decider
    that records on the registry or emits gate.decided itself is the fourth copy #1986 removed;
    it calls ``squadops.cycles.gate_decisions.record_gate_decision`` instead (a bare name, which
    this does not flag; a registry's method is an attribute call, which it does)."""
    offenders = [
        hit
        for tree in ("src", "adapters")
        for path in sorted((_ROOT / tree).rglob("*.py"))
        if path != _RECORDER and path not in _REGISTRY_FILES
        for hit in _hand_assembled_steps(path)
    ]
    assert offenders == []


def _approval_pairs(path: Path) -> list[str]:
    """Collection literals naming both approving values: a private copy of the approving set."""
    found = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            names = {e.attr for e in node.elts if isinstance(e, ast.Attribute)}
            if {"APPROVED", "APPROVED_WITH_REFINEMENTS"} <= names:
                found.append(f"{path.relative_to(_ROOT)}:{node.lineno}")
    return found


def test_what_counts_as_an_approval_is_answered_once():
    """Three readers decide whether a decision approves: the workload gate, the executor's mid-run
    gate and the recorder. The route once answered differently from the gate, and a refinement
    approval proceeded with nothing promoted (#1986). Each reads ``APPROVING_DECISIONS``."""
    copies = [
        hit
        for tree in ("src", "adapters")
        for path in sorted((_ROOT / tree).rglob("*.py"))
        if path != _ROOT / "src/squadops/cycles/models.py"
        for hit in _approval_pairs(path)
    ]
    assert copies == []
