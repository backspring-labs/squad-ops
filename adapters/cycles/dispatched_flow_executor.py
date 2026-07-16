"""
Dispatched flow executor adapter.

Dispatches cycle tasks to agent containers via RabbitMQ instead of
executing them in-process.  Each agent handles its own task using
its own LLM model and PromptService.

Mirrors InProcessFlowExecutor structure (SIP-0066) but replaces
``orchestrator.submit_task()`` with a publish→consume request/reply
pattern over the ``{agent_id}_comms`` queue.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import time
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from adapters.cycles.correction_runner import CorrectionRunner
from adapters.cycles.execution_errors import (
    _CancellationError,
    _ExecutionError,
    _PausedError,
    _RecruitmentRejectedError,
)
from adapters.cycles.pulse_boundary_runner import PulseBoundaryRunner
from adapters.cycles.run_completion import RunCompletion, resolve_terminal_outcome
from adapters.cycles.task_dispatcher import TaskDispatcher
from adapters.cycles.task_naming import build_task_name
from squadops.cycles.agent_config import build_agent_resolver
from squadops.cycles.build_completeness import compute_missing_required_files
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import ArtifactRef, Cycle, GateDecisionValue, Run, RunStatus
from squadops.cycles.naming import flow_run_name
from squadops.cycles.patch_verification import (
    PATCH_PASSED,
    overlay_artifacts,
    verify_patched_artifacts,
)
from squadops.cycles.run_ledger import RunLedger
from squadops.cycles.task_outcome import TaskOutcome
from squadops.cycles.task_plan import generate_task_plan
from squadops.cycles.verification_normalize import normalize_task_checks
from squadops.events.types import EventType
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.runtime.admission import admit_participants, release_participants
from squadops.runtime.recruitment import reserve_buffer_decision
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus
from squadops.telemetry.context import use_correlation_context
from squadops.telemetry.models import CorrelationContext

if TYPE_CHECKING:
    from adapters.cycles.reply_router import ReplyRouter
    from squadops.cycles.models import GateDecision, SquadProfile
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.cycles.squad_profile import SquadProfilePort
    from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort
    from squadops.ports.runtime.activity import RuntimeActivityPort
    from squadops.ports.runtime.assignments import AssignmentPort
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
    from squadops.runtime.coordinator import RuntimeCoordinator

logger = logging.getLogger(__name__)


class DispatchedFlowExecutor(FlowExecutionPort):
    """Flow executor that dispatches tasks to agent containers via RabbitMQ.

    Uses a request/reply pattern: publishes a ``comms.task`` message to
    ``{agent_id}_comms``, then awaits the ``TaskResult`` via the
    :class:`ReplyRouter`, which holds a long-lived subscription on the agent's
    per-agent reply queue (``{agent_id}_replies``) and resolves a future keyed
    by ``task_id`` (SIP-0094).
    """

    def __init__(
        self,
        cycle_registry: CycleRegistryPort | None = None,
        artifact_vault: ArtifactVaultPort | None = None,
        queue: QueuePort | None = None,
        squad_profile: SquadProfilePort | None = None,
        project_registry: ProjectRegistryPort | None = None,
        task_timeout: float = 300.0,
        llm_observability: LLMObservabilityPort | None = None,
        workflow_tracker: WorkflowTrackerPort | None = None,
        event_bus: CycleEventBusPort | None = None,
        reply_router: ReplyRouter | None = None,
        assignment_port: AssignmentPort | None = None,
        activity_port: RuntimeActivityPort | None = None,
        coordinator: RuntimeCoordinator | None = None,
        run_completion: RunCompletion | None = None,
        correction_runner: CorrectionRunner | None = None,
        pulse_boundary_runner: PulseBoundaryRunner | None = None,
        task_dispatcher: TaskDispatcher | None = None,
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._queue = queue
        self._reply_router = reply_router
        self._squad_profile = squad_profile
        self._project_registry = project_registry
        self._task_timeout = task_timeout
        self._llm_observability = llm_observability
        self._workflow_tracker = workflow_tracker
        # SIP-0089 §2.5: reserve-buffer guard dependency. Opt-in — when None,
        # the guard is skipped entirely (safe no-op until an AssignmentPort is
        # wired in the composition root).
        self._assignment_port = assignment_port
        # SIP-0089 §4.4 (executor-side instrumentation): opt-in RuntimeActivityPort.
        # When wired, each dispatched task opens a RuntimeActivity (start on
        # dispatch, complete/fail on reply) so an agent's current task is
        # observable. Best-effort — never breaks dispatch; None disables it.
        self._activity_port = activity_port
        # SIP-0089 §3.5 (#233): opt-in RuntimeCoordinator. When wired, recruitment
        # routes each participant ambient→cycle through the coordinator (acquiring
        # the cycle FocusLease) after the §2.5 guard passes, and releases them on
        # finalize. When None (memory registry / lite local cycles), recruitment
        # falls back to §2.5-only — a cycle never hard-fails for missing runtime
        # infra.
        self._coordinator = coordinator
        self._cancelled: set[str] = set()
        # SIP-0097 §6.4: run-completion collaborator (terminal path). Plain
        # injected collaborator with a default composed from this executor's
        # own deps — not a port.
        self._run_completion = run_completion or RunCompletion(
            cycle_registry=cycle_registry,
            artifact_vault=artifact_vault,
            llm_observability=llm_observability,
            workflow_tracker=workflow_tracker,
        )

        # SIP-0077: Cycle event bus (defaults to NoOp if not provided)
        if event_bus is None:
            from adapters.events.noop_cycle_event_bus import NoOpCycleEventBus

            event_bus = NoOpCycleEventBus()
        self._cycle_event_bus = event_bus
        # SIP-0097 §6.1: task-dispatch collaborator (request/reply transport +
        # per-task observability). Composed first — the correction and pulse
        # runners below depend on it (the §6 final dependency graph; the
        # slice-3/4 interim dispatch callables are retired per AC#9).
        self._task_dispatcher = task_dispatcher or TaskDispatcher(
            queue=queue,
            reply_router=reply_router,
            workflow_tracker=workflow_tracker,
            activity_port=activity_port,
            event_bus=event_bus,
            task_timeout=task_timeout,
        )
        # SIP-0097 §6.3: correction-protocol collaborator. store_artifact stays
        # an executor-supplied late-bound callable (artifact plumbing is §6.7
        # executor residual, residual-but-watched).
        self._correction_runner = correction_runner or CorrectionRunner(
            cycle_registry=cycle_registry,
            artifact_vault=artifact_vault,
            event_bus=event_bus,
            task_dispatcher=self._task_dispatcher,
            store_artifact=lambda *args, **kw: self._store_artifact(*args, **kw),
        )
        # SIP-0097 §6.2: pulse-boundary collaborator (boundary verification +
        # bounded repair loop). LLM observability is event-emission-only per
        # the observability ownership rule.
        self._pulse_boundary_runner = pulse_boundary_runner or PulseBoundaryRunner(
            cycle_registry=cycle_registry,
            event_bus=event_bus,
            llm_observability=llm_observability,
            task_dispatcher=self._task_dispatcher,
            store_artifact=lambda *args, **kw: self._store_artifact(*args, **kw),
        )
        # SIP-0097 §6.6: per-run pulse summaries live on the RunLedger created
        # in execute_run() and passed explicitly; multi-workload forwarding
        # overrides are threaded execute_cycle() → execute_run() as a
        # parameter. The executor carries no per-run/per-cycle mutable
        # instance state (self._cancelled is the one cross-run exception).

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_run(
        self,
        cycle_id: str,
        run_id: str,
        profile_id: str | None = None,
        *,
        forwarding_overrides: dict | None = None,
    ) -> None:
        """Execute a run by dispatching tasks to agent containers via RabbitMQ.

        ``forwarding_overrides`` is an adapter-internal keyword extension
        (SIP-0083 multi-workload forwarding, threaded from execute_cycle();
        SIP-0097 §6.6 — an immutable cycle-scoped value, never stored on the
        executor). Port callers use the positional FlowExecutionPort signature.
        """
        obs_ctx = None
        flow_run_id = None
        terminal_status = "COMPLETED"
        ledger = RunLedger()
        cycle = None
        plan = None
        # SIP-0089 §3.5 (#233): agents this run transitioned ambient→cycle, to be
        # returned to ambient (releasing their cycle lease) in the finally. Stays
        # empty when recruitment defers (admission rolls its own recruits back) or
        # when no coordinator is wired.
        recruited_agent_ids: tuple[str, ...] = ()

        try:
            cycle, run_root = await self._prepare_cycle_for_run(
                cycle_id, run_id, forwarding_overrides=forwarding_overrides
            )
            run = await self._cycle_registry.get_run(run_id)
            profile, _ = await self._squad_profile.resolve_snapshot(profile_id)

            # queued/failed/paused -> running. Skipped when already RUNNING:
            # the resume/retry routes flip the run to RUNNING before enqueuing
            # execution (#222/#256), and RUNNING -> RUNNING is an illegal
            # transition — the unconditional call instantly failed every
            # resumed run on a lifecycle-enforcing registry (#342).
            if run.status != RunStatus.RUNNING.value:
                await self._cycle_registry.update_run_status(run_id, RunStatus.RUNNING)

            # SIP-0079: Check if resuming from checkpoint
            existing_checkpoint = await self._cycle_registry.get_latest_checkpoint(run_id)
            if existing_checkpoint:
                self._cycle_event_bus.emit(
                    EventType.RUN_RESUMED,
                    entity_type="run",
                    entity_id=run_id,
                    context={
                        "cycle_id": cycle_id,
                        "run_id": run_id,
                        "project_id": cycle.project_id,
                    },
                    payload={"checkpoint_index": existing_checkpoint.checkpoint_index},
                )
            else:
                self._cycle_event_bus.emit(
                    EventType.RUN_STARTED,
                    entity_type="run",
                    entity_id=run_id,
                    context={
                        "cycle_id": cycle_id,
                        "run_id": run_id,
                        "project_id": cycle.project_id,
                    },
                )

            # SIP-0086 / SIP-0092: Load implementation plan for implementation
            # workloads. The plan is produced by the planning workload and
            # forwarded via plan_artifact_refs. Loading it here (not mid-loop)
            # keeps the executor deterministic — the plan is fully materialized
            # before task dispatch begins.
            implementation_plan = await self._load_plan_for_run(cycle, run)

            plan = generate_task_plan(cycle, run, profile, plan=implementation_plan)
            participating_agent_ids = {e.agent_id for e in plan}

            # SIP-0089 §2.5: reserve-buffer guard. The plan now names every
            # agent this run would recruit. If one is committed to — or about to
            # start — a hard duty window (§11.4), defer the run rather than pull
            # the agent into cycle work. Opt-in: skipped when no AssignmentPort
            # is wired. Decision is pure (time-injected) and lives in the runtime
            # domain; we only enforce it here.
            if self._assignment_port is not None:
                guard_now = datetime.now(UTC)
                active_assignments = await self._assignment_port.list_active_assignments(guard_now)
                decision = reserve_buffer_decision(
                    active_assignments,
                    participating_agent_ids,
                    guard_now,
                )
                if not decision.allowed:
                    raise _RecruitmentRejectedError(decision.blocking_agent_id, decision.reason)

            # SIP-0089 §3.5 (#233): having cleared the reserve-buffer guard, route
            # recruitment through the coordinator — each participant transitions
            # ambient→cycle, acquiring its cycle FocusLease (§3.4). A lease
            # conflict is a deferral, not a failure: it rides the same
            # _RecruitmentRejectedError → RUN_PAUSED path with a typed focus_lease_*
            # reason (no new EventType). admission rolls back any agents it already
            # recruited before deferring, so a paused run strands no one in cycle.
            # Opt-in: skipped when no coordinator is wired (§2.5-only fallback).
            if self._coordinator is not None:
                admission = await admit_participants(
                    self._coordinator,
                    participating_agent_ids,
                    owner_ref=run_id,
                )
                if not admission.admitted:
                    raise _RecruitmentRejectedError(admission.blocking_agent_id, admission.reason)
                recruited_agent_ids = admission.recruited_agent_ids

            # Build-only validation (D6): require plan_artifact_refs
            include_plan = bool(cycle.applied_defaults.get("plan_tasks", True))
            include_build = bool(cycle.applied_defaults.get("build_tasks"))
            seed_artifact_refs: list[str] = []
            if include_build and not include_plan:
                # Legacy build-only run: plan_artifact_refs are mandatory
                plan_refs = cycle.execution_overrides.get("plan_artifact_refs")
                if not plan_refs:
                    raise _ExecutionError("plan_artifact_refs required for build-only cycle")
                seed_artifact_refs = list(plan_refs)
            elif run.workload_type is not None:
                # Multi-workload run: seed from forwarded planning artifacts
                plan_refs = cycle.execution_overrides.get("plan_artifact_refs")
                if plan_refs:
                    seed_artifact_refs = list(plan_refs)

            # LangFuse + Prefect observability setup
            obs_ctx, flow_run_id = await self._init_run_observability(
                cycle_id,
                run_id,
                cycle,
                plan,
            )

            # SIP-0087 B4: enter flow-level correlation scope so orchestrator
            # logs emitted between dispatches (workload progression, gate
            # decisions, executor lifecycle) carry flow_run_id (and no
            # task_run_id) and land in the flow-run pane in the Prefect UI.
            # TaskDispatcher.dispatch_task nests its own per-task scope inside this one.
            flow_ctx = CorrelationContext(cycle_id=cycle_id, flow_run_id=flow_run_id)
            with use_correlation_context(flow_ctx):
                logger.info(
                    "Executing run %s for cycle %s (%d tasks, mode=%s, dispatch=dispatched)",
                    run_id,
                    cycle_id,
                    len(plan),
                    cycle.task_flow_policy.mode,
                )

                # Dispatch based on policy mode
                mode = cycle.task_flow_policy.mode
                if mode == "sequential":
                    await self._execute_sequential(
                        plan,
                        run_id,
                        cycle,
                        flow_run_id,
                        seed_artifact_refs,
                        obs_ctx=obs_ctx,
                        profile=profile,
                        run_root=run_root,
                        ledger=ledger,
                    )
                elif mode == "fan_out_fan_in":
                    await self._execute_fan_out(plan, run_id, cycle, flow_run_id)
                elif mode == "fan_out_soft_gates":
                    await self._execute_sequential(
                        plan,
                        run_id,
                        cycle,
                        flow_run_id,
                        seed_artifact_refs,
                        obs_ctx=obs_ctx,
                        profile=profile,
                        run_root=run_root,
                        ledger=ledger,
                    )
                else:
                    await self._execute_sequential(
                        plan,
                        run_id,
                        cycle,
                        flow_run_id,
                        seed_artifact_refs,
                        obs_ctx=obs_ctx,
                        run_root=run_root,
                        ledger=ledger,
                    )

                # Success -> completed
                await self._cycle_registry.update_run_status(run_id, RunStatus.COMPLETED)
                self._cycle_event_bus.emit(
                    EventType.RUN_COMPLETED,
                    entity_type="run",
                    entity_id=run_id,
                    context={
                        "cycle_id": cycle_id,
                        "run_id": run_id,
                        "project_id": cycle.project_id,
                    },
                )
                logger.info("Run %s completed successfully", run_id)

        except Exception as exc:
            # SIP-0097 §6.4: the exception→status mapping is owned by the
            # run-completion module; this block persists, emits, and logs
            # what the mapping decides (behavior-preserving collapse of the
            # former per-class handlers).
            outcome = resolve_terminal_outcome(exc, run_id)
            terminal_status = outcome.terminal_status
            await self._safe_transition(run_id, outcome.run_status)
            self._cycle_event_bus.emit(
                outcome.event_type,
                entity_type="run",
                entity_id=run_id,
                context={"cycle_id": cycle_id, "run_id": run_id},
                payload=outcome.event_payload,
            )
            if outcome.log_kind == "exception":
                logger.exception(outcome.log_message)
            elif outcome.log_kind == "error":
                logger.error(outcome.log_message)
            else:
                logger.info(outcome.log_message)

        finally:
            # SIP-0089 §3.5 (#233): release the cycle leases this run acquired,
            # whatever the outcome (completed/failed/paused/cancelled). Best-effort
            # and isolated per agent — a stranded cycle lease would block all of an
            # agent's future recruitment, so this must run before anything that can
            # raise. Empty (and skipped) when the run recruited no one.
            if self._coordinator is not None and recruited_agent_ids:
                await release_participants(self._coordinator, recruited_agent_ids, owner_ref=run_id)
            await self._run_completion.finalize(
                cycle_id,
                run_id,
                terminal_status,
                obs_ctx,
                flow_run_id,
                cycle=cycle,
                plan=plan,
                ledger=ledger,
            )

    async def cancel_run(self, run_id: str) -> None:
        """Cancel an in-progress run."""
        self._cancelled.add(run_id)
        try:
            await self._cycle_registry.cancel_run(run_id)
        except Exception:
            logger.warning("cancel_run: registry cancel failed for %s", run_id, exc_info=True)

    # ------------------------------------------------------------------
    # Multi-workload orchestration (SIP-0083)
    # ------------------------------------------------------------------

    async def execute_cycle(
        self, cycle_id: str, first_run_id: str, profile_id: str | None = None
    ) -> None:
        """Execute a full cycle by iterating over workload_sequence.

        Assumes execute_run() returns only after the run reaches a terminal
        state (completed, failed, cancelled). Decision semantics for inter-
        workload gates are interpreted here, not in the polling helper.
        """
        cycle = await self._cycle_registry.get_cycle(cycle_id)
        workload_sequence = cycle.applied_defaults.get("workload_sequence", [])

        # Single-workload fast path (D7)
        if len(workload_sequence) <= 1:
            await self.execute_run(cycle_id, first_run_id, profile_id)
            return

        # #257: support resuming mid-sequence. first_run_id may be a later
        # workload's run (a resumed/deferred run), not the position-0 run. Start
        # the loop at that run's workload index so earlier, already-completed
        # workloads aren't re-run and the resumed run isn't double-executed.
        # Cycle-create passes the first run, which resolves to index 0.
        start_index = await self._starting_workload_index(cycle_id, first_run_id)
        current_run_id = first_run_id
        # SIP-0097 §6.6: forwarding overrides are a cycle-scoped value threaded
        # into each run invocation, not executor state. Built at the end of
        # workload i, consumed by workload i+1's execute_run.
        forwarding_overrides: dict | None = None
        for i in range(start_index, len(workload_sequence)):
            workload_entry = workload_sequence[i]
            await self.execute_run(
                cycle_id,
                current_run_id,
                profile_id,
                forwarding_overrides=forwarding_overrides,
            )

            # Check terminal status (compare persisted string values)
            run = await self._cycle_registry.get_run(current_run_id)
            if run.status in (RunStatus.FAILED.value, RunStatus.CANCELLED.value):
                self._cycle_event_bus.emit(
                    EventType.WORKLOAD_COMPLETED,
                    entity_type="workload",
                    entity_id=current_run_id,
                    context={"cycle_id": cycle_id, "run_id": current_run_id},
                    payload={
                        "workload_type": workload_entry.get("type"),
                        "terminal_status": run.status,
                    },
                )
                break

            self._cycle_event_bus.emit(
                EventType.WORKLOAD_COMPLETED,
                entity_type="workload",
                entity_id=current_run_id,
                context={"cycle_id": cycle_id, "run_id": current_run_id},
                payload={
                    "workload_type": workload_entry.get("type"),
                    "terminal_status": RunStatus.COMPLETED.value,
                },
            )

            # Last workload — done
            if i >= len(workload_sequence) - 1:
                break

            # Inter-workload gate
            gate_name = workload_entry.get("gate")
            if gate_name and gate_name != "auto":
                # #464: the inter-workload gate is the plan gate our cycle
                # shapes actually traverse (the mid-run _handle_gate path only
                # fires for task_flow_policy gates) — validate the authored
                # plan BEFORE asking the operator to review it. A doomed plan
                # gets a rejection, not a review request.
                await self._reject_invalid_plan_before_workload_gate(run, cycle, gate_name)
                self._cycle_event_bus.emit(
                    EventType.WORKLOAD_GATE_AWAITING,
                    entity_type="workload",
                    entity_id=current_run_id,
                    context={"cycle_id": cycle_id, "run_id": current_run_id},
                    payload={"gate_name": gate_name},
                )
                decision = await self._poll_inter_workload_gate(
                    current_run_id,
                    cycle,
                    gate_name,
                )

                if decision.decision == GateDecisionValue.REJECTED:
                    break  # Run stays COMPLETED; rejection in gate_decisions

                if decision.decision == GateDecisionValue.RETURNED_FOR_REVISION:
                    # #466: revision is NOT an approval — do not advance the
                    # sequence with the un-revised plan (the 3.10 false-approve).
                    # Parity with the mid-run gate path: revision requires
                    # manual retry-run creation; the decision + notes stay in
                    # gate_decisions for whoever creates it.
                    logger.info(
                        "Gate %r returned_for_revision on run %s: stopping the "
                        "workload sequence; revision requires manual retry-run "
                        "creation (automatic retry-in-same-phase is not "
                        "implemented in this version)",
                        gate_name,
                        current_run_id,
                    )
                    break

                if decision.decision not in (
                    GateDecisionValue.APPROVED,
                    GateDecisionValue.APPROVED_WITH_REFINEMENTS,
                ):
                    # #466: exhaustive dispatch — an unknown/future decision
                    # value must never silently act as an approval.
                    logger.warning(
                        "Gate %r on run %s carries unrecognized decision %r: "
                        "stopping the workload sequence",
                        gate_name,
                        current_run_id,
                        decision.decision,
                    )
                    break

                # Write refinement notes as artifact (D10)
                if (
                    decision.decision == GateDecisionValue.APPROVED_WITH_REFINEMENTS
                    and decision.notes
                ):
                    artifact_content = f"# Refinement Notes\n\n{decision.notes}\n"
                    content_bytes = artifact_content.encode()
                    refinement_ref = ArtifactRef(
                        artifact_id=f"art_{uuid4().hex[:12]}",
                        project_id=cycle.project_id,
                        cycle_id=cycle.cycle_id,
                        run_id=current_run_id,
                        artifact_type="document",
                        filename="refinement_notes.md",
                        content_hash=sha256(content_bytes).hexdigest(),
                        size_bytes=len(content_bytes),
                        media_type="text/markdown",
                        created_at=datetime.now(UTC),
                        metadata={"producing_task_type": "gate.refinement_notes"},
                    )
                    await self._artifact_vault.store(refinement_ref, content_bytes)
                    await self._cycle_registry.append_artifact_refs(
                        current_run_id, (refinement_ref.artifact_id,)
                    )

            # Positional duplicate guard (D14).
            # Assumes runs are created in sequence order by this orchestration
            # loop and no out-of-band run creation targets the same position.
            next_workload = workload_sequence[i + 1]
            all_runs = await self._cycle_registry.list_runs(cycle_id)
            non_cancelled = sorted(
                [r for r in all_runs if r.status != RunStatus.CANCELLED.value],
                key=lambda r: r.run_number,
            )

            # Build forwarding overrides for the next workload's execute_run()
            forwarding_overrides = await self._build_forwarding_overrides(
                cycle,
                run,
            )

            if len(non_cancelled) > i + 1:
                current_run_id = non_cancelled[i + 1].run_id
            else:
                next_run = await self._create_next_workload_run(
                    cycle,
                    run,
                    next_workload,
                    config_hash=run.resolved_config_hash,
                )
                current_run_id = next_run.run_id

            self._cycle_event_bus.emit(
                EventType.WORKLOAD_ADVANCED,
                entity_type="workload",
                entity_id=current_run_id,
                context={"cycle_id": cycle_id, "run_id": current_run_id},
                payload={"workload_type": next_workload.get("type")},
            )

    async def _starting_workload_index(self, cycle_id: str, first_run_id: str) -> int:
        """Workload-sequence index that ``first_run_id`` occupies (#257).

        Runs map positionally to workloads — one run per position, created in
        sequence order (D14) — so a run's index among the cycle's non-cancelled
        runs (sorted by run_number) is its workload position. This lets
        execute_cycle resume mid-sequence without re-running earlier completed
        workloads or double-executing the resumed run. Returns 0 when the run is
        the first/only one (the cycle-create entry) or is not found.
        """
        all_runs = await self._cycle_registry.list_runs(cycle_id)
        non_cancelled = sorted(
            (r for r in all_runs if r.status != RunStatus.CANCELLED.value),
            key=lambda r: r.run_number,
        )
        for index, run in enumerate(non_cancelled):
            if run.run_id == first_run_id:
                return index
        return 0

    async def _poll_inter_workload_gate(
        self, run_id: str, cycle: Cycle, gate_name: str
    ) -> GateDecision:
        """Poll for and return the inter-workload gate decision on a completed run.

        Decision semantics (approved, rejected, etc.) are interpreted by
        execute_cycle(), not here. This helper only waits for any decision
        to appear on the named gate.
        """
        poll_interval = 2.0
        while True:
            if await self._is_cancelled(run_id):
                raise _CancellationError(run_id)
            run = await self._cycle_registry.get_run(run_id)
            for decision in run.gate_decisions:
                if decision.gate_name == gate_name:
                    return decision
            await asyncio.sleep(poll_interval)

    async def _build_forwarding_overrides(
        self,
        cycle: Cycle,
        completed_run: Run,
    ) -> dict:
        """Build execution_overrides with artifact refs from the completed run.

        Forwarded artifact lists are sorted by creation time for deterministic
        ordering.  Operator-supplied overrides in cycle.execution_overrides
        always take precedence.

        Merge semantics:
        - List keys (plan_artifact_refs, prior_workload_artifact_refs):
          merge with existing values, deduplicate.
        - Scalar keys (impl_run_id): only write when no explicit override exists.
        """
        overrides = dict(cycle.execution_overrides)

        # promoted artifacts only — empty list if nothing promoted (D9, §5.6 rule 6)
        promoted = await self._artifact_vault.list_artifacts(
            run_id=completed_run.run_id,
            promotion_status="promoted",
        )
        promoted_refs = [a.artifact_id for a in sorted(promoted, key=lambda a: a.created_at)]
        if "prior_workload_artifact_refs" in overrides:
            existing = overrides["prior_workload_artifact_refs"]
            seen = set(existing)
            merged = list(existing) + [r for r in promoted_refs if r not in seen]
            overrides["prior_workload_artifact_refs"] = merged
        else:
            overrides["prior_workload_artifact_refs"] = promoted_refs

        # workload-type-specific keys
        wt = completed_run.workload_type
        if wt == "framing":
            # SIP-0086 / SIP-0092: include control_implementation_plan
            # alongside documents so the implementation_plan.yaml reaches the
            # implementation workload.
            plan_types = {"document", "control_implementation_plan"}
            plan_candidates = [a for a in promoted if a.artifact_type in plan_types]
            plan_refs = [a.artifact_id for a in sorted(plan_candidates, key=lambda a: a.created_at)]
            if "plan_artifact_refs" in overrides:
                existing = overrides["plan_artifact_refs"]
                seen = set(existing)
                merged = list(existing) + [r for r in plan_refs if r not in seen]
                overrides["plan_artifact_refs"] = merged
            else:
                overrides["plan_artifact_refs"] = plan_refs
        elif wt == "implementation":
            if "impl_run_id" not in overrides:
                overrides["impl_run_id"] = completed_run.run_id

        return overrides

    async def _create_next_workload_run(
        self,
        cycle: Cycle,
        completed_run: Run,
        workload_entry: dict,
        config_hash: str,
    ) -> Run:
        """Create the next workload Run."""
        all_runs = await self._cycle_registry.list_runs(cycle.cycle_id)
        next_number = max(r.run_number for r in all_runs) + 1

        next_run = Run(
            run_id=f"run_{uuid4().hex[:12]}",
            cycle_id=cycle.cycle_id,
            run_number=next_number,
            status=RunStatus.QUEUED.value,
            initiated_by="system",
            resolved_config_hash=config_hash,
            workload_type=workload_entry.get("type"),
        )
        return await self._cycle_registry.create_run(next_run)

    # ------------------------------------------------------------------
    # Execution strategies
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Build task artifact filter (D3, §2.2)
    # ------------------------------------------------------------------

    # Maps build task_type → which prior artifacts to inject.
    # by_producing_task: match on producing_task_type metadata
    # by_type / by_type_fallback: match on artifact_type for artifacts without provenance
    _BUILD_ARTIFACT_FILTER: dict[str, dict[str, list[str]]] = {
        "development.develop": {
            # SIP-0086: include prior development.develop for manifest-driven
            # subtask chaining (dev→dev artifact accumulation)
            "by_producing_task": [
                "strategy.analyze_prd",
                "development.design",
                "development.develop",
            ],
            "by_type_fallback": ["document"],
        },
        "builder.assemble": {
            "by_producing_task": ["development.develop"],
            "by_type": ["source", "config"],
            # #443: provenance-less documents are the seeded scaffold (frozen
            # fill-contract files) — without them assembly packages a partial app.
            "by_type_fallback": ["document"],
        },
        "qa.test": {
            # SIP-0086: include development.develop for manifest-driven QA
            # subtasks that need to see all prior build artifacts
            "by_producing_task": ["qa.validate", "builder.assemble", "development.develop"],
            "by_type": ["source", "config"],
            # #443: same fallback development.develop already has — the seeded
            # scaffold must reach verification or frontend_build/tests_pass run
            # against a workspace missing package.json and the backend modules.
            "by_type_fallback": ["document"],
        },
    }

    async def _resolve_artifact_contents(
        self,
        task_type: str,
        stored_artifacts: list[tuple[str, ArtifactRef]],
    ) -> dict[str, str]:
        """Pre-resolve artifact content for build tasks (D3).

        Args:
            task_type: The build task type being dispatched.
            stored_artifacts: List of (artifact_id, ArtifactRef) from prior tasks.

        Returns:
            Dict of filename → content string. Empty if task_type not a build task.
        """
        filter_spec = self._BUILD_ARTIFACT_FILTER.get(task_type)
        if not filter_spec:
            return {}

        producing_tasks = set(filter_spec.get("by_producing_task", []))
        type_filter = set(filter_spec.get("by_type", []))
        type_fallback = set(filter_spec.get("by_type_fallback", []))

        selected_ids: list[str] = []
        for art_id, ref in stored_artifacts:
            producing_task = ref.metadata.get("producing_task_type", "")
            if producing_task and producing_task in producing_tasks:
                selected_ids.append(art_id)
            elif producing_task and producing_task in type_filter:
                # by_type filter applies to all artifacts with matching type
                pass  # handled below
            elif not producing_task and ref.artifact_type in type_fallback:
                # Fallback for artifacts without provenance (e.g., injected plan refs)
                selected_ids.append(art_id)

            # by_type: match artifact_type regardless of producing_task
            if type_filter and ref.artifact_type in type_filter:
                if art_id not in selected_ids:
                    selected_ids.append(art_id)

        # Resolve content (D3: 512KB limit)
        contents: dict[str, str] = {}
        total_bytes = 0
        limit = 512 * 1024

        for art_id in selected_ids:
            try:
                ref, content_bytes = await self._artifact_vault.retrieve(art_id)
                decoded = content_bytes.decode(errors="replace")
                total_bytes += len(content_bytes)
                if total_bytes > limit:
                    logger.warning(
                        "Artifact content limit exceeded (%d bytes) for %s, "
                        "stopping pre-resolution",
                        total_bytes,
                        task_type,
                    )
                    break
                contents[ref.filename] = decoded
            except Exception:
                logger.warning(
                    "Failed to retrieve artifact %s for build task %s",
                    art_id,
                    task_type,
                    exc_info=True,
                )

        return contents

    async def _execute_sequential(
        self,
        plan: list[TaskEnvelope],
        run_id: str,
        cycle: Cycle,
        flow_run_id: str | None = None,
        seed_artifact_refs: list[str] | None = None,
        obs_ctx: Any = None,
        profile: SquadProfile | None = None,
        run_root: str = "",
        *,
        ledger: RunLedger,
    ) -> None:
        """Sequential: dispatch one task at a time, fail-fast.

        SIP-0070: evaluates pulse verification at cadence closes and
        milestone boundaries.  Phase 2: FAIL = run FAILED (no repair).
        """
        prior_outputs: dict[str, Any] = {}
        all_artifact_refs: list[str] = []
        # Track stored artifacts with their refs for build pre-resolution
        stored_artifacts: list[tuple[str, ArtifactRef]] = []

        # SIP-0079: Checkpoint/resume state tracking
        completed_task_ids: list[str] = []
        plan_delta_refs: list[str] = []
        skip_task_ids: set[str] = set()

        # SIP-0079 Phase 3: Outcome routing state
        consecutive_failures: int = 0
        # #374: run-level correction count as a mutable holder. A `patch` re-runs the
        # failed check via dispatch_with_retry's "continue", so the count must bump on
        # each inner-loop correction (not just once per outer iteration) to bound it
        # (max_correction_attempts) and keep corr-/plan_delta- ids unique across re-runs.
        correction_counter: dict[str, int] = {"n": 0}
        task_attempt_counts: dict[str, int] = {}

        # SIP-0079: Time budget enforcement (RC-8)
        time_budget = cycle.applied_defaults.get("time_budget_seconds")
        run_start_time = time.monotonic()

        # SIP-0079: Resume from checkpoint — restore prior state
        checkpoint = await self._cycle_registry.get_latest_checkpoint(run_id)
        if checkpoint:
            await self._restore_checkpoint_state(
                checkpoint,
                run_id,
                cycle,
                skip_task_ids,
                prior_outputs,
                completed_task_ids,
                plan_delta_refs,
                all_artifact_refs,
                stored_artifacts,
            )

        # Seed from prior plan artifacts for build-only runs (§2.3)
        if seed_artifact_refs:
            await self._seed_prior_artifacts(
                seed_artifact_refs,
                stored_artifacts,
                all_artifact_refs,
            )

        # Build role → agent_id resolver for repair task dispatch
        agent_resolver = build_agent_resolver(profile)

        # ------------------------------------------------------------------
        # SIP-0070: Parse pulse checks + cadence policy from applied_defaults
        # ------------------------------------------------------------------
        pulse_ctx = self._pulse_boundary_runner.setup_pulse_context(cycle, plan, obs_ctx)
        milestone_bindings = pulse_ctx["milestone_bindings"]
        cadence_suites = pulse_ctx["cadence_suites"]
        has_pulse_checks = pulse_ctx["has_pulse_checks"]
        cadence = pulse_ctx["cadence"]
        engine = pulse_ctx["engine"]

        # Cadence tracking state
        cadence_task_count = 0
        cadence_start_time = time.monotonic()
        cadence_interval_id = 1

        for task_idx, envelope in enumerate(plan):
            if await self._check_task_preconditions(
                run_id, envelope, skip_task_ids, time_budget, run_start_time, completed_task_ids
            ):
                continue

            # Enrich envelope with chain context and dispatch
            enriched = await self._enrich_envelope(
                envelope,
                prior_outputs,
                all_artifact_refs,
                stored_artifacts,
            )

            # SIP-0087: executor owns Prefect task-run creation so task_run_id
            # is available for contextvar scoping + heartbeat before the
            # agent starts emitting logs.
            task_run_id = await self._task_dispatcher.create_task_run_if_enabled(
                flow_run_id, envelope
            )

            # SIP-0077: task.dispatched event (bridge now only reads terminal
            # state from context; creation already happened above).
            self._cycle_event_bus.emit(
                EventType.TASK_DISPATCHED,
                entity_type="task",
                entity_id=envelope.task_id,
                context={
                    "cycle_id": cycle.cycle_id,
                    "run_id": run_id,
                    "flow_run_id": flow_run_id or "",
                    "task_run_id": task_run_id or "",
                },
                payload={
                    "task_type": envelope.task_type,
                    "task_name": build_task_name(envelope),
                },
            )

            # Dispatch + retry loop for retryable failures (SIP-0079).
            # Routing stays here (§6.1): the dispatcher receives the outcome
            # decision as a closure over this loop's orchestration state and
            # only acts on the returned action token.
            # Loop-scoped values bind as defaults: fixed at definition time,
            # exactly like the old per-call parameter passing (and B023-safe).
            # SIP-0096 §6.4 (Phase 2): holds the latest failed result so the abort
            # path — where the correction protocol raises from *inside*
            # dispatch_with_retry before it can return — can still record the
            # failing task's verification evidence. The #276-class evidence (a
            # failed/not-executed qa.test that triggers the abort) is exactly what
            # must survive, or a failed run reads as "0 verified" instead of red.
            _last_failed_result: dict[str, Any] = {}

            async def _route_outcome(
                result,
                _envelope=envelope,
                _enriched=enriched,
                _consecutive_failures=consecutive_failures,
                _holder=_last_failed_result,
            ):
                _holder["result"] = result
                action = await self._handle_task_outcome(
                    result=result,
                    envelope=_envelope,
                    enriched_envelope=_enriched,
                    cycle=cycle,
                    run_id=run_id,
                    task_attempt_counts=task_attempt_counts,
                    consecutive_failures=_consecutive_failures,
                    correction_counter=correction_counter,
                    prior_outputs=prior_outputs,
                    all_artifact_refs=all_artifact_refs,
                    stored_artifacts=stored_artifacts,
                    completed_task_ids=completed_task_ids,
                    plan_delta_refs=plan_delta_refs,
                    profile=profile,
                    flow_run_id=flow_run_id,
                    patched_result_holder=_holder,
                )
                if action in ("continue", "accept_patch"):
                    # #379: this attempt failed — re-dispatched ("continue") or
                    # superseded by a verified patch ("accept_patch", #389). Record
                    # its evidence now so the ledger honestly holds the
                    # failed→passed history; aggregation supersedes it to the final
                    # state per (check_id, subject). Self-filtering: a transport retry
                    # carries no validation_result/test_result → nothing is recorded.
                    _record_task_evidence(result)
                return action

            def _record_task_evidence(task_result, _envelope=envelope) -> None:
                # Normalize this task's verification outputs into the run ledger for
                # the end-of-run aggregation choke point. Every result is stamped with
                # the producing task id (#379) so a repaired-and-re-run check resolves
                # to its final state at aggregation. ``_envelope`` is bound as a default
                # (B023) so it captures THIS iteration's task, matching _route_outcome.
                # Best-effort: a normalizer defect must never break task execution (the
                # report path is guarded the same).
                if task_result is None or not getattr(task_result, "outputs", None):
                    return
                try:
                    for check_result in normalize_task_checks(
                        task_result.outputs, subject=_envelope.task_id
                    ):
                        ledger.record_check_result(check_result)
                except Exception:
                    logger.warning("Verification-evidence recording failed", exc_info=True)

            try:
                task_succeeded, result = await self._task_dispatcher.dispatch_with_retry(
                    enriched,
                    envelope,
                    cycle,
                    run_id,
                    flow_run_id=flow_run_id,
                    task_run_id=task_run_id,
                    handle_task_outcome=_route_outcome,
                )
            except Exception:
                # Correction aborted (raised inside dispatch_with_retry). Record the
                # final failed result before the run unwinds, then re-raise — recording
                # is additive and never alters the abort's control flow.
                _record_task_evidence(_last_failed_result.get("result"))
                raise

            # #389: a verified patch supersedes the failed result — swap before
            # recording/collection so the ledger and artifact store see the
            # corrected outputs (repaired artifacts + executed-passed checks).
            patched = _last_failed_result.pop("patched_result", None)
            if patched is not None:
                result = patched

            # Every non-abort completion — success AND corrected-failure
            # (break_correction) — records its final result here; the abort path
            # above is the only other producer, so no task is double-recorded.
            _record_task_evidence(result)

            if not task_succeeded:
                # #374: reaching here means the correction returned break_correction —
                # i.e. governance chose "continue" (advance without repair). A `patch`
                # now returns "continue", re-running the failed check inside
                # dispatch_with_retry, so it never lands here. The correction count is
                # bumped on the shared holder inside _handle_task_outcome, not here.
                consecutive_failures = 0

            if not task_succeeded:
                # Correction "continue"/"patch" handled — skip to next task
                continue

            # Reset consecutive failures on success
            consecutive_failures = 0

            # Collect artifacts + checkpoint after successful task
            await self._collect_artifacts_and_checkpoint(
                result=result,
                envelope=envelope,
                cycle=cycle,
                run_id=run_id,
                prior_outputs=prior_outputs,
                all_artifact_refs=all_artifact_refs,
                stored_artifacts=stored_artifacts,
                completed_task_ids=completed_task_ids,
                plan_delta_refs=plan_delta_refs,
            )

            # ----------------------------------------------------------
            # SIP-0070: Pulse boundary evaluation (after task, before gate)
            # ----------------------------------------------------------
            if has_pulse_checks and engine is not None:
                cadence_task_count += 1
                cadence_closed = self._pulse_boundary_runner.evaluate_pulse_boundaries(
                    task_idx=task_idx,
                    plan=plan,
                    cadence_task_count=cadence_task_count,
                    cadence_start_time=cadence_start_time,
                    cadence=cadence,
                )
                await self._pulse_boundary_runner.run_pulse_evaluations(
                    task_idx=task_idx,
                    milestone_bindings=milestone_bindings,
                    cadence_suites=cadence_suites,
                    cadence_closed=cadence_closed,
                    cadence_interval_id=cadence_interval_id,
                    run_id=run_id,
                    cycle=cycle,
                    obs_ctx=obs_ctx,
                    engine=engine,
                    envelope=envelope,
                    prior_outputs=prior_outputs,
                    stored_artifacts=stored_artifacts,
                    all_artifact_refs=all_artifact_refs,
                    flow_run_id=flow_run_id,
                    agent_resolver=agent_resolver,
                    run_root=run_root,
                    ledger=ledger,
                )

                if cadence_closed:
                    cadence_interval_id += 1
                    cadence_task_count = 0
                    cadence_start_time = time.monotonic()

            # Post-task gate check (runs after verification)
            if self._is_gate_boundary(cycle, envelope.task_type):
                await self._handle_gate(
                    run_id,
                    cycle,
                    envelope.task_type,
                    stored_artifacts=stored_artifacts,
                    profile=profile,
                )

        # #291: deliverable-completeness gate. The per-task builder validator
        # (#107) only enforces the *active* task's required files; a required
        # file that framing spread across tasks — or that no single task owns —
        # is never checked, so a run can ship green without the Dockerfile its
        # own profile mandates (#276). The loop is done, so stored_artifacts now
        # holds the complete emitted set — the only point where the deliverable
        # is fully known. Missing → fail the run (FAILED, via _ExecutionError →
        # resolve_terminal_outcome). The per-task required_files *evidence* the
        # roll-up reads is emitted at the builder task itself (#399), so an
        # in-loop builder failure is disclosed even though this gate is only
        # reached when every task succeeded.
        resolved_config = {**cycle.applied_defaults, **cycle.execution_overrides}
        deficiency = compute_missing_required_files(plan, stored_artifacts, resolved_config)
        if deficiency is not None:
            profile_name, missing = deficiency
            raise _ExecutionError(
                f"Build deliverable incomplete: build profile {profile_name!r} requires files "
                f"the run never emitted. Missing required files: {missing}."
            )

    # ------------------------------------------------------------------
    # SIP-0086: Manifest loading for implementation workloads
    # ------------------------------------------------------------------

    async def _load_plan_for_run(
        self,
        cycle: Any,
        run: Any,
    ) -> Any:
        """Load implementation plan for an implementation workload run.

        Searches forwarded plan_artifact_refs for a control_implementation_plan
        artifact. Called before generate_task_plan() so the plan is fully
        materialized before task dispatch begins — no mid-loop mutation.

        Returns ImplementationPlan or None (RC-4 graceful fallback).
        """
        from squadops.cycles.implementation_plan import ImplementationPlan

        # Only load the plan when implementation_plan is enabled in resolved config
        if not cycle.applied_defaults.get("implementation_plan", False):
            return None

        # Search forwarded planning artifacts for the plan
        plan_refs = cycle.execution_overrides.get("plan_artifact_refs", [])
        if not plan_refs:
            return None

        for ref_id in plan_refs:
            try:
                ref, content_bytes = await self._artifact_vault.retrieve(ref_id)
                if ref.filename == "implementation_plan.yaml" or (
                    hasattr(ref, "artifact_type")
                    and ref.artifact_type == "control_implementation_plan"
                ):
                    yaml_content = content_bytes.decode(errors="replace")
                    manifest = ImplementationPlan.from_yaml(yaml_content)
                    logger.info(
                        "Loaded implementation plan with %d subtasks for run %s",
                        len(manifest.tasks),
                        run.run_id,
                    )
                    return manifest
            except Exception:
                logger.warning(
                    "Failed to load manifest from artifact %s, falling back to static task steps",
                    ref_id,
                    exc_info=True,
                )
                return None

        return None

    # ------------------------------------------------------------------
    # Extracted helpers for _execute_sequential
    # ------------------------------------------------------------------

    async def _check_task_preconditions(
        self,
        run_id: str,
        envelope: TaskEnvelope,
        skip_task_ids: set[str],
        time_budget: float | None,
        run_start_time: float,
        completed_task_ids: list[str],
    ) -> bool:
        """Check whether a task should proceed, be skipped, or abort the run.

        Returns True if the task should be skipped (caller should ``continue``).
        Raises _CancellationError or _ExecutionError for terminal conditions.
        """
        if await self._is_cancelled(run_id):
            raise _CancellationError(run_id)

        if envelope.task_id in skip_task_ids:
            logger.info(
                "Skipping completed task %s (%s) from checkpoint",
                envelope.task_id,
                envelope.task_type,
            )
            return True

        if time_budget is not None and (time.monotonic() - run_start_time) >= time_budget:
            raise _ExecutionError(
                f"Time budget exhausted ({time_budget}s) after {len(completed_task_ids)} tasks"
            )

        return False

    async def _enrich_envelope(
        self,
        envelope: TaskEnvelope,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
    ) -> TaskEnvelope:
        """Build chain context inputs and return an enriched envelope."""

        extra_inputs: dict[str, Any] = {
            "prior_outputs": prior_outputs,
            "artifact_refs": list(all_artifact_refs),
        }

        # Pre-resolve artifact contents for build tasks (D3)
        if envelope.task_type in self._BUILD_ARTIFACT_FILTER:
            artifact_contents = await self._resolve_artifact_contents(
                envelope.task_type,
                stored_artifacts,
            )
            if artifact_contents:
                extra_inputs["artifact_contents"] = artifact_contents

        return dataclasses.replace(
            envelope,
            inputs={
                **envelope.inputs,
                **extra_inputs,
            },
        )

    async def _restore_checkpoint_state(
        self,
        checkpoint: RunCheckpoint,
        run_id: str,
        cycle: Cycle,
        skip_task_ids: set[str],
        prior_outputs: dict[str, Any],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
    ) -> None:
        """Restore execution state from a checkpoint (SIP-0079 resume)."""
        skip_task_ids.update(checkpoint.completed_task_ids)
        prior_outputs.update(checkpoint.prior_outputs)
        completed_task_ids.extend(checkpoint.completed_task_ids)
        plan_delta_refs.extend(checkpoint.plan_delta_refs)
        # Restore artifact refs from checkpoint
        for art_id in checkpoint.artifact_refs:
            if art_id not in all_artifact_refs:
                all_artifact_refs.append(art_id)
            try:
                ref, _ = await self._artifact_vault.retrieve(art_id)
                stored_artifacts.append((art_id, ref))
            except Exception:
                logger.warning(
                    "Failed to restore artifact %s from checkpoint", art_id, exc_info=True
                )
        self._cycle_event_bus.emit(
            EventType.CHECKPOINT_RESTORED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={
                "checkpoint_index": checkpoint.checkpoint_index,
                "completed_task_count": len(skip_task_ids),
            },
        )
        logger.info(
            "Resumed run %s from checkpoint %d (%d tasks completed)",
            run_id,
            checkpoint.checkpoint_index,
            len(skip_task_ids),
        )

    async def _seed_prior_artifacts(
        self,
        seed_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        all_artifact_refs: list[str],
    ) -> None:
        """Load seed artifacts for build-only runs (section 2.3)."""
        for art_id in seed_artifact_refs:
            try:
                ref, _ = await self._artifact_vault.retrieve(art_id)
                stored_artifacts.append((art_id, ref))
                all_artifact_refs.append(art_id)
            except Exception:
                logger.warning(
                    "Failed to seed artifact %s for build-only run",
                    art_id,
                    exc_info=True,
                )

    async def _handle_task_outcome(
        self,
        result: TaskResult,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        task_attempt_counts: dict[str, int],
        consecutive_failures: int,
        correction_counter: dict[str, int],
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        profile: Any = None,
        flow_run_id: str | None = None,
        patched_result_holder: dict[str, Any] | None = None,
        enriched_envelope: TaskEnvelope | None = None,
    ) -> str:
        """Route a failed task outcome. Returns an action string.

        ``enriched_envelope`` is the dispatch-time envelope carrying the
        materialized workspace (``artifact_contents``) — the base ``envelope``
        never has it (#456 retest plumbing; the 3.11 instant-fail).

        Returns:
            "continue" — re-dispatch the same task (caller's while loop retries it):
                a retryable failure, OR (#374) a ``patch`` correction whose repair is
                verified behaviorally by re-running the failed check itself.
            "accept_patch" — (#389) a ``patch`` correction whose repaired artifacts
                behaviorally pass the failed task's typed acceptance criteria; the
                corrected result is placed in ``patched_result_holder`` and the task
                advances without re-dispatch (re-dispatching a generative task
                re-rolls its artifacts and clobbers the repair).
            "break_correction" — correction handled without re-run (governance
                "continue": advance without repair), advance to next task.

        Raises:
            _PausedError — task is blocked
            _ExecutionError — unrecoverable failure (incl. max_correction_attempts
                exhausted, so a repair that never converges fails the run)
        """
        outcome = (result.outputs or {}).get("outcome_class") if result.outputs else None

        # D5 fallback table: classify unclassified failures
        if outcome is None:
            task_attempt_counts[envelope.task_id] = task_attempt_counts.get(envelope.task_id, 0) + 1
            max_retries = cycle.applied_defaults.get("max_task_retries", 2)
            if task_attempt_counts[envelope.task_id] >= max_retries:
                outcome = TaskOutcome.SEMANTIC_FAILURE
            else:
                outcome = TaskOutcome.RETRYABLE_FAILURE

        if outcome == TaskOutcome.BLOCKED:
            raise _PausedError(f"Task {envelope.task_id} ({envelope.task_type}) blocked")

        if outcome == TaskOutcome.RETRYABLE_FAILURE:
            logger.info(
                "Retryable failure for %s (attempt %d), retrying",
                envelope.task_id,
                task_attempt_counts.get(envelope.task_id, 1),
            )
            return "continue"

        # SEMANTIC_FAILURE / NEEDS_REPAIR / NEEDS_REPLAN → correction

        # D9: definition-of-done task failure → immediate abort, no correction
        if envelope.task_type == "governance.define_done":
            raise _ExecutionError(
                f"Definition-of-done task {envelope.task_id} failed (no correction): {result.error}"
            )

        # Trigger correction protocol
        max_corrections = cycle.applied_defaults.get("max_correction_attempts", 2)

        if correction_counter["n"] >= max_corrections:
            raise _ExecutionError(f"Max correction attempts ({max_corrections}) exhausted")

        # #374: bump the shared run-level count on THIS correction (before dispatch) so a
        # patch that re-runs the check (below) is bounded, and each re-run gets a fresh
        # corr-/plan_delta- id. The pre-increment value keys those deterministic ids.
        attempt = correction_counter["n"]
        correction_counter["n"] = attempt + 1

        protocol = await self._correction_runner.run_correction_protocol(
            run_id=run_id,
            cycle=cycle,
            envelope=envelope,
            result=result,
            correction_attempts=attempt,
            prior_outputs=prior_outputs,
            all_artifact_refs=all_artifact_refs,
            stored_artifacts=stored_artifacts,
            completed_task_ids=completed_task_ids,
            plan_delta_refs=plan_delta_refs,
            profile=profile,
            flow_run_id=flow_run_id,
        )
        correction_path = protocol.correction_path

        if correction_path == "abort":
            raise _ExecutionError(
                f"Correction protocol decided to abort after {envelope.task_type} failure"
            )
        elif correction_path == "rewind":
            raise _ExecutionError(f"Rewinding to checkpoint after {envelope.task_type} failure")
        elif correction_path == "patch":
            # #374/#389 (pure-behavioral): the verdict is the re-executed check,
            # never the LLM validate_repair judgment. First re-run the failed
            # task's typed acceptance criteria against the REPAIRED artifacts
            # (#389) — a pass accepts the patch outright, because re-dispatching
            # a generative task re-rolls its artifacts and discards the repair
            # (the cyc_6841d75f167c oscillation). Anything short of a verified
            # pass falls back to "continue": re-dispatch, re-enter correction
            # until max_correction_attempts exhausts (guard above) →
            # _ExecutionError → the run fails honestly instead of false-completing.
            action = await self._try_accept_patch(
                envelope,
                result,
                protocol.repair_artifacts,
                patched_result_holder,
                run_id=run_id,
                cycle=cycle,
                correction_attempts=attempt,
                enriched_envelope=enriched_envelope,
                prior_outputs=prior_outputs,
                all_artifact_refs=all_artifact_refs,
                stored_artifacts=stored_artifacts,
                completed_task_ids=completed_task_ids,
                plan_delta_refs=plan_delta_refs,
                profile=profile,
                flow_run_id=flow_run_id,
            )
            return action
        elif correction_path == "continue":
            # Governance chose to advance without repair (accept-and-move-on).
            return "break_correction"
        else:
            raise _ExecutionError(f"Unknown correction path: {correction_path}")

    async def _try_accept_patch(
        self,
        envelope: TaskEnvelope,
        result: TaskResult,
        repair_artifacts: list[dict[str, Any]],
        patched_result_holder: dict[str, Any] | None,
        *,
        run_id: str = "",
        cycle: Cycle | None = None,
        correction_attempts: int = 0,
        prior_outputs: dict[str, Any] | None = None,
        all_artifact_refs: list[str] | None = None,
        stored_artifacts: list[tuple[str, ArtifactRef]] | None = None,
        completed_task_ids: list[str] | None = None,
        plan_delta_refs: list[str] | None = None,
        profile: Any = None,
        flow_run_id: str | None = None,
        enriched_envelope: TaskEnvelope | None = None,
    ) -> str:
        """Behaviorally verify a patch (#389); return "accept_patch" or "continue".

        Verification itself is the pure ``patch_verification`` module; this
        method only assembles its inputs from the failed task and renders the
        corrected result. Any non-pass (failed, unverifiable, no repair
        artifacts, no holder) falls back to the pre-#389 re-dispatch path —
        conservative by construction, never a false accept.

        #456: typed criteria are necessary but not sufficient when the failed
        task carries behavioral evidence — ``tests_pass`` is synthesized from
        the task's executed ``test_result``, so a patched result that keeps the
        stale pre-repair ``test_result`` records the failure as the check's
        final state no matter what the typed rows say. When the failed outputs
        carry a ``test_result``, the repaired suite is re-executed in the QA
        agent's environment (via the correction runner) and the corrected
        result takes the retest's fresh behavioral evidence. A retest that
        fails — or can't run — falls back to "continue", same as a typed miss.
        """
        if not repair_artifacts or patched_result_holder is None:
            return "continue"

        resolved_config = (envelope.inputs or {}).get("resolved_config") or {}
        criteria = (envelope.inputs or {}).get("acceptance_criteria") or []
        patched_artifacts = overlay_artifacts(
            (result.outputs or {}).get("artifacts") or [], repair_artifacts
        )
        verification = await verify_patched_artifacts(
            criteria,
            patched_artifacts,
            stack=resolved_config.get("stack"),
            typed_acceptance_enabled=resolved_config.get("typed_acceptance", True),
            command_acceptance_enabled=resolved_config.get("command_acceptance_checks", True),
        )
        logger.info(
            "patch_verification task=%s task_type=%s status=%s reason=%s checks=%d",
            envelope.task_id,
            envelope.task_type,
            verification.status,
            verification.reason or "",
            len(verification.checks),
        )
        if verification.status != PATCH_PASSED:
            return "continue"

        corrected_outputs = dict(result.outputs or {})

        # #456: behavioral-evidence-backed task — re-execute the repaired
        # suite before accepting; fresh test_result supersedes the stale one.
        retest_rows: list[dict[str, Any]] = []
        if isinstance(corrected_outputs.get("test_result"), dict):
            if cycle is None:
                logger.warning(
                    "patch_verification task=%s carries test_result but no retest "
                    "context — falling back to re-dispatch",
                    envelope.task_id,
                )
                return "continue"
            # The retest needs the dispatch-time workspace: artifact_contents
            # is added by _enrich_envelope and never exists on the base
            # envelope (3.11: the retest instant-failed input validation
            # because it was built from the un-enriched envelope).
            retest_result = await self._correction_runner.reexecute_repaired_suite(
                run_id,
                cycle,
                enriched_envelope if enriched_envelope is not None else envelope,
                patched_artifacts,
                correction_attempts,
                prior_outputs=prior_outputs if prior_outputs is not None else {},
                all_artifact_refs=all_artifact_refs if all_artifact_refs is not None else [],
                stored_artifacts=stored_artifacts if stored_artifacts is not None else [],
                completed_task_ids=completed_task_ids if completed_task_ids is not None else [],
                plan_delta_refs=plan_delta_refs if plan_delta_refs is not None else [],
                profile=profile,
                flow_run_id=flow_run_id,
            )
            retest_outputs = (retest_result.outputs or {}) if retest_result else {}
            fresh_test_result = retest_outputs.get("test_result")
            retest_passed = (
                retest_result is not None
                and retest_result.status == "SUCCEEDED"
                and isinstance(fresh_test_result, dict)
                and fresh_test_result.get("tests_passed") is True
            )
            logger.info(
                "patch_retest task=%s status=%s passed=%s",
                envelope.task_id,
                retest_result.status if retest_result else "not_dispatched",
                retest_passed,
            )
            if not retest_passed:
                return "continue"
            corrected_outputs["test_result"] = fresh_test_result
            retest_validation = retest_outputs.get("validation_result")
            if isinstance(retest_validation, dict):
                retest_rows = [
                    row for row in retest_validation.get("checks", []) if isinstance(row, dict)
                ]

        corrected_outputs["artifacts"] = patched_artifacts
        prior_validation = corrected_outputs.get("validation_result")
        corrected_outputs["validation_result"] = {
            **(prior_validation if isinstance(prior_validation, dict) else {}),
            "passed": True,
            "patch_verified": True,
            "checks": [r.to_check_row() for r in verification.checks] + retest_rows,
        }
        corrected_outputs.pop("outcome_class", None)
        patched_result_holder["patched_result"] = dataclasses.replace(
            result,
            status=TaskResultStatus.SUCCEEDED,
            outputs=corrected_outputs,
            error=None,
            outcome_class=None,
        )
        return "accept_patch"

    async def _collect_artifacts_and_checkpoint(
        self,
        result: TaskResult,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
    ) -> None:
        """Collect artifacts from a successful task and save a checkpoint."""
        # Collect artifacts (with producing_task_type metadata)
        new_refs: list[str] = []
        for art in (result.outputs or {}).get("artifacts", []):
            ref = await self._store_artifact(
                art,
                cycle,
                run_id,
                envelope,
                producing_task_type=envelope.task_type,
            )
            new_refs.append(ref.artifact_id)
            all_artifact_refs.append(ref.artifact_id)
            stored_artifacts.append((ref.artifact_id, ref))

        if new_refs:
            await self._cycle_registry.append_artifact_refs(run_id, tuple(new_refs))

        # Chain outputs by role
        role = envelope.metadata.get("role", "unknown")
        prior_outputs[role] = {k: v for k, v in (result.outputs or {}).items() if k != "artifacts"}

        # SIP-0079: Checkpoint after successful task (RC-4)
        completed_task_ids.append(envelope.task_id)
        checkpoint_index = len(completed_task_ids)
        new_checkpoint = RunCheckpoint(
            run_id=run_id,
            checkpoint_index=checkpoint_index,
            completed_task_ids=tuple(completed_task_ids),
            prior_outputs=dict(prior_outputs),
            artifact_refs=tuple(all_artifact_refs),
            plan_delta_refs=tuple(plan_delta_refs),
            created_at=datetime.now(UTC),
        )
        await self._cycle_registry.save_checkpoint(new_checkpoint)
        self._cycle_event_bus.emit(
            EventType.CHECKPOINT_CREATED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={
                "checkpoint_index": checkpoint_index,
                "completed_task_id": envelope.task_id,
            },
        )

    # ------------------------------------------------------------------
    # Extracted helpers for execute_run
    # ------------------------------------------------------------------

    async def _prepare_cycle_for_run(
        self,
        cycle_id: str,
        run_id: str,
        forwarding_overrides: dict | None = None,
    ) -> tuple[Cycle, str]:
        """Load cycle, merge forwarding overrides, resolve PRD, materialize run root.

        Returns (cycle, run_root).
        """
        import dataclasses as _dc

        cycle = await self._cycle_registry.get_cycle(cycle_id)
        # SIP-0083: merge forwarding overrides from multi-workload orchestration
        # (threaded per-run from execute_cycle, SIP-0097 §6.6 — not executor state)
        if forwarding_overrides:
            cycle = _dc.replace(
                cycle,
                execution_overrides={
                    **cycle.execution_overrides,
                    **forwarding_overrides,
                },
            )

        # Resolve PRD content — if prd_ref is an artifact ID, fetch the
        # actual content so handlers receive the PRD text, not just the ID.
        prd_content = cycle.prd_ref
        if prd_content and prd_content.startswith("art_") and self._artifact_vault:
            try:
                _, raw = await self._artifact_vault.retrieve(prd_content)
                prd_content = raw.decode("utf-8", errors="replace")
            except Exception:
                logger.warning(
                    "Failed to resolve PRD artifact %s, falling back to ID",
                    prd_content,
                    exc_info=True,
                )
        if not prd_content:
            prd_content = await self._resolve_prd_from_project(cycle.project_id)
        if prd_content and prd_content != cycle.prd_ref:
            cycle = _dc.replace(cycle, prd_ref=prd_content)

        # Materialize run_root directory with seed files (PRD)
        run_root = await self._materialize_run_root(cycle, run_id)
        return cycle, run_root

    async def _init_run_observability(
        self,
        cycle_id: str,
        run_id: str,
        cycle: Cycle,
        plan: list[TaskEnvelope],
    ) -> tuple[Any, str | None]:
        """Set up LangFuse trace and Prefect flow run.

        Returns (obs_ctx, flow_run_id). Either may be None.
        """
        obs_ctx = None
        flow_run_id = None

        # LangFuse: open cycle trace keyed by shared trace_id
        trace_id = plan[0].trace_id if plan else None
        if self._llm_observability:
            from squadops.telemetry.models import CorrelationContext, StructuredEvent

            obs_ctx = CorrelationContext(cycle_id=cycle_id, trace_id=trace_id)
            self._llm_observability.start_cycle_trace(obs_ctx)
            self._llm_observability.record_event(
                obs_ctx,
                StructuredEvent(
                    name="cycle.started",
                    message=f"Cycle {cycle_id} started ({len(plan)} tasks, dispatched)",
                ),
            )

        # Prefect: create flow run
        if self._workflow_tracker:
            try:
                flow_id = await self._workflow_tracker.ensure_flow()
                flow_run_id = await self._workflow_tracker.create_flow_run(
                    flow_id,
                    run_name=flow_run_name(cycle.project_id, cycle_id, run_id),
                    parameters={
                        "cycle_id": cycle_id,
                        "run_id": run_id,
                        "project_id": cycle.project_id,
                    },
                )
                await self._workflow_tracker.set_flow_run_state(flow_run_id, "RUNNING", "Running")
            except Exception:
                logger.warning("Prefect flow run creation failed", exc_info=True)

        return obs_ctx, flow_run_id

    async def _execute_fan_out(
        self,
        plan: list[TaskEnvelope],
        run_id: str,
        cycle: Cycle,
        flow_run_id: str | None = None,
    ) -> None:
        """Fan-out/fan-in: dispatch all tasks concurrently, await all."""

        if await self._is_cancelled(run_id):
            raise _CancellationError(run_id)

        tasks = []
        task_run_ids: list[str | None] = []
        for envelope in plan:
            # SIP-0087: create Prefect task_run here so task_run_id is in the
            # TASK_DISPATCHED context and visible to the contextvar scope.
            task_run_id = await self._task_dispatcher.create_task_run_if_enabled(
                flow_run_id, envelope
            )
            task_run_ids.append(task_run_id)

            self._cycle_event_bus.emit(
                EventType.TASK_DISPATCHED,
                entity_type="task",
                entity_id=envelope.task_id,
                context={
                    "cycle_id": cycle.cycle_id,
                    "run_id": run_id,
                    "flow_run_id": flow_run_id or "",
                    "task_run_id": task_run_id or "",
                },
                payload={
                    "task_type": envelope.task_type,
                    "task_name": build_task_name(envelope),
                },
            )
            enriched = dataclasses.replace(
                envelope,
                inputs={**envelope.inputs, "prior_outputs": {}, "artifact_refs": []},
            )
            tasks.append(
                self._task_dispatcher.dispatch_task(
                    enriched,
                    run_id,
                    flow_run_id=flow_run_id,
                    task_run_id=task_run_id,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # SIP-0096 Phase 2 slice-1 gap: this fan-out path does NOT yet record
        # verification evidence to the run ledger (the sequential path does, at the
        # dispatch-with-retry seam). Harmless while the throttle is off (no shipped
        # profile declares required_checks) — a FAN_OUT_FAN_IN cycle simply records
        # zero evidence, same as pre-Phase-2. MUST be wired before slice 4 turns the
        # throttle on, or a required check would falsely block here. Tracked in #375.
        all_artifact_refs: list[str] = []
        for i, result in enumerate(results):
            task_context = {
                "cycle_id": cycle.cycle_id,
                "run_id": run_id,
                "task_run_id": task_run_ids[i] or "",
            }
            if isinstance(result, Exception):
                self._cycle_event_bus.emit(
                    EventType.TASK_FAILED,
                    entity_type="task",
                    entity_id=plan[i].task_id,
                    context=task_context,
                    payload={"task_type": plan[i].task_type, "error": str(result)},
                )
                raise _ExecutionError(f"Task {plan[i].task_id} raised exception: {result}")
            if result.status == "SUCCEEDED":
                self._cycle_event_bus.emit(
                    EventType.TASK_SUCCEEDED,
                    entity_type="task",
                    entity_id=plan[i].task_id,
                    context=task_context,
                    payload={"task_type": plan[i].task_type},
                )
            else:
                self._cycle_event_bus.emit(
                    EventType.TASK_FAILED,
                    entity_type="task",
                    entity_id=plan[i].task_id,
                    context=task_context,
                    payload={"task_type": plan[i].task_type, "error": result.error or ""},
                )
            if result.status != "SUCCEEDED":
                raise _ExecutionError(f"Task {plan[i].task_id} failed: {result.error}")
            for art in (result.outputs or {}).get("artifacts", []):
                ref = await self._store_artifact(art, cycle, run_id, plan[i])
                all_artifact_refs.append(ref.artifact_id)

        if all_artifact_refs:
            await self._cycle_registry.append_artifact_refs(run_id, tuple(all_artifact_refs))

    # ------------------------------------------------------------------
    # Gate handling
    # ------------------------------------------------------------------

    def _is_gate_boundary(self, cycle: Cycle, task_type: str) -> bool:
        """Check if completed task_type triggers a gate."""
        for gate in cycle.task_flow_policy.gates:
            if task_type in gate.after_task_types:
                return True
        return False

    async def _handle_gate(
        self,
        run_id: str,
        cycle: Cycle,
        task_type: str,
        *,
        stored_artifacts: list[tuple[str, ArtifactRef]] | None = None,
        profile: Any = None,
    ) -> None:
        """Pause, poll for decision, resume or reject.

        #295 (SIP-0097 slice 6): before pausing for review, a materialized
        implementation plan naming a role the squad can't satisfy is rejected
        here — the operator is never asked to approve an unsatisfiable plan,
        and the failure lands at the gate instead of mid-implementation
        dispatch. The dispatch-time check in generate_task_plan remains the
        final net.
        """
        gate_names = [
            g.name for g in cycle.task_flow_policy.gates if task_type in g.after_task_types
        ]
        if stored_artifacts and profile is not None:
            await self._reject_unsatisfiable_plan_at_gate(
                stored_artifacts, profile, gate_names, cycle
            )
        logger.info("Run %s paused at gate(s): %s", run_id, gate_names)
        await self._cycle_registry.update_run_status(run_id, RunStatus.PAUSED)
        self._cycle_event_bus.emit(
            EventType.RUN_PAUSED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={"gate_names": gate_names},
        )

        poll_interval = 2.0
        while True:
            if await self._is_cancelled(run_id):
                raise _CancellationError(run_id)

            run = await self._cycle_registry.get_run(run_id)
            for gate_name in gate_names:
                for decision in run.gate_decisions:
                    if decision.gate_name == gate_name:
                        if decision.decision in (
                            GateDecisionValue.APPROVED,
                            GateDecisionValue.APPROVED_WITH_REFINEMENTS,
                        ):
                            await self._cycle_registry.update_run_status(run_id, RunStatus.RUNNING)
                            self._cycle_event_bus.emit(
                                EventType.RUN_RESUMED,
                                entity_type="run",
                                entity_id=run_id,
                                context={"cycle_id": cycle.cycle_id, "run_id": run_id},
                                payload={"gate_name": gate_name},
                            )
                            logger.info(
                                "Gate %r %s, resuming run %s",
                                gate_name,
                                decision.decision,
                                run_id,
                            )
                            return
                        elif decision.decision == GateDecisionValue.REJECTED:
                            raise _ExecutionError(f"Gate {gate_name!r} rejected: {decision.notes}")
                        elif decision.decision == GateDecisionValue.RETURNED_FOR_REVISION:
                            raise _ExecutionError(
                                f"Gate {gate_name!r} returned_for_revision: "
                                "returned_for_revision requires manual retry-run "
                                "creation; automatic retry-in-same-phase is not "
                                "implemented in this version."
                            )

            await asyncio.sleep(poll_interval)

    async def _reject_invalid_plan_before_workload_gate(
        self,
        run: Any,
        cycle: Cycle,
        gate_name: str,
    ) -> None:
        """#464: criteria-scope validation at the inter-workload plan gate.

        This is the gate path multi-workload cycles actually traverse (the
        framing run COMPLETES, then the sequence gates) — the mid-run
        ``_reject_unsatisfiable_plan_at_gate`` never fires here. Searches the
        completed run's artifacts for the authored plan and rejects the
        sequence before the operator is asked to review a mechanically doomed
        plan. Role validation is not duplicated at this seam: it keeps its
        dispatch-time net in ``generate_task_plan``, which fails the next
        workload within seconds. Absent or unreadable plans defer to that same
        net — this check only ever adds an earlier rejection, never a pass.
        """
        if not cycle.applied_defaults.get("implementation_plan", False):
            return

        from squadops.cycles.implementation_plan import ImplementationPlan

        for ref_id in tuple(run.artifact_refs or ()):
            try:
                ref, content_bytes = await self._artifact_vault.retrieve(ref_id)
            except Exception:
                continue
            if ref.filename == "implementation_plan.yaml" or (
                getattr(ref, "artifact_type", None) == "control_implementation_plan"
            ):
                try:
                    plan = ImplementationPlan.from_yaml(content_bytes.decode(errors="replace"))
                except Exception:
                    logger.warning(
                        "Plan artifact %s unreadable before gate %r — deferring to the "
                        "dispatch-time validation net",
                        ref_id,
                        gate_name,
                        exc_info=True,
                    )
                    return
                errors = plan.validate_criteria_scope()
                if errors:
                    raise _ExecutionError(
                        f"Plan rejected before gate {gate_name!r}: " + "; ".join(errors)
                    )
                return

    async def _reject_unsatisfiable_plan_at_gate(
        self,
        stored_artifacts: list[tuple[str, ArtifactRef]],
        profile: Any,
        gate_names: list[str],
        cycle: Cycle,
    ) -> None:
        """#295: fail fast when the materialized plan can't be satisfied.

        Looks for the run's authored ``implementation_plan.yaml`` /
        ``control_implementation_plan`` artifact (same detection as
        ``_load_plan_for_run``) and validates its roles against the squad
        profile. Keyed on plan presence, not the gate's name, so it holds
        across the ``progress_plan_review`` / ``plan-review`` naming variants.
        An absent or unreadable plan defers to the dispatch-time net —
        this check only ever *adds* an earlier rejection, never a pass.
        """
        if not cycle.applied_defaults.get("implementation_plan", False):
            return

        from squadops.cycles.implementation_plan import ImplementationPlan

        plan = None
        for artifact_id, ref in stored_artifacts:
            if ref.filename == "implementation_plan.yaml" or (
                hasattr(ref, "artifact_type") and ref.artifact_type == "control_implementation_plan"
            ):
                try:
                    _, content_bytes = await self._artifact_vault.retrieve(artifact_id)
                    plan = ImplementationPlan.from_yaml(content_bytes.decode(errors="replace"))
                except Exception:
                    logger.warning(
                        "Plan artifact %s unreadable at gate(s) %s — deferring to the "
                        "dispatch-time validation net",
                        artifact_id,
                        gate_names,
                        exc_info=True,
                    )
                    return
                break
        if plan is None:
            return

        errors = plan.validate_against_profile(profile)
        # #464: criteria-scope validation rides the same fail-fast seam — a
        # style-lottery regex costs seconds at the gate, not an hour of
        # correction budget mid-implementation.
        errors += plan.validate_criteria_scope()
        if errors:
            raise _ExecutionError(
                f"Plan rejected at gate(s) {gate_names}: the materialized implementation "
                f"plan fails gate validation against squad profile {profile.profile_id!r} — "
                + "; ".join(errors)
                + ". Fix the plan: roles must exist in the profile, and regex criteria "
                "may only target document artifacts."
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _is_cancelled(self, run_id: str) -> bool:
        """Check local fast-path set AND registry state."""
        if run_id in self._cancelled:
            return True
        run = await self._cycle_registry.get_run(run_id)
        if run.status == RunStatus.CANCELLED.value:
            self._cancelled.add(run_id)
            return True
        return False

    async def _store_artifact(
        self,
        art_dict: dict[str, Any],
        cycle: Cycle,
        run_id: str,
        envelope: TaskEnvelope,
        producing_task_type: str | None = None,
    ) -> ArtifactRef:
        """Store a task output artifact in the vault."""
        content = art_dict.get("content", "").encode("utf-8")
        metadata: dict[str, Any] = {
            "task_id": envelope.task_id,
            "role": envelope.metadata.get("role"),
        }
        if producing_task_type:
            metadata["producing_task_type"] = producing_task_type
        ref = ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=cycle.project_id,
            artifact_type=art_dict.get("type", "document"),
            filename=art_dict["name"],
            content_hash=sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type=art_dict.get("media_type", "text/markdown"),
            created_at=datetime.now(UTC),
            cycle_id=cycle.cycle_id,
            run_id=run_id,
            metadata=metadata,
        )
        return await self._artifact_vault.store(ref, content)

    async def _materialize_run_root(self, cycle: Cycle, run_id: str) -> str:
        """Create a run_root directory and write seed files (e.g. PRD).

        Returns the absolute path to the run_root directory.
        """
        import tempfile
        from pathlib import Path

        base_dir = os.environ.get("SQUADOPS_RUN_ROOT")
        if base_dir:
            run_root = Path(base_dir) / run_id
        else:
            run_root = Path(tempfile.gettempdir()) / "squadops" / "runs" / run_id
        run_root.mkdir(parents=True, exist_ok=True)

        # Write PRD to disk if available
        prd_ref = cycle.prd_ref
        if prd_ref:
            prd_path = run_root / "prd.md"
            if prd_ref.startswith("art_") and self._artifact_vault:
                # Artifact ID — fetch content from vault
                try:
                    _, content = await self._artifact_vault.retrieve(prd_ref)
                    prd_path.write_bytes(content)
                    logger.info("Materialized PRD %s to %s", prd_ref, prd_path)
                except Exception:
                    logger.warning("Failed to materialize PRD %s", prd_ref, exc_info=True)
            else:
                # Inline PRD content
                prd_path.write_text(prd_ref, encoding="utf-8")
                logger.info("Wrote inline PRD to %s", prd_path)

        return str(run_root)

    async def _resolve_prd_from_project(self, project_id: str) -> str | None:
        """Load PRD content from project's prd_path if configured."""
        if not self._project_registry:
            return None
        try:
            from pathlib import Path

            project = await self._project_registry.get_project(project_id)
            if not project.prd_path:
                return None
            prd_file = Path(project.prd_path)
            if not prd_file.exists():
                logger.warning("PRD file not found: %s", prd_file)
                return None
            return prd_file.read_text(encoding="utf-8")
        except Exception:
            logger.warning("Failed to resolve PRD for project %s", project_id, exc_info=True)
            return None

    async def _safe_transition(self, run_id: str, status: RunStatus) -> None:
        """Attempt status transition, logging but not raising on failure."""
        try:
            await self._cycle_registry.update_run_status(run_id, status)
        except Exception:
            logger.warning(
                "Failed to transition run %s to %s",
                run_id,
                status.value,
                exc_info=True,
            )
