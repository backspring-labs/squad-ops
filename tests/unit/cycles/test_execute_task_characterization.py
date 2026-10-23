"""The executor's per-task method, characterized before #1994 breaks it into named steps.

#1994's third piece breaks ``DispatchedFlowExecutor._execute_task`` (313 lines) into named steps
(the extraction map's §4c): its three routing closures become a per-task router, the patched-result
swap and the failure bookkeeping one of the router's steps, the success tail
``_after_task_success`` and the dispatch announcement ``_announce_dispatch``. That is a move: no
event, no call to a collaborator or any of its arguments, no ledger row and no change to the run's
state may differ, and none may change order.

These cases drive the real method with a real ``RunState`` and ``RunLedger`` and record every call it
makes, in order, against a golden captured from the code BEFORE the move. Two collaborators are
scripted:
- the dispatcher's ``dispatch_with_retry``, which acts on a routing action as the real one does
  (``task_dispatcher.py``: route a failed attempt, re-dispatch on ``continue``, return on
  ``accept_patch`` or ``break_correction``);
- ``_handle_task_outcome``, which returns each case's actions.

Every other collaborator the method calls is a recorder on the instance, or on this module's name
for ``supply_the_redispatch``. The steps keep calling each of them through the executor and this
module, so the move can't need a test edit.

Bug caught: a router that hands the routing decision a different failure count than the run held
when the task started (the count is never raised, #2348, so this pins the value handed over); a
held result that is no longer the dict the repair writes into, so an accepted patch is
never swapped in and the failed result is collected; a failed result held before it is admitted
(#1323); the abort path recording nothing, or a completion recorded twice; a kept-progress round's
failed attempt unrecorded, or re-dispatched; a failure the correction lets through that still
collects, binds or opens a gate; a re-dispatch that no longer asks for its lessons (#2162); the
success tail reordered (the bind before the collection, the gate before the pulse checks); or the
dispatched event's context or payload changed.

Regenerate (only for a DELIBERATE behaviour change, in the PR that makes it):
    UPDATE_EXECUTE_TASK_GOLDENS=1 pytest tests/unit/cycles/test_execute_task_characterization.py
"""

from __future__ import annotations

import dataclasses
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from adapters.noop.ports import NoOpFailurePatternRecall, NoOpProposalEvidence
from squadops.cycles.emission_integrity import EMISSION_FAILURE_KEY
from squadops.cycles.models import Cycle, Gate, TaskFlowPolicy
from squadops.cycles.run_ledger import RunLedger
from squadops.execution import dispatched_flow_executor as dfe
from squadops.execution.dispatched_flow_executor import (
    DispatchedFlowExecutor,
    RunState,
    _Budget,
    _ExecutionError,
    _PulseContext,
)
from squadops.execution.patch_acceptance import KEEP_PROGRESS
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus

pytestmark = [pytest.mark.domain_orchestration]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "execute_task_characterization.json"
_GATE_AFTER = "development.develop"


def _envelope(task_id: str, task_type: str, role: str) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        agent_id=f"{role}-agent",
        cycle_id="cyc_char",
        pulse_id="pulse_1",
        project_id="proj_char",
        task_type=task_type,
        correlation_id="corr_1",
        causation_id="cause_1",
        trace_id="trace_1",
        span_id="span_1",
        inputs={"prior_attempts": 1},
        metadata={"role": role},
    )


def _result(label: str, *, ok: bool, check_status: str, absent: bool = False) -> TaskResult:
    outputs: dict[str, Any] = {
        "label": label,
        "validation_result": {
            "checks": [
                {
                    "check": "endpoint_defined",
                    "status": check_status,
                    "reason": None if check_status == "passed" else f"{label}: route missing",
                    "criterion_id": "c-1",
                }
            ]
        },
    }
    if absent:
        outputs[EMISSION_FAILURE_KEY] = {"signature": f"{label}-no-file"}
    return TaskResult(
        task_id="t-dev",
        status=TaskResultStatus.SUCCEEDED if ok else TaskResultStatus.FAILED,
        outputs=outputs,
        error=None if ok else f"{label} failed",
    )


def _failed(label: str, *, absent: bool = False) -> TaskResult:
    return _result(label, ok=False, check_status="failed", absent=absent)


def _passed(label: str) -> TaskResult:
    return _result(label, ok=True, check_status="passed")


