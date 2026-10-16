"""The correction protocol's diagnosis, recorded before #1994 splits it (extraction map §4d, step 0).

``CorrectionRunner._diagnose`` builds what a correction round knows: the failure evidence and
what is added to it, the round failure, the priority reserve. Then it dispatches each step the
profile declares. The correction golden (``test_correction_context_golden.py``) records only the
repair and retest envelopes, so the analysis and decision envelopes built here were pinned only
by single assertions. Map §4d moves the evidence into ``_round_evidence`` and one declared step
into ``_dispatch_declared_step``; this file is what proves the move changed nothing.

Each case enters at ``run_correction_protocol``, the runner's entry point the executor calls,
with the dispatch seam captured and ``uuid4`` counted. It records:
- every protocol step's envelope: its ids, agent, type, metadata, its inputs and their key order;
- the events emitted, in order, with their payloads;
- the ledger's round-failure rows;
- what the protocol returned, or the exception the round ended with.

Regenerate (only for a DELIBERATE behaviour change, in the PR that makes it):
    UPDATE_CORRECTION_DIAGNOSIS_GOLDENS=1 \\
        pytest tests/unit/cycles/test_correction_diagnosis_characterization.py
"""

from __future__ import annotations

import copy
import dataclasses
import itertools
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.cycles.models import AgentProfileEntry, SquadProfile
from squadops.cycles.run_ledger import RunLedger
from squadops.execution.correction_runner import CorrectionRunner
from squadops.execution.execution_errors import _ExecutionError
from squadops.stacks.scaffold import InterfaceManifest
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_orchestration]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "correction_diagnosis_characterization.json"
_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)
_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_RUN_ID = "run_abcdef123456"
_FAILED_TASK_ID = "task-run_abcdef12-m001-development.develop"

_PROFILE = SquadProfile(
    profile_id="full",
    name="Full Squad",
    description="All",
    version=1,
    agents=tuple(
        AgentProfileEntry(agent_id=agent, role=role, model="m", enabled=True, serves_roles=(role,))
        for agent, role in (
            ("nat", "strat"),
            ("neo", "dev"),
            ("eve", "qa"),
            ("data-agent", "data"),
            ("max", "lead"),
            ("bob", "builder"),
        )
    ),
    created_at=_NOW,
)

_FAILED_INPUTS = {
    "prd": "PRD-CONTENT",
    "resolved_config": {"build_profile": "fastapi_react_vite"},
    "subtask_focus": "Backend API",
    "expected_artifacts": ["backend/routes.py"],
    "implementation_artifacts": ["backend/routes.py", "backend/models.py"],
    "acceptance_criteria": [
        {"check": "endpoint_defined", "params": {"method": "GET", "path": "/api/runs"}}
    ],
}

_ANALYSIS = {
    "classification": "work_product",
    "analysis_summary": "The emitted routes module never registers GET /api/runs.",
}
_DECISION = {
    "correction_path": "patch",
    "decision_rationale": "patch the routes module",
    "affected_task_types": ["development.develop"],
    "structural_plan_change_candidate": "none",
}
_DISPUTE = {
    "by": "development",
    "check": "endpoint_defined",
    "reason": "the endpoint is registered under /api/v1/runs, as the contract says",
}


@dataclasses.dataclass
class _Case:
    """One correction round: what the profile declares, what the analyzer says, and the run's
    state going in."""

    steps: list[str] = dataclasses.field(default_factory=lambda: ["analyze", "decide", "repair"])
    analysis: dict[str, Any] = dataclasses.field(default_factory=lambda: dict(_ANALYSIS))
    with_manifest: bool = False
    scaffold_enforcement_carry: list[str] | None = None
    repair_rejections: list[str] | None = None
    disputes: list[dict[str, Any]] | None = None
    required_checks: list[str] | None = None
    correction_attempts: int = 0
    correction_budget: int = 3


def _cases() -> dict[str, _Case]:
    return {
        "full_protocol_with_carried_evidence": _Case(
            with_manifest=True,
            scaffold_enforcement_carry=["backend/models.py is frozen: restored to the scaffold"],
            repair_rejections=["round 0's repair was refused: endpoint_defined still failed"],
        ),
        "refuted_claim_reaches_the_decision": _Case(
            analysis={
                **_ANALYSIS,
                "analysis_summary": (
                    "The handler in backend/services/run_service.py returns the wrong shape. "
                    "The routes module never registers GET /api/runs."
                ),
            }
        ),
        "repair_alone_declared": _Case(steps=["repair"]),
        "contested_row_left_unruled": _Case(disputes=[_DISPUTE]),
        "contested_row_confirmed": _Case(
            disputes=[_DISPUTE],
            analysis={
                **_ANALYSIS,
                "dispute_rulings": [
                    {
                        "check": "endpoint_defined",
                        "dispute_confirmed": True,
                        "reason": "the contract names /api/v1/runs",
                    }
                ],
            },
        ),
        "reserve_ends_the_round": _Case(
            required_checks=["acceptance:tests_pass"], correction_attempts=2, correction_budget=3
        ),
    }