class _Trace:
    """Every call, in order, with its arguments by name: objects by identity, values as they are."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.names: dict[int, str] = {}

    def name(self, obj: Any, label: str) -> None:
        self.names[id(obj)] = label

    def label(self, value: Any) -> Any:
        if id(value) in self.names:
            return self.names[id(value)]
        if isinstance(value, TaskResult):
            return f"result:{(value.outputs or {}).get('label')}"
        if value is None or isinstance(value, bool | int | float | str):
            return value
        if isinstance(value, tuple | list):
            return [self.label(v) for v in value]
        if isinstance(value, set | frozenset):
            return sorted(str(self.label(v)) for v in value)
        if isinstance(value, dict):
            return {str(k): self.label(v) for k, v in value.items()}
        return type(value).__name__

    def add(self, call: str, **args: Any) -> None:
        self.calls.append({"call": call, **{k: self.label(v) for k, v in args.items()}})


class _ScriptedDispatcher:
    """``create_task_run_if_enabled`` and ``dispatch_with_retry``, acting on a routing action as
    the real dispatcher does."""

    def __init__(self, trace: _Trace, attempts: list[TaskResult]) -> None:
        self._trace = trace
        self._attempts = list(attempts)

    async def create_task_run_if_enabled(self, flow_run_id, envelope):
        self._trace.add("create_task_run_if_enabled", flow_run_id=flow_run_id, envelope=envelope)
        return "tr_char"

    async def dispatch_with_retry(
        self, enriched, envelope, cycle, run_id, *, flow_run_id, task_run_id, handle_task_outcome
    ):
        self._trace.add(
            "dispatch_with_retry",
            enriched=enriched,
            envelope=envelope,
            cycle=cycle,
            run_id=run_id,
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
        )
        while True:
            result = self._attempts.pop(0)
            self._trace.add("attempt", result=result)
            if result.status != TaskResultStatus.SUCCEEDED:
                action = await handle_task_outcome(result)
                self._trace.add("routed", action=action)
                if action == "continue":
                    continue
                if action == "accept_patch":
                    return True, result
                if action == "break_correction":
                    return False, result
            return True, result


class _EventBus:
    def __init__(self, trace: _Trace) -> None:
        self._trace = trace

    def emit(self, event_type, *, entity_type, entity_id, context, payload):
        self._trace.add(
            "emit",
            event_type=str(event_type),
            entity_type=entity_type,
            entity_id=entity_id,
            context=context,
            payload=payload,
        )


class _PulseRunner:
    def __init__(self, trace: _Trace, cadence_closed: bool) -> None:
        self._trace = trace
        self._cadence_closed = cadence_closed

    def evaluate_pulse_boundaries(self, **kwargs):
        self._trace.add("evaluate_pulse_boundaries", **kwargs)
        return self._cadence_closed

    async def run_pulse_evaluations(self, **kwargs):
        self._trace.add("run_pulse_evaluations", **kwargs)


@dataclasses.dataclass
class _Case:
    """One task's run: what the preconditions say, what each dispatch returns, how each failed
    attempt is routed, and the run's state going in."""

    declined: bool = False
    attempts: list[TaskResult] = dataclasses.field(default_factory=list)
    #: per routed attempt: an action, or ``("accept_patch", patched)``, or ``"abort"``
    actions: list[Any] = dataclasses.field(default_factory=list)
    kept: list[TaskResult] = dataclasses.field(default_factory=list)
    pulse_checks: bool = False
    cadence_closed: bool = False


def _cases() -> dict[str, _Case]:
    return {
        "declined_by_a_precondition": _Case(declined=True),
        "first_try_success_with_pulse_and_gate": _Case(
            attempts=[_passed("ok")], pulse_checks=True, cadence_closed=True
        ),
        "re_dispatched_then_success": _Case(
            attempts=[_failed("first"), _passed("second")],
            actions=["continue"],
            pulse_checks=True,
        ),
        "repair_accepted": _Case(
            attempts=[_failed("first", absent=True)],
            actions=[("accept_patch", _passed("patched"))],
        ),
        "kept_progress_then_accepted": _Case(
            attempts=[_failed("first")],
            actions=[KEEP_PROGRESS, ("accept_patch", _passed("patched"))],
            kept=[_failed("retest-on-kept")],
        ),
        "failure_let_through": _Case(attempts=[_failed("first")], actions=["break_correction"]),
        "abort_from_inside_the_dispatch": _Case(attempts=[_failed("first")], actions=["abort"]),
    }


def _cycle() -> Cycle:
    return Cycle(
        cycle_id="cyc_char",
        project_id="proj_char",
        created_at=datetime(2026, 10, 15, tzinfo=UTC),
        created_by="system",
        prd_ref="prd_char",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:char",
        task_flow_policy=TaskFlowPolicy(
            mode="sequential",
            gates=(Gate(name="review", description="after dev", after_task_types=(_GATE_AFTER,)),),
        ),
        build_strategy="fresh",
        applied_defaults={},
    )


def _name_state(trace: _Trace, state: RunState) -> None:
    trace.name(state, "state")
    for group in ("produced", "checkpoint", "routing", "correction", "ownership", "cadence"):
        holder = getattr(state, group)
        for field in dataclasses.fields(holder):
            value = getattr(holder, field.name)
            if isinstance(value, dict | list | set):
                trace.name(value, f"state.{group}.{field.name}")