def _failed_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        task_id=_FAILED_TASK_ID,
        agent_id="neo",
        cycle_id="cyc_char",
        pulse_id="p1",
        project_id="proj",
        task_type="development.develop",
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
        inputs=copy.deepcopy(_FAILED_INPUTS),
        metadata={"role": "dev"},
    )


def _failed_result() -> TaskResult:
    return TaskResult(
        task_id=_FAILED_TASK_ID,
        status="FAILED",
        outputs={
            "outcome_class": "SEMANTIC_FAILURE",
            "failure_classification": "work_product",
            "validation_result": {
                "passed": False,
                "summary": "1/2 checks passed",
                "missing_components": [],
                "checks": [
                    {
                        "check": "endpoint_defined",
                        "passed": False,
                        "detail": "GET /api/runs missing",
                    },
                    {"check": "expected_artifacts", "passed": True},
                ],
            },
            "artifacts": [
                {"name": "backend/routes.py", "type": "source", "content": "def broken(): ..."}
            ],
        },
        error="validation failed",
    )


def _cycle(case: _Case) -> SimpleNamespace:
    config: dict[str, Any] = {"correction_steps": list(case.steps)}
    if case.required_checks:
        config["required_checks"] = list(case.required_checks)
    return SimpleNamespace(
        cycle_id="cyc_char",
        project_id="proj",
        prd_ref="PRD-CONTENT",
        resolved_config=lambda: copy.deepcopy(config),
        campaign_id=None,
        execution_overrides={},
        applied_defaults={},
    )


def _plain(value: Any) -> Any:
    """The JSON form the golden holds: tuples read back as lists, anything else as its text."""
    return json.loads(json.dumps(value, default=str))


def _envelope_record(envelope: TaskEnvelope) -> dict[str, Any]:
    return {
        "task_id": envelope.task_id,
        "agent_id": envelope.agent_id,
        "task_type": envelope.task_type,
        "correlation_id": envelope.correlation_id,
        "causation_id": envelope.causation_id,
        "trace_id": envelope.trace_id,
        "span_id": envelope.span_id,
        "pulse_id": envelope.pulse_id,
        "metadata": copy.deepcopy(envelope.metadata),
        "input_keys": list(envelope.inputs or {}),
        "inputs": copy.deepcopy(envelope.inputs),
    }


async def _run_case(case: _Case, monkeypatch, manifest: InterfaceManifest) -> dict[str, Any]:
    event_bus = MagicMock()
    runner = CorrectionRunner(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        event_bus=event_bus,
        task_dispatcher=AsyncMock(),
        store_artifact=AsyncMock(),
        failure_recall=NoOpFailurePatternRecall(),
    )
    outputs_by_type = {
        "data.analyze_failure": case.analysis,
        "governance.correction_decision": _DECISION,
    }
    steps: list[dict[str, Any]] = []

    async def _capture_dispatch(step_envelope, *args, **kwargs):
        # Captured at dispatch: ``prior_outputs`` and the artifact refs mutate between steps.
        steps.append(_envelope_record(step_envelope))
        outputs = copy.deepcopy(outputs_by_type.get(step_envelope.task_type, {"artifacts": []}))
        return TaskResult(task_id=step_envelope.task_id, status="SUCCEEDED", outputs=outputs)

    monkeypatch.setattr(runner, "_dispatch_protocol_step", _capture_dispatch)
    # One counter for every uuid the round draws, in the runner (a local import) and in the
    # repair half (a module import), so the ids record the order they were drawn in.
    counter = itertools.count()

    def _uuid4() -> SimpleNamespace:
        return SimpleNamespace(hex=f"{next(counter):032d}")

    monkeypatch.setattr("uuid.uuid4", _uuid4)
    monkeypatch.setattr("squadops.execution.correction_repair.uuid4", _uuid4)

    ledger = RunLedger()
    returned = raised = None
    try:
        protocol = await runner.run_correction_protocol(
            run_id=_RUN_ID,
            cycle=_cycle(case),
            envelope=_failed_envelope(),
            result=_failed_result(),
            correction_attempts=case.correction_attempts,
            prior_outputs={"dev": {"summary": "[dev] built"}},
            all_artifact_refs=["art_routes"],
            stored_artifacts=[],
            completed_task_ids=[_FAILED_TASK_ID],
            plan_delta_refs=[],
            profile=_PROFILE,
            correction_budget=case.correction_budget,
            flow_run_id="flow_char",
            interface_manifest=manifest if case.with_manifest else None,
            artifact_contents=None,
            scaffold_enforcement_carry=case.scaffold_enforcement_carry,
            budget_guard=None,
            signature_state={},
            ledger=ledger,
            repair_rejections=case.repair_rejections,
            has_accepted_repair=False,
            dispute_carry={_FAILED_TASK_ID: list(case.disputes)} if case.disputes else {},
            round_seq=0,
        )
        returned = dataclasses.asdict(protocol)
    except _ExecutionError as exc:
        raised = {
            "error": str(exc),
            "terminal": dataclasses.asdict(exc.terminal) if exc.terminal else None,
        }
    events = [
        {
            "event": str(call.args[0]),
            "entity_type": call.kwargs.get("entity_type"),
            "entity_id": call.kwargs.get("entity_id"),
            "context": call.kwargs.get("context"),
            "payload": call.kwargs.get("payload"),
        }
        for call in event_bus.emit.call_args_list
    ]
    return _plain(
        {
            "steps": steps,
            "events": events,
            "round_failures": [rf.to_dict() for rf in ledger.round_failures],
            "returned": returned,
            "raised": raised,
        }
    )


@pytest.fixture(scope="module")
def manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    if os.environ.get("UPDATE_CORRECTION_DIAGNOSIS_GOLDENS") or not _GOLDEN_PATH.exists():
        return {}
    return json.loads(_GOLDEN_PATH.read_text())


@pytest.mark.parametrize("case_name", list(_cases()))
async def test_the_diagnosis_matches_its_golden(case_name, golden, manifest, monkeypatch):
    observed = await _run_case(_cases()[case_name], monkeypatch, manifest)
    if os.environ.get("UPDATE_CORRECTION_DIAGNOSIS_GOLDENS"):
        recorded = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
        recorded[case_name] = observed
        _GOLDEN_PATH.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n")
        pytest.skip("golden regenerated")
    assert case_name in golden, f"no golden for {case_name}: regenerate deliberately"
    assert observed == golden[case_name]


def _step(observed: dict[str, Any], task_type: str) -> dict[str, Any]:
    (step,) = [s for s in observed["steps"] if s["task_type"] == task_type]
    return step


async def test_the_decision_is_told_the_claims_the_workspace_refutes(manifest, monkeypatch):
    """Bug caught: the refutation attached to the analysis step, or to no step, after the move.
    Only a step after the analysis can carry it, and it names the path the workspace lacks."""
    observed = await _run_case(
        _cases()["refuted_claim_reaches_the_decision"], monkeypatch, manifest
    )
    analyze = _step(observed, "data.analyze_failure")
    decide = _step(observed, "governance.correction_decision")
    assert "refuted_source_claims" not in analyze["inputs"]
    assert [c["path"] for c in decide["inputs"]["refuted_source_claims"]] == [
        "backend/services/run_service.py"
    ]
    assert decide["inputs"]["failure_analysis"] == _plain(
        _cases()["refuted_claim_reaches_the_decision"].analysis
    )


async def test_the_reserve_ends_the_round_after_recording_it_and_before_any_dispatch(
    manifest, monkeypatch
):
    """Bug caught: the reserve checked after a step dispatches (the round would spend an attempt
    it is refused), or before the round failure is recorded (the round would vanish from the
    run's record)."""
    observed = await _run_case(_cases()["reserve_ends_the_round"], monkeypatch, manifest)
    assert observed["steps"] == []
    assert observed["raised"]["error"].startswith("reserved_for_required:")
    assert [rf["failed_checks"] for rf in observed["round_failures"]] == [["endpoint_defined"]]
    assert [e["event"] for e in observed["events"]] == ["correction.initiated"]


async def test_every_step_of_one_round_shares_its_correlation_id(manifest, monkeypatch):
    """Bug caught: the correlation id drawn per step after the loop body moves, which breaks the
    lineage a trace of the round is read by."""
    observed = await _run_case(
        _cases()["full_protocol_with_carried_evidence"], monkeypatch, manifest
    )
    assert len(observed["steps"]) >= 3
    assert len({s["correlation_id"] for s in observed["steps"]}) == 1
    assert {s["causation_id"] for s in observed["steps"]} == {_FAILED_TASK_ID}