class _Recorders:
    """The leaf collaborators ``_execute_task`` calls, each recording its arguments. Two answer from
    the case: the preconditions (declined or not) and ``_handle_task_outcome`` (each routed
    attempt's action)."""

    def __init__(self, trace: _Trace, case: _Case) -> None:
        self._trace = trace
        self._case = case
        self._actions = list(case.actions)
        self._kept = list(case.kept)

    async def check_task_preconditions(self, run_id, envelope, skip, seconds, started, completed):
        self._trace.add(
            "check_task_preconditions",
            run_id=run_id,
            envelope=envelope,
            skip_task_ids=skip,
            budget_seconds=seconds,
            budget_started=started,
            completed_task_ids=completed,
        )
        return self._case.declined

    async def enrich_envelope(
        self, envelope, prior, refs, stored, *, interface_manifest, run_derived_contract
    ):
        self._trace.add(
            "enrich_envelope",
            envelope=envelope,
            prior_outputs=prior,
            all_artifact_refs=refs,
            stored_artifacts=stored,
            interface_manifest=interface_manifest,
            run_derived_contract=run_derived_contract,
        )
        enriched = dataclasses.replace(envelope, inputs={**envelope.inputs, "chain": "enriched"})
        self._trace.name(enriched, "enriched")
        return enriched

    async def admit_failed_emission(
        self, result, envelope, cycle, run_id, refs, *, bound_record, compliance_counter
    ):
        self._trace.add(
            "admit_failed_emission",
            result=result,
            envelope=envelope,
            cycle=cycle,
            run_id=run_id,
            all_artifact_refs=refs,
            bound_record=bound_record,
            compliance_counter=compliance_counter,
        )
        label = f"{result.outputs['label']}+admitted"
        return dataclasses.replace(result, outputs={**result.outputs, "label": label})

    async def handle_task_outcome(self, **kwargs):
        holder = kwargs["patched_result_holder"]
        if id(holder) not in self._trace.names:
            self._trace.name(holder, "held")
        self._trace.add("handle_task_outcome", **kwargs)
        action = self._actions.pop(0)
        if action == "abort":
            raise _ExecutionError("Correction protocol decided to abort")
        if isinstance(action, tuple):
            action, patched = action
            holder["patched_result"] = patched
        return action

    async def store_kept_progress(self, holder, envelope, enriched, cycle, run_id, state, **kwargs):
        self._trace.add(
            "store_kept_progress",
            holder=holder,
            envelope=envelope,
            enriched=enriched,
            cycle=cycle,
            run_id=run_id,
            state=state,
            **kwargs,
        )
        return self._kept.pop(0)

    async def supply_the_redispatch(self, pair, *, recall, cycle, run_id, now):
        self._trace.add(
            "supply_the_redispatch", pair=pair, recall=recall, cycle=cycle, run_id=run_id
        )

    async def collect_artifacts_and_checkpoint(self, **kwargs):
        self._trace.add("collect_artifacts_and_checkpoint", **kwargs)

    async def bind_authored_manifest(self, cycle, run_id, stored, authored):
        self._trace.add(
            "bind_authored_manifest",
            cycle=cycle,
            run_id=run_id,
            stored_artifacts=stored,
            authored=authored,
        )
        return ("bound-contract", "bound-manifest")

    async def handle_gate(self, run_id, cycle, task_type, *, stored_artifacts, profile):
        self._trace.add(
            "handle_gate",
            run_id=run_id,
            cycle=cycle,
            task_type=task_type,
            stored_artifacts=stored_artifacts,
            profile=profile,
        )


def _executor(trace: _Trace, case: _Case, monkeypatch) -> DispatchedFlowExecutor:
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        failure_recall=NoOpFailurePatternRecall(),
        proposal_evidence=NoOpProposalEvidence(),
    )
    trace.name(executor._failure_recall, "failure_recall")
    executor._task_dispatcher = _ScriptedDispatcher(trace, case.attempts)
    executor._cycle_event_bus = _EventBus(trace)
    executor._pulse_boundary_runner = _PulseRunner(trace, case.cadence_closed)
    rec = _Recorders(trace, case)
    executor._check_task_preconditions = rec.check_task_preconditions
    executor._enrich_envelope = rec.enrich_envelope
    executor._admit_failed_emission = rec.admit_failed_emission
    executor._handle_task_outcome = rec.handle_task_outcome
    executor._store_kept_progress = rec.store_kept_progress
    executor._collect_artifacts_and_checkpoint = rec.collect_artifacts_and_checkpoint
    executor._bind_authored_manifest = rec.bind_authored_manifest
    executor._handle_gate = rec.handle_gate
    monkeypatch.setattr(dfe, "supply_the_redispatch", rec.supply_the_redispatch)
    return executor


async def _run_case(case: _Case, monkeypatch) -> dict[str, Any]:
    trace = _Trace()
    executor = _executor(trace, case, monkeypatch)
    dev = _envelope("t-dev", _GATE_AFTER, "dev")
    qa = _envelope("t-qa", "qa.test", "qa")
    state = RunState(budget=_Budget(seconds=3600.0, started=100.0))
    state.cadence.started = 50.0
    ledger = RunLedger()
    cycle = _cycle()
    profile = object()
    pulse = _PulseContext(
        milestone_bindings={"m": "suite"},
        cadence_suites=["cadence-suite"],
        has_checks=case.pulse_checks,
        cadence="every_task",
        engine=object() if case.pulse_checks else None,
    )
    for obj, label in (
        (executor, "executor"),
        (dev, "envelope"),
        (qa, "next-envelope"),
        (ledger, "ledger"),
        (cycle, "cycle"),
        (profile, "profile"),
        (pulse.engine, "pulse_engine"),
        (pulse.milestone_bindings, "milestone_bindings"),
        (pulse.cadence_suites, "cadence_suites"),
    ):
        if obj is not None:
            trace.name(obj, label)
    _name_state(trace, state)
    plan = [dev, qa]
    trace.name(plan, "plan")

    def budget_guard() -> None:
        return None

    trace.name(budget_guard, "budget_guard")
    raised = None
    try:
        await executor._execute_task(
            state,
            dev,
            task_idx=0,
            plan=plan,
            cycle=cycle,
            run_id="run_char",
            flow_run_id="flow_char",
            profile=profile,
            run_root="/runs/run_char",
            obs_ctx="obs",
            ledger=ledger,
            interface_manifest=None,
            pulse=pulse,
            budget_guard=budget_guard,
        )
    except _ExecutionError as exc:
        raised = f"{type(exc).__name__}: {exc}"
    observed = {
        "calls": trace.calls,
        "raised": raised,
        "ledger_check_results": [
            json.loads(json.dumps(dataclasses.asdict(r), default=str)) for r in ledger.check_results
        ],
        "ledger_absent_emissions": [dataclasses.asdict(a) for a in ledger.absent_emissions],
        "state_after": {
            "accepted_repair_task_ids": sorted(state.correction.accepted_repair_task_ids),
            "cadence_task_count": state.cadence.task_count,
            "cadence_interval_id": state.cadence.interval_id,
            "cadence_restarted": state.cadence.started != 50.0,
            "authored": list(state.authored),
        },
    }
    # The golden is JSON: tuples read back as lists, so the observation is compared in that form.
    return json.loads(json.dumps(observed, default=str))


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    if os.environ.get("UPDATE_EXECUTE_TASK_GOLDENS") or not _GOLDEN_PATH.exists():
        return {}
    return json.loads(_GOLDEN_PATH.read_text())


@pytest.mark.parametrize("case_name", list(_cases()))
async def test_execute_task_matches_its_golden(case_name, golden, monkeypatch):
    observed = await _run_case(_cases()[case_name], monkeypatch)
    if os.environ.get("UPDATE_EXECUTE_TASK_GOLDENS"):
        recorded = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
        recorded[case_name] = observed
        _GOLDEN_PATH.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n")
        pytest.skip("golden regenerated")
    assert case_name in golden, f"no golden for {case_name}: regenerate deliberately"
    assert observed == golden[case_name]


def _calls(observed: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [c for c in observed["calls"] if c["call"] == name]


async def test_an_accepted_repair_is_collected_in_place_of_the_failed_result(monkeypatch):
    """#389: the repair writes its verified result into the held dict, and the swap after the
    dispatch takes it from that same dict. If the router held a different dict, the failed
    attempt would be collected and the ledger's last word on the check would be the failure."""
    observed = await _run_case(_cases()["repair_accepted"], monkeypatch)
    (collect,) = _calls(observed, "collect_artifacts_and_checkpoint")
    assert collect["result"] == "result:patched"
    assert [(r["status"], r["reason"]) for r in observed["ledger_check_results"]] == [
        ("failed", "first: route missing"),
        ("passed", None),
    ]


async def test_an_abort_records_the_held_result_once_and_re_raises(monkeypatch):
    """SIP-0096 §6.4: an abort raised inside the dispatch still records the failing attempt (the
    admitted one, #1323), exactly once, and nothing after the dispatch runs."""
    observed = await _run_case(_cases()["abort_from_inside_the_dispatch"], monkeypatch)
    assert observed["raised"] == "_ExecutionError: Correction protocol decided to abort"
    assert [(r["status"], r["subject"]) for r in observed["ledger_check_results"]] == [
        ("failed", "t-dev")
    ]
    assert _calls(observed, "collect_artifacts_and_checkpoint") == []
    assert _calls(observed, "handle_gate") == []
