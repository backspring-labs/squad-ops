"""
Distributed flow executor adapter.

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
import json
import logging
import os
import time
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import ArtifactRef, Cycle, GateDecisionValue, Run, RunStatus
from squadops.cycles.plan_delta import PlanDelta
from squadops.cycles.pulse_models import (
    CADENCE_BOUNDARY_ID,
    CadencePolicy,
    PulseDecision,
    SuiteOutcome,
    parse_pulse_checks,
)
from squadops.cycles.pulse_verification import (
    build_repair_task_envelopes,
    collect_cadence_bound_suites,
    determine_boundary_decision,
    resolve_milestone_bindings,
    run_pulse_verification,
)
from squadops.cycles.task_outcome import TaskOutcome
from squadops.cycles.task_plan import generate_task_plan
from squadops.events.types import EventType
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.tasks.models import TaskEnvelope, TaskResult
from squadops.telemetry.context import use_correlation_context, use_run_ids
from squadops.telemetry.models import CorrelationContext

if TYPE_CHECKING:
    from squadops.capabilities.acceptance import AcceptanceCheckEngine
    from squadops.capabilities.models import AcceptanceContext
    from squadops.cycles.models import GateDecision, SquadProfile
    from squadops.cycles.pulse_models import PulseCheckDefinition, PulseVerificationRecord
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.cycles.squad_profile import SquadProfilePort
    from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort

logger = logging.getLogger(__name__)


class _ExecutionError(Exception):
    """Internal: task failure or gate rejection."""


class _CancellationError(Exception):
    """Internal: run was cancelled."""


class _PausedError(Exception):
    """Internal: run paused due to BLOCKED outcome."""


class DistributedFlowExecutor(FlowExecutionPort):
    """Flow executor that dispatches tasks to agent containers via RabbitMQ.

    Uses a request/reply pattern: publishes a ``comms.task`` message to
    ``{agent_id}_comms``, then consumes the ``TaskResult`` from a per-run
    reply queue (``cycle_results_{run_id}``).
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
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._queue = queue
        self._squad_profile = squad_profile
        self._project_registry = project_registry
        self._task_timeout = task_timeout
        self._llm_observability = llm_observability
        self._workflow_tracker = workflow_tracker
        self._cancelled: set[str] = set()

        # SIP-0077: Cycle event bus (defaults to NoOp if not provided)
        if event_bus is None:
            from adapters.events.noop_cycle_event_bus import NoOpCycleEventBus

            event_bus = NoOpCycleEventBus()
        self._cycle_event_bus = event_bus
        # Accumulated per-run pulse verification summaries for run report.
        # Reset at the start of each execute_run().
        self._pulse_report_entries: list[dict[str, Any]] = []
        # SIP-0083: forwarding overrides set by execute_cycle() before
        # calling execute_run() for subsequent workloads. Merged into
        # cycle.execution_overrides via dataclasses.replace().
        self._forwarding_overrides: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_run(self, cycle_id: str, run_id: str, profile_id: str | None = None) -> None:
        """Execute a run by dispatching tasks to agent containers via RabbitMQ."""
        obs_ctx = None
        flow_run_id = None
        terminal_status = "COMPLETED"
        self._pulse_report_entries = []
        cycle = None
        plan = None

        try:
            cycle, run_root = await self._prepare_cycle_for_run(cycle_id, run_id)
            run = await self._cycle_registry.get_run(run_id)
            profile, _ = await self._squad_profile.resolve_snapshot(profile_id)

            # queued/failed/paused -> running
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
            # _dispatch_task nests its own per-task scope inside this one.
            flow_ctx = CorrelationContext(cycle_id=cycle_id, flow_run_id=flow_run_id)
            with use_correlation_context(flow_ctx):
                logger.info(
                    "Executing run %s for cycle %s (%d tasks, mode=%s, dispatch=distributed)",
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

        except _CancellationError:
            terminal_status = "CANCELLED"
            await self._safe_transition(run_id, RunStatus.CANCELLED)
            self._cycle_event_bus.emit(
                EventType.RUN_CANCELLED,
                entity_type="run",
                entity_id=run_id,
                context={"cycle_id": cycle_id, "run_id": run_id},
            )
            logger.info("Run %s cancelled", run_id)

        except _PausedError:
            terminal_status = "PAUSED"
            await self._safe_transition(run_id, RunStatus.PAUSED)
            self._cycle_event_bus.emit(
                EventType.RUN_PAUSED,
                entity_type="run",
                entity_id=run_id,
                context={"cycle_id": cycle_id, "run_id": run_id},
            )
            logger.info("Run %s paused", run_id)

        except _ExecutionError as exc:
            terminal_status = "FAILED"
            await self._safe_transition(run_id, RunStatus.FAILED)
            self._cycle_event_bus.emit(
                EventType.RUN_FAILED,
                entity_type="run",
                entity_id=run_id,
                context={"cycle_id": cycle_id, "run_id": run_id},
                payload={"error": str(exc)},
            )
            logger.error("Run %s failed: %s", run_id, exc)

        except Exception as exc:
            terminal_status = "FAILED"
            await self._safe_transition(run_id, RunStatus.FAILED)
            self._cycle_event_bus.emit(
                EventType.RUN_FAILED,
                entity_type="run",
                entity_id=run_id,
                context={"cycle_id": cycle_id, "run_id": run_id},
                payload={"error": str(exc)},
            )
            logger.exception("Run %s failed with unexpected error: %s", run_id, exc)

        finally:
            await self._finalize_run(
                cycle_id,
                run_id,
                terminal_status,
                obs_ctx,
                flow_run_id,
                cycle=cycle,
                plan=plan,
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

        current_run_id = first_run_id
        for i, workload_entry in enumerate(workload_sequence):
            await self.execute_run(cycle_id, current_run_id, profile_id)

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
            self._forwarding_overrides = await self._build_forwarding_overrides(
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
    # Dispatch
    # ------------------------------------------------------------------

    # SIP-0087: task-run lifecycle lives here (moved out of WorkflowTrackerBridge) so
    # the task_run_id is known before the agent starts producing logs.
    @staticmethod
    def _build_task_name(role: str, envelope: TaskEnvelope) -> str:
        """Build a Gantt-friendly Prefect task name.

        Focused-mode envelopes (manifest-decomposed subtasks) get
        ``role[idx]: focus`` so the Gantt distinguishes parallel subtasks
        instead of showing N identical ``role: task_type`` rows.
        Legacy / non-focused envelopes keep ``role: task_type``.
        """
        inputs = envelope.inputs or {}
        focus = inputs.get("subtask_focus")
        idx = inputs.get("subtask_index")
        if focus:
            focus_short = str(focus)[:60]
            return f"{role}[{idx}]: {focus_short}" if idx is not None else f"{role}: {focus_short}"
        return f"{role}: {envelope.task_type}"

    async def _create_task_run_if_enabled(
        self,
        flow_run_id: str | None,
        envelope: TaskEnvelope,
    ) -> str | None:
        """Create a Prefect task_run + set RUNNING. Returns task_run_id or None."""
        if self._workflow_tracker is None or not flow_run_id:
            return None
        role = envelope.metadata.get("role", "unknown") if envelope.metadata else "unknown"
        task_name = self._build_task_name(role, envelope)
        task_run_id = await self._workflow_tracker.create_task_run(
            flow_run_id, envelope.task_id, task_name
        )
        await self._workflow_tracker.set_task_run_state(task_run_id, "RUNNING", "Running")
        return task_run_id

    async def _task_heartbeat(
        self,
        envelope: TaskEnvelope,
        *,
        interval: float,
    ) -> None:
        """Log a heartbeat line every ``interval`` seconds until cancelled.

        Runs inside the task's ``use_run_ids`` scope (contextvars copy across
        ``asyncio.create_task``), so emitted records carry the active
        flow_run_id + task_run_id and land in the right Prefect pane.
        """
        start = time.monotonic()
        capability_id = (
            envelope.metadata.get("capability_id", envelope.task_type)
            if envelope.metadata
            else envelope.task_type
        )
        while True:
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - start
            logger.info(
                "task_heartbeat elapsed=%.1fs capability_id=%s task_id=%s",
                elapsed,
                capability_id,
                envelope.task_id,
            )

    async def _dispatch_task(
        self,
        envelope: TaskEnvelope,
        run_id: str,
        *,
        flow_run_id: str | None = None,
        task_run_id: str | None = None,
        heartbeat_interval: float = 30.0,
    ) -> TaskResult:
        """Publish task to agent queue, wait for result on reply queue.

        If ``task_run_id`` is not supplied but ``flow_run_id`` is and a
        :class:`WorkflowTrackerPort` is wired, one is created here — supports
        correction/repair paths that don't pre-create the workflow run.

        Enters a ``CorrelationContext`` scope with flow/task run IDs so the
        ``PrefectLogHandler`` scopes handler logs to the right Prefect task
        pane, and spawns a periodic heartbeat coroutine so long-running LLM
        calls show liveness in the UI.
        """
        if task_run_id is None:
            task_run_id = await self._create_task_run_if_enabled(flow_run_id, envelope)

        # SIP-0087 B1: propagate run IDs to the agent over the wire so the
        # agent's PrefectLogHandler can scope handler logs to the right task
        # pane. The agent enters use_correlation_context(...) on receipt.
        envelope = dataclasses.replace(
            envelope,
            flow_run_id=flow_run_id or "",
            task_run_id=task_run_id or "",
        )

        base_ctx = CorrelationContext.from_envelope(
            envelope,
            agent_id=envelope.agent_id or "",
            agent_role=(envelope.metadata.get("role") if envelope.metadata else None),
        )

        with (
            use_correlation_context(base_ctx),
            use_run_ids(flow_run_id=flow_run_id, task_run_id=task_run_id),
        ):
            heartbeat = asyncio.create_task(
                self._task_heartbeat(envelope, interval=heartbeat_interval),
                name=f"prefect-heartbeat-{envelope.task_id}",
            )
            try:
                return await self._publish_and_await(envelope, run_id)
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass

    async def _publish_and_await(
        self,
        envelope: TaskEnvelope,
        run_id: str,
    ) -> TaskResult:
        """Dispatch over the queue and poll the reply queue for a result."""
        reply_queue = f"cycle_results_{run_id}"

        message = {
            "action": "comms.task",
            "metadata": {
                "reply_queue": reply_queue,
                "correlation_id": envelope.correlation_id,
            },
            "payload": envelope.to_dict(),
        }

        queue_name = f"{envelope.agent_id}_comms"
        await self._queue.publish(queue_name, json.dumps(message))

        logger.info(
            "Dispatched task %s (%s) to %s, awaiting reply on %s",
            envelope.task_id,
            envelope.task_type,
            queue_name,
            reply_queue,
        )

        deadline = time.monotonic() + self._task_timeout
        # Block on the reply queue in long chunks so a single consumer
        # registration covers each chunk — avoids the consumer-tag churn
        # of poll-and-sleep that previously raced with arriving replies.
        # Cap each chunk well below typical broker idle-disconnect windows.
        chunk_seconds = 30.0

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            wait = min(chunk_seconds, remaining)

            try:
                messages = await self._queue.consume_blocking(
                    reply_queue, timeout=wait, max_messages=1
                )
            except Exception as exc:
                # Channel went stale or broker hiccup. Drop the cached
                # queue handle and back off briefly before retrying so
                # the next call re-declares against a fresh channel.
                logger.warning(
                    "consume_blocking on %s failed (%s); invalidating cache and retrying",
                    reply_queue,
                    exc,
                )
                try:
                    await self._queue.invalidate_queue(reply_queue)
                except Exception:
                    logger.debug("invalidate_queue raised; continuing", exc_info=True)
                await asyncio.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
                continue

            for msg in messages:
                data = json.loads(msg.payload)
                result_data = data.get("payload", {})
                if result_data.get("task_id") == envelope.task_id:
                    await self._queue.ack(msg)
                    return TaskResult.from_dict(result_data)
                # Not our message — ack to avoid blocking
                await self._queue.ack(msg)

        return TaskResult(
            task_id=envelope.task_id,
            status="FAILED",
            error=f"Timed out waiting for agent {envelope.agent_id} after {self._task_timeout}s",
        )

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
        },
        "qa.test": {
            # SIP-0086: include development.develop for manifest-driven QA
            # subtasks that need to see all prior build artifacts
            "by_producing_task": ["qa.validate", "builder.assemble", "development.develop"],
            "by_type": ["source", "config"],
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
        correction_attempts: int = 0
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
        agent_resolver = self._build_agent_resolver(profile)

        # ------------------------------------------------------------------
        # SIP-0070: Parse pulse checks + cadence policy from applied_defaults
        # ------------------------------------------------------------------
        pulse_ctx = self._setup_pulse_context(cycle, plan, obs_ctx)
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
            task_run_id = await self._create_task_run_if_enabled(flow_run_id, envelope)

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
                    "task_name": f"{envelope.metadata.get('role', 'unknown')}: {envelope.task_type}",
                },
            )

            # Dispatch + retry loop for retryable failures (SIP-0079)
            task_succeeded, result = await self._dispatch_with_retry(
                enriched=enriched,
                envelope=envelope,
                cycle=cycle,
                run_id=run_id,
                task_attempt_counts=task_attempt_counts,
                consecutive_failures=consecutive_failures,
                correction_attempts=correction_attempts,
                prior_outputs=prior_outputs,
                all_artifact_refs=all_artifact_refs,
                stored_artifacts=stored_artifacts,
                completed_task_ids=completed_task_ids,
                plan_delta_refs=plan_delta_refs,
                profile=profile,
                flow_run_id=flow_run_id,
                task_run_id=task_run_id,
            )

            if not task_succeeded:
                # SIP-0079: correction completed with continue/patch outcome.
                # Original flow: consecutive_failures was incremented before
                # correction, then reset to 0 on continue/patch. The increment
                # only survives on abort/rewind paths which raise inside
                # _handle_task_outcome before reaching here. Net effect: reset.
                consecutive_failures = 0
                correction_attempts += 1

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
                cadence_closed = self._evaluate_pulse_boundaries(
                    task_idx=task_idx,
                    plan=plan,
                    cadence_task_count=cadence_task_count,
                    cadence_start_time=cadence_start_time,
                    cadence=cadence,
                )
                await self._run_pulse_evaluations(
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
                )

                if cadence_closed:
                    cadence_interval_id += 1
                    cadence_task_count = 0
                    cadence_start_time = time.monotonic()

            # Post-task gate check (runs after verification)
            if self._is_gate_boundary(cycle, envelope.task_type):
                await self._handle_gate(run_id, cycle, envelope.task_type)

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

    @staticmethod
    def _build_agent_resolver(profile: SquadProfile | None) -> dict[str, str]:
        """Build a role → agent_id mapping from the squad profile."""
        if not profile:
            return {}
        return {agent.role: agent.agent_id for agent in profile.agents if agent.enabled}

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
        import dataclasses

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

    async def _dispatch_with_retry(
        self,
        enriched: TaskEnvelope,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        task_attempt_counts: dict[str, int],
        consecutive_failures: int,
        correction_attempts: int,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        profile: Any = None,
        flow_run_id: str | None = None,
        task_run_id: str | None = None,
    ) -> tuple[bool, TaskResult]:
        """Dispatch a task with retry loop for retryable failures.

        Returns (task_succeeded, result). Raises on unrecoverable failures.
        """
        while True:
            result = await self._dispatch_task(
                enriched,
                run_id,
                flow_run_id=flow_run_id,
                task_run_id=task_run_id,
            )

            # SIP-0087: task_run_id carried in context so the bridge can set
            # terminal Prefect state without owning the ID.
            task_context = {
                "cycle_id": cycle.cycle_id,
                "run_id": run_id,
                "task_run_id": task_run_id or "",
            }
            if result.status == "SUCCEEDED":
                self._cycle_event_bus.emit(
                    EventType.TASK_SUCCEEDED,
                    entity_type="task",
                    entity_id=envelope.task_id,
                    context=task_context,
                    payload={"task_type": envelope.task_type},
                )
            else:
                self._cycle_event_bus.emit(
                    EventType.TASK_FAILED,
                    entity_type="task",
                    entity_id=envelope.task_id,
                    context=task_context,
                    payload={
                        "task_type": envelope.task_type,
                        "error": result.error or "",
                    },
                )

            if result.status != "SUCCEEDED":
                action = await self._handle_task_outcome(
                    result=result,
                    envelope=envelope,
                    cycle=cycle,
                    run_id=run_id,
                    task_attempt_counts=task_attempt_counts,
                    consecutive_failures=consecutive_failures,
                    correction_attempts=correction_attempts,
                    prior_outputs=prior_outputs,
                    all_artifact_refs=all_artifact_refs,
                    stored_artifacts=stored_artifacts,
                    completed_task_ids=completed_task_ids,
                    plan_delta_refs=plan_delta_refs,
                    profile=profile,
                    flow_run_id=flow_run_id,
                )

                if action == "continue":
                    continue  # retry same task
                elif action == "break_correction":
                    return False, result

                # "raise" actions handled inside _handle_task_outcome

            return True, result

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

    def _setup_pulse_context(
        self,
        cycle: Cycle,
        plan: list[TaskEnvelope],
        obs_ctx: Any,
    ) -> dict[str, Any]:
        """Parse pulse checks and cadence policy from applied_defaults.

        Returns a dict with keys: milestone_bindings, cadence_suites,
        has_pulse_checks, cadence, engine.
        """
        raw_pulse_checks = cycle.applied_defaults.get("pulse_checks", [])
        raw_cadence = cycle.applied_defaults.get("cadence_policy", {})

        pulse_checks = parse_pulse_checks(raw_pulse_checks) if raw_pulse_checks else ()
        cadence = (
            CadencePolicy(
                max_pulse_seconds=raw_cadence.get("max_pulse_seconds", 600),
                max_tasks_per_pulse=raw_cadence.get("max_tasks_per_pulse", 5),
            )
            if raw_cadence
            else CadencePolicy()
        )

        milestone_bindings: dict[int, list] = {}
        cadence_suites: list = []
        has_pulse_checks = bool(pulse_checks)

        if has_pulse_checks:
            milestone_bindings, unmatched = resolve_milestone_bindings(pulse_checks, plan)
            cadence_suites = collect_cadence_bound_suites(pulse_checks)

            for suite in unmatched:
                logger.warning(
                    "Pulse suite %r (boundary_id=%r) has no matching task_type in plan — skipping",
                    suite.suite_id,
                    suite.boundary_id,
                )
                self._emit_pulse_event(
                    obs_ctx,
                    "pulse_check.binding_skipped",
                    f"Suite {suite.suite_id!r} unmatched: after_task_types "
                    f"{suite.after_task_types!r} not in plan",
                    suite_id=suite.suite_id,
                    boundary_id=suite.boundary_id,
                )

        engine = None
        if has_pulse_checks:
            from pathlib import Path

            from squadops.capabilities.acceptance import AcceptanceCheckEngine

            engine = AcceptanceCheckEngine(chroot=Path.cwd())

        return {
            "milestone_bindings": milestone_bindings,
            "cadence_suites": cadence_suites,
            "has_pulse_checks": has_pulse_checks,
            "cadence": cadence,
            "engine": engine,
        }

    async def _handle_task_outcome(
        self,
        result: TaskResult,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        task_attempt_counts: dict[str, int],
        consecutive_failures: int,
        correction_attempts: int,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        profile: Any = None,
        flow_run_id: str | None = None,
    ) -> str:
        """Route a failed task outcome. Returns an action string.

        Returns:
            "continue" — retry the same task (caller continues while loop)
            "break_correction" — correction handled, advance to next task

        Raises:
            _PausedError — task is blocked
            _ExecutionError — unrecoverable failure
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

        # D9: contract task failure → immediate abort, no correction
        if envelope.task_type == "governance.establish_contract":
            raise _ExecutionError(
                f"Contract task {envelope.task_id} failed (no correction): {result.error}"
            )

        # Trigger correction protocol
        max_corrections = cycle.applied_defaults.get("max_correction_attempts", 2)

        if correction_attempts >= max_corrections:
            raise _ExecutionError(f"Max correction attempts ({max_corrections}) exhausted")

        correction_path = await self._run_correction_protocol(
            run_id=run_id,
            cycle=cycle,
            envelope=envelope,
            result=result,
            correction_attempts=correction_attempts,
            prior_outputs=prior_outputs,
            all_artifact_refs=all_artifact_refs,
            stored_artifacts=stored_artifacts,
            completed_task_ids=completed_task_ids,
            plan_delta_refs=plan_delta_refs,
            profile=profile,
            flow_run_id=flow_run_id,
        )

        if correction_path == "abort":
            raise _ExecutionError(
                f"Correction protocol decided to abort after {envelope.task_type} failure"
            )
        elif correction_path == "rewind":
            raise _ExecutionError(f"Rewinding to checkpoint after {envelope.task_type} failure")
        elif correction_path in ("continue", "patch"):
            return "break_correction"
        else:
            raise _ExecutionError(f"Unknown correction path: {correction_path}")

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

    def _evaluate_pulse_boundaries(
        self,
        task_idx: int,
        plan: list[TaskEnvelope],
        cadence_task_count: int,
        cadence_start_time: float,
        cadence: CadencePolicy,
    ) -> bool:
        """Determine whether the cadence boundary has closed."""
        elapsed = time.monotonic() - cadence_start_time
        is_last_task = task_idx == len(plan) - 1
        return (
            cadence_task_count >= cadence.max_tasks_per_pulse
            or elapsed >= cadence.max_pulse_seconds
            or is_last_task
        )

    async def _run_pulse_evaluations(
        self,
        task_idx: int,
        milestone_bindings: dict,
        cadence_suites: list,
        cadence_closed: bool,
        cadence_interval_id: int,
        run_id: str,
        cycle: Cycle,
        obs_ctx: Any,
        engine: Any,
        envelope: TaskEnvelope,
        prior_outputs: dict[str, Any],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        all_artifact_refs: list[str],
        flow_run_id: str | None,
        agent_resolver: dict[str, str],
        run_root: str,
    ) -> None:
        """Run milestone and cadence pulse evaluations at the current boundary."""
        from squadops.capabilities.models import AcceptanceContext

        acc_ctx = AcceptanceContext(
            run_root=run_root,
            cycle_id=cycle.cycle_id,
            workload_id=cycle.cycle_id,
            run_id=run_id,
        )

        max_repair_attempts = cycle.applied_defaults.get(
            "max_repair_attempts",
            2,
        )

        # --- Milestone boundary check ---
        if task_idx in milestone_bindings:
            bound_suites = milestone_bindings[task_idx]
            for suite in bound_suites:
                await self._verify_with_repair(
                    suites=[suite],
                    boundary_id=suite.boundary_id,
                    cadence_interval_id=cadence_interval_id,
                    run_id=run_id,
                    cycle=cycle,
                    obs_ctx=obs_ctx,
                    engine=engine,
                    context=acc_ctx,
                    envelope=envelope,
                    prior_outputs=prior_outputs,
                    stored_artifacts=stored_artifacts,
                    all_artifact_refs=all_artifact_refs,
                    max_repair_attempts=max_repair_attempts,
                    flow_run_id=flow_run_id,
                    agent_resolver=agent_resolver,
                )

        # --- Cadence close check ---
        if cadence_closed and cadence_suites:
            await self._verify_with_repair(
                suites=cadence_suites,
                boundary_id=CADENCE_BOUNDARY_ID,
                cadence_interval_id=cadence_interval_id,
                run_id=run_id,
                cycle=cycle,
                obs_ctx=obs_ctx,
                engine=engine,
                context=acc_ctx,
                envelope=envelope,
                prior_outputs=prior_outputs,
                stored_artifacts=stored_artifacts,
                all_artifact_refs=all_artifact_refs,
                max_repair_attempts=max_repair_attempts,
                flow_run_id=flow_run_id,
                agent_resolver=agent_resolver,
            )

    # ------------------------------------------------------------------
    # Extracted helpers for execute_run
    # ------------------------------------------------------------------

    async def _prepare_cycle_for_run(self, cycle_id: str, run_id: str) -> tuple[Cycle, str]:
        """Load cycle, merge forwarding overrides, resolve PRD, materialize run root.

        Returns (cycle, run_root).
        """
        import dataclasses as _dc

        cycle = await self._cycle_registry.get_cycle(cycle_id)
        # SIP-0083: merge forwarding overrides from multi-workload orchestration
        if self._forwarding_overrides:
            cycle = _dc.replace(
                cycle,
                execution_overrides={
                    **cycle.execution_overrides,
                    **self._forwarding_overrides,
                },
            )
            self._forwarding_overrides = {}

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
                    message=f"Cycle {cycle_id} started ({len(plan)} tasks, distributed)",
                ),
            )

        # Prefect: create flow run
        if self._workflow_tracker:
            try:
                flow_id = await self._workflow_tracker.ensure_flow()
                flow_run_id = await self._workflow_tracker.create_flow_run(
                    flow_id,
                    run_name=f"{cycle.project_id}/{cycle_id[:12]}/{run_id[:12]}",
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

    async def _finalize_run(
        self,
        cycle_id: str,
        run_id: str,
        terminal_status: str,
        obs_ctx: Any,
        flow_run_id: str | None,
        cycle: Cycle | None = None,
        plan: list[TaskEnvelope] | None = None,
    ) -> None:
        """Close observability traces and generate run report."""
        # LangFuse: close cycle trace
        if self._llm_observability and obs_ctx:
            from squadops.telemetry.models import StructuredEvent

            self._llm_observability.record_event(
                obs_ctx,
                StructuredEvent(
                    name="cycle.completed",
                    message=f"Cycle {cycle_id} reached {terminal_status}",
                ),
            )
            self._llm_observability.end_cycle_trace(obs_ctx)
            self._llm_observability.flush()

        # Prefect: set terminal state
        if self._workflow_tracker and flow_run_id:
            try:
                await self._workflow_tracker.set_flow_run_state(
                    flow_run_id, terminal_status, terminal_status.title()
                )
            except Exception:
                logger.warning("Prefect terminal state update failed", exc_info=True)

        # Run report: best-effort (D10)
        try:
            if cycle_id and run_id:
                await self._generate_run_report(
                    cycle_id,
                    run_id,
                    terminal_status,
                    cycle=cycle,
                    plan=plan,
                )
        except Exception:
            logger.warning("Run report generation failed", exc_info=True)

    # ------------------------------------------------------------------
    # Extracted helpers for _generate_run_report
    # ------------------------------------------------------------------

    @staticmethod
    def _build_report_metadata_lines(
        cycle_id: str,
        run_id: str,
        run: Any,
        terminal_status: str,
        cycle: Any,
    ) -> list[str]:
        """Build the metadata section lines for the run report."""
        lines = [
            "# Run Report",
            "",
            "## Metadata",
            f"- **Cycle ID:** {cycle_id}",
            f"- **Run ID:** {run_id}",
            f"- **Run Number:** {run.run_number}",
            f"- **Status:** {terminal_status}",
        ]
        if cycle:
            lines.append(f"- **Project ID:** {cycle.project_id}")
            lines.append(f"- **Build Strategy:** {cycle.build_strategy}")
            lines.append(f"- **Squad Profile:** {cycle.squad_profile_id}")
        if run.started_at:
            lines.append(f"- **Started:** {run.started_at.isoformat()}")
        if run.finished_at:
            lines.append(f"- **Finished:** {run.finished_at.isoformat()}")
        return lines

    @staticmethod
    def _build_report_quality_lines(terminal_status: str) -> list[str]:
        """Build the quality notes section for the run report."""
        lines = ["", "## Quality Notes"]
        if terminal_status == "COMPLETED":
            lines.append("All tasks completed successfully.")
        elif terminal_status == "FAILED":
            lines.append("One or more tasks failed. Check task artifacts for details.")
        elif terminal_status == "CANCELLED":
            lines.append("Run was cancelled before completion.")
        else:
            lines.append(f"Terminal status: {terminal_status}")
        lines.append("")
        return lines

    def _build_pulse_report_lines(self) -> list[str]:
        """Build the pulse verification section for the run report."""
        lines: list[str] = []
        lines.append("")
        lines.append("## Pulse Verification")
        pass_count = sum(1 for e in self._pulse_report_entries if e["decision"] == "pass")
        fail_count = sum(1 for e in self._pulse_report_entries if e["decision"] == "fail")
        exhausted_count = sum(1 for e in self._pulse_report_entries if e["decision"] == "exhausted")
        total = len(self._pulse_report_entries)
        lines.append(
            f"Total boundary checks: {total} "
            f"(PASS: {pass_count}, FAIL: {fail_count}, EXHAUSTED: {exhausted_count})"
        )
        repair_entries = [e for e in self._pulse_report_entries if e["repair_attempt"] > 0]
        if repair_entries:
            max_attempt = max(e["repair_attempt"] for e in repair_entries)
            lines.append(f"Repair attempts: {len(repair_entries)} (max attempt: {max_attempt})")
        lines.append("")
        for entry in self._pulse_report_entries:
            suites_str = ", ".join(f"{s['suite_id']}={s['outcome']}" for s in entry["suites"])
            repair_tag = f" (repair #{entry['repair_attempt']})" if entry["repair_attempt"] else ""
            lines.append(
                f"- **{entry['boundary_id']}** [{entry['decision'].upper()}]{repair_tag}: "
                f"{suites_str}"
            )
        return lines

    # ------------------------------------------------------------------
    # Extracted helpers for _run_correction_protocol
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_agent_id(role: str, profile: Any) -> str:
        """Resolve a role to an agent_id using the squad profile, or fall back to role."""
        if profile:
            for agent in profile.agents:
                if agent.role == role and agent.enabled:
                    return agent.agent_id
        return role

    async def _checkpoint_correction_task(
        self,
        task_id: str,
        run_id: str,
        cycle: Cycle,
        completed_task_ids: list[str],
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        plan_delta_refs: list[str],
    ) -> None:
        """Checkpoint a correction or repair task after successful dispatch."""
        completed_task_ids.append(task_id)
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
                "completed_task_id": task_id,
            },
        )

    # ------------------------------------------------------------------
    # Correction protocol
    # ------------------------------------------------------------------

    async def _run_correction_protocol(
        self,
        run_id: str,
        cycle: Cycle,
        envelope: TaskEnvelope,
        result: TaskResult,
        correction_attempts: int,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
        profile: Any = None,
        flow_run_id: str | None = None,
    ) -> str:
        """Run the correction protocol: analyze → decide → act.

        Returns the correction_path chosen by the governance handler.
        Side effects: dispatches correction/repair tasks, stores plan delta,
        emits correction events.
        """
        from uuid import uuid4

        from squadops.cycles.task_plan import CORRECTION_TASK_STEPS, REPAIR_TASK_STEPS

        # 1. Emit CORRECTION_INITIATED
        self._cycle_event_bus.emit(
            EventType.CORRECTION_INITIATED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={
                "failed_task_id": envelope.task_id,
                "failed_task_type": envelope.task_type,
                "correction_attempt": correction_attempts + 1,
            },
        )

        # 2. Build correction task envelopes (deterministic IDs)
        failure_evidence = {
            "failed_task_id": envelope.task_id,
            "failed_task_type": envelope.task_type,
            "error": result.error or "",
            "outcome_class": (result.outputs or {}).get("outcome_class", ""),
        }

        correction_outputs: dict[str, Any] = {}
        corr_correlation_id = uuid4().hex

        for step_idx, (task_type, role) in enumerate(CORRECTION_TASK_STEPS):
            corr_task_id = f"corr-{run_id[:12]}-{correction_attempts:02d}-{task_type}"
            agent_id = self._resolve_agent_id(role, profile)

            corr_inputs: dict[str, Any] = {
                "prd": cycle.prd_ref,
                "failure_evidence": failure_evidence,
                "prior_outputs": prior_outputs,
                "artifact_refs": list(all_artifact_refs),
            }
            if correction_outputs:
                corr_inputs["failure_analysis"] = correction_outputs

            corr_envelope = TaskEnvelope(
                task_id=corr_task_id,
                agent_id=agent_id,
                cycle_id=cycle.cycle_id,
                pulse_id=uuid4().hex,
                project_id=cycle.project_id,
                task_type=task_type,
                correlation_id=corr_correlation_id,
                causation_id=envelope.task_id,
                trace_id=uuid4().hex,
                span_id=uuid4().hex,
                inputs=corr_inputs,
                metadata={"role": role, "step_index": step_idx},
            )

            # 3. Dispatch correction task. SIP-0087 B2: create task_run before
            # dispatch so the agent's PrefectLogHandler can scope correction-
            # task logs to a dedicated UI pane and the bridge can transition
            # terminal state without owning the ID.
            corr_task_run_id = await self._create_task_run_if_enabled(flow_run_id, corr_envelope)
            corr_task_context = {
                "cycle_id": cycle.cycle_id,
                "run_id": run_id,
                "flow_run_id": flow_run_id or "",
                "task_run_id": corr_task_run_id or "",
            }
            self._cycle_event_bus.emit(
                EventType.TASK_DISPATCHED,
                entity_type="task",
                entity_id=corr_task_id,
                context=corr_task_context,
                payload={"task_type": task_type},
            )

            corr_result = await self._dispatch_task(
                corr_envelope,
                run_id,
                flow_run_id=flow_run_id,
                task_run_id=corr_task_run_id,
            )

            if corr_result.status == "SUCCEEDED":
                self._cycle_event_bus.emit(
                    EventType.TASK_SUCCEEDED,
                    entity_type="task",
                    entity_id=corr_task_id,
                    context=corr_task_context,
                    payload={"task_type": task_type},
                )
                await self._checkpoint_correction_task(
                    corr_task_id,
                    run_id,
                    cycle,
                    completed_task_ids,
                    prior_outputs,
                    all_artifact_refs,
                    plan_delta_refs,
                )
            else:
                self._cycle_event_bus.emit(
                    EventType.TASK_FAILED,
                    entity_type="task",
                    entity_id=corr_task_id,
                    context=corr_task_context,
                    payload={"task_type": task_type, "error": corr_result.error or ""},
                )

            # Collect correction task outputs
            correction_outputs = {
                k: v for k, v in (corr_result.outputs or {}).items() if k != "artifacts"
            }

        # 4. Read correction_path
        correction_path = correction_outputs.get("correction_path", "abort")

        # 5. Emit CORRECTION_DECIDED
        self._cycle_event_bus.emit(
            EventType.CORRECTION_DECIDED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={
                "correction_path": correction_path,
                "decision_rationale": correction_outputs.get("decision_rationale", ""),
            },
        )

        # 6. Store plan delta as artifact
        delta = PlanDelta(
            delta_id=uuid4().hex,
            run_id=run_id,
            correction_path=correction_path,
            trigger=f"task_failure:{envelope.task_type}",
            failure_classification=correction_outputs.get("classification", "unknown"),
            analysis_summary=correction_outputs.get("analysis_summary", "N/A"),
            decision_rationale=correction_outputs.get("decision_rationale", "N/A"),
            changes=tuple(correction_outputs.get("affected_task_types", [])),
            affected_task_types=tuple(correction_outputs.get("affected_task_types", [])),
            created_at=datetime.now(UTC),
        )
        delta_content = json.dumps(delta.to_dict(), default=str).encode()
        delta_ref = ArtifactRef(
            artifact_id=f"delta_{delta.delta_id[:12]}",
            project_id=cycle.project_id,
            artifact_type="plan_delta",
            filename=f"plan_delta_{correction_attempts}.json",
            content_hash=sha256(delta_content).hexdigest(),
            size_bytes=len(delta_content),
            media_type="application/json",
            created_at=datetime.now(UTC),
            cycle_id=cycle.cycle_id,
            run_id=run_id,
        )
        await self._artifact_vault.store(delta_ref, delta_content)
        all_artifact_refs.append(delta_ref.artifact_id)
        plan_delta_refs.append(delta_ref.artifact_id)

        # 7. Handle patch path: dispatch repair tasks
        if correction_path == "patch":
            for step_idx, (task_type, role) in enumerate(REPAIR_TASK_STEPS):
                repair_task_id = f"repair-{run_id[:12]}-{correction_attempts:02d}-{task_type}"
                agent_id = self._resolve_agent_id(role, profile)

                repair_inputs: dict[str, Any] = {
                    "prd": cycle.prd_ref,
                    "failure_evidence": failure_evidence,
                    "correction_decision": correction_outputs,
                    "prior_outputs": prior_outputs,
                    "artifact_refs": list(all_artifact_refs),
                }

                repair_envelope = TaskEnvelope(
                    task_id=repair_task_id,
                    agent_id=agent_id,
                    cycle_id=cycle.cycle_id,
                    pulse_id=uuid4().hex,
                    project_id=cycle.project_id,
                    task_type=task_type,
                    correlation_id=corr_correlation_id,
                    causation_id=envelope.task_id,
                    trace_id=uuid4().hex,
                    span_id=uuid4().hex,
                    inputs=repair_inputs,
                    metadata={"role": role, "step_index": step_idx},
                )

                # SIP-0087 B2: create repair task_run + propagate IDs through
                # dispatch and terminal events so correction-driven repairs
                # appear in the Prefect UI.
                repair_task_run_id = await self._create_task_run_if_enabled(
                    flow_run_id, repair_envelope
                )
                repair_task_context = {
                    "cycle_id": cycle.cycle_id,
                    "run_id": run_id,
                    "flow_run_id": flow_run_id or "",
                    "task_run_id": repair_task_run_id or "",
                }
                self._cycle_event_bus.emit(
                    EventType.TASK_DISPATCHED,
                    entity_type="task",
                    entity_id=repair_task_id,
                    context=repair_task_context,
                    payload={"task_type": task_type},
                )

                repair_result = await self._dispatch_task(
                    repair_envelope,
                    run_id,
                    flow_run_id=flow_run_id,
                    task_run_id=repair_task_run_id,
                )

                if repair_result.status == "SUCCEEDED":
                    self._cycle_event_bus.emit(
                        EventType.TASK_SUCCEEDED,
                        entity_type="task",
                        entity_id=repair_task_id,
                        context=repair_task_context,
                        payload={"task_type": task_type},
                    )
                    await self._checkpoint_correction_task(
                        repair_task_id,
                        run_id,
                        cycle,
                        completed_task_ids,
                        prior_outputs,
                        all_artifact_refs,
                        plan_delta_refs,
                    )
                else:
                    self._cycle_event_bus.emit(
                        EventType.TASK_FAILED,
                        entity_type="task",
                        entity_id=repair_task_id,
                        context=repair_task_context,
                        payload={"task_type": task_type, "error": repair_result.error or ""},
                    )

                # Collect repair outputs
                role_key = repair_envelope.metadata.get("role", "unknown")
                prior_outputs[role_key] = {
                    k: v for k, v in (repair_result.outputs or {}).items() if k != "artifacts"
                }

        # 8. Emit CORRECTION_COMPLETED
        self._cycle_event_bus.emit(
            EventType.CORRECTION_COMPLETED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={"correction_path": correction_path},
        )

        return correction_path

    async def _execute_fan_out(
        self,
        plan: list[TaskEnvelope],
        run_id: str,
        cycle: Cycle,
        flow_run_id: str | None = None,
    ) -> None:
        """Fan-out/fan-in: dispatch all tasks concurrently, await all."""
        import dataclasses

        if await self._is_cancelled(run_id):
            raise _CancellationError(run_id)

        tasks = []
        task_run_ids: list[str | None] = []
        for envelope in plan:
            # SIP-0087: create Prefect task_run here so task_run_id is in the
            # TASK_DISPATCHED context and visible to the contextvar scope.
            task_run_id = await self._create_task_run_if_enabled(flow_run_id, envelope)
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
                    "task_name": f"{envelope.metadata.get('role', 'unknown')}: {envelope.task_type}",
                },
            )
            enriched = dataclasses.replace(
                envelope,
                inputs={**envelope.inputs, "prior_outputs": {}, "artifact_refs": []},
            )
            tasks.append(
                self._dispatch_task(
                    enriched,
                    run_id,
                    flow_run_id=flow_run_id,
                    task_run_id=task_run_id,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

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

    async def _handle_gate(self, run_id: str, cycle: Cycle, task_type: str) -> None:
        """Pause, poll for decision, resume or reject."""
        gate_names = [
            g.name for g in cycle.task_flow_policy.gates if task_type in g.after_task_types
        ]
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

    # ------------------------------------------------------------------
    # Pulse verification (SIP-0070)
    # ------------------------------------------------------------------

    def _emit_pulse_event(
        self,
        obs_ctx: Any,
        event_name: str,
        message: str,
        *,
        suite_id: str = "",
        boundary_id: str = "",
        cadence_interval_id: int = 0,
        extra_attrs: tuple[tuple[str, Any], ...] = (),
    ) -> None:
        """Emit a pulse_check.* telemetry event via LLM observability port."""
        if not self._llm_observability or not obs_ctx:
            return
        from squadops.telemetry.models import StructuredEvent

        attrs: list[tuple[str, Any]] = [
            ("suite_id", suite_id),
            ("boundary_id", boundary_id),
            ("cadence_interval_id", cadence_interval_id),
        ]
        attrs.extend(extra_attrs)

        self._llm_observability.record_event(
            obs_ctx,
            StructuredEvent(name=event_name, message=message, attributes=tuple(attrs)),
        )

    async def _run_boundary_verification(
        self,
        suites: list[PulseCheckDefinition],
        boundary_id: str,
        cadence_interval_id: int,
        run_id: str,
        cycle: Cycle,
        obs_ctx: Any,
        engine: AcceptanceCheckEngine,
        context: AcceptanceContext,
        repair_attempt_number: int = 0,
    ) -> tuple[PulseDecision, list[PulseVerificationRecord]]:
        """Run all suites at a boundary, persist records, return decision + records.

        Returns ``(decision, records)`` so callers can filter failed suites
        for targeted repair reruns.
        """
        # Emit suite_started per suite
        for suite in suites:
            self._emit_pulse_event(
                obs_ctx,
                "pulse_check.suite_started",
                f"Suite {suite.suite_id!r} starting at boundary {boundary_id!r}",
                suite_id=suite.suite_id,
                boundary_id=boundary_id,
                cadence_interval_id=cadence_interval_id,
            )

        # SIP-0077: pulse.boundary_reached
        self._cycle_event_bus.emit(
            EventType.PULSE_BOUNDARY_REACHED,
            entity_type="pulse",
            entity_id=boundary_id,
            context={
                "cycle_id": cycle.cycle_id,
                "run_id": run_id,
                "project_id": cycle.project_id,
            },
            payload={
                "boundary_id": boundary_id,
                "cadence_interval_id": cadence_interval_id,
                "suite_count": len(suites),
                "suite_ids": [s.suite_id for s in suites],
                "repair_attempt_number": repair_attempt_number,
            },
        )

        records = await run_pulse_verification(
            suites=suites,
            context=context,
            engine=engine,
            boundary_id=boundary_id,
            cadence_interval_id=cadence_interval_id,
            run_id=run_id,
            repair_attempt_number=repair_attempt_number,
        )

        # Persist and emit per-suite events
        for record in records:
            await self._cycle_registry.record_pulse_verification(run_id, record)

            if record.suite_outcome.value == "pass":
                self._emit_pulse_event(
                    obs_ctx,
                    "pulse_check.suite_passed",
                    f"Suite {record.suite_id!r} PASSED at {boundary_id!r}",
                    suite_id=record.suite_id,
                    boundary_id=boundary_id,
                    cadence_interval_id=cadence_interval_id,
                )
            else:
                self._emit_pulse_event(
                    obs_ctx,
                    "pulse_check.suite_failed",
                    f"Suite {record.suite_id!r} FAILED at {boundary_id!r}",
                    suite_id=record.suite_id,
                    boundary_id=boundary_id,
                    cadence_interval_id=cadence_interval_id,
                )

            # SIP-0077: pulse.suite_evaluated
            self._cycle_event_bus.emit(
                EventType.PULSE_SUITE_EVALUATED,
                entity_type="pulse",
                entity_id=record.suite_id,
                context={
                    "cycle_id": cycle.cycle_id,
                    "run_id": run_id,
                    "project_id": cycle.project_id,
                },
                payload={
                    "suite_id": record.suite_id,
                    "boundary_id": boundary_id,
                    "cadence_interval_id": cadence_interval_id,
                    "outcome": record.suite_outcome.value,
                    "repair_attempt_number": repair_attempt_number,
                },
            )

        decision = determine_boundary_decision(records)

        # Accumulate for run report
        self._pulse_report_entries.append(
            {
                "boundary_id": boundary_id,
                "cadence_interval_id": cadence_interval_id,
                "decision": decision.value,
                "repair_attempt": repair_attempt_number,
                "suites": [
                    {"suite_id": r.suite_id, "outcome": r.suite_outcome.value} for r in records
                ],
            }
        )

        # Emit boundary-level decision
        self._emit_pulse_event(
            obs_ctx,
            "pulse_check.boundary_decision",
            f"Boundary {boundary_id!r} decision: {decision.value}",
            boundary_id=boundary_id,
            cadence_interval_id=cadence_interval_id,
            extra_attrs=(("decision", decision.value),),
        )

        # SIP-0077: pulse.boundary_decided
        self._cycle_event_bus.emit(
            EventType.PULSE_BOUNDARY_DECIDED,
            entity_type="pulse",
            entity_id=boundary_id,
            context={
                "cycle_id": cycle.cycle_id,
                "run_id": run_id,
                "project_id": cycle.project_id,
            },
            payload={
                "boundary_id": boundary_id,
                "cadence_interval_id": cadence_interval_id,
                "decision": decision.value,
                "suite_count": len(records),
                "repair_attempt_number": repair_attempt_number,
            },
        )

        return decision, records

    async def _verify_with_repair(
        self,
        suites: list[PulseCheckDefinition],
        boundary_id: str,
        cadence_interval_id: int,
        run_id: str,
        cycle: Cycle,
        obs_ctx: Any,
        engine: AcceptanceCheckEngine,
        context: AcceptanceContext,
        envelope: TaskEnvelope,
        prior_outputs: dict[str, Any],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        all_artifact_refs: list[str],
        max_repair_attempts: int = 2,
        flow_run_id: str | None = None,
        agent_resolver: dict[str, str] | None = None,
    ) -> None:
        """Verify boundary, repair on failure, exhaust on repeated failure.

        Phase 3: FAIL triggers bounded repair loop (4-agent chain, max
        ``max_repair_attempts``). Only previously-failed suites are rerun.
        EXHAUSTED → run FAILED with VERIFICATION_EXHAUSTED reason.
        """
        import dataclasses

        decision, records = await self._run_boundary_verification(
            suites=suites,
            boundary_id=boundary_id,
            cadence_interval_id=cadence_interval_id,
            run_id=run_id,
            cycle=cycle,
            obs_ctx=obs_ctx,
            engine=engine,
            context=context,
        )

        if decision == PulseDecision.PASS:
            return

        # Collect initially-failed suites from records
        failed_suites = [
            s for s, r in zip(suites, records, strict=True) if r.suite_outcome == SuiteOutcome.FAIL
        ]
        repair_attempt = 0

        while failed_suites:
            if repair_attempt >= max_repair_attempts:
                # EXHAUSTED — emit event and fail the run
                self._emit_pulse_event(
                    obs_ctx,
                    "pulse_check.boundary_decision",
                    f"Boundary {boundary_id!r} EXHAUSTED after "
                    f"{max_repair_attempts} repair attempts",
                    boundary_id=boundary_id,
                    cadence_interval_id=cadence_interval_id,
                    extra_attrs=(
                        ("decision", PulseDecision.EXHAUSTED.value),
                        ("repair_attempts", max_repair_attempts),
                    ),
                )

                # SIP-0077: pulse.repair_exhausted
                failed_ids = [s.suite_id for s in failed_suites]
                self._cycle_event_bus.emit(
                    EventType.PULSE_REPAIR_EXHAUSTED,
                    entity_type="pulse",
                    entity_id=boundary_id,
                    context={
                        "cycle_id": cycle.cycle_id,
                        "run_id": run_id,
                        "project_id": cycle.project_id,
                    },
                    payload={
                        "boundary_id": boundary_id,
                        "cadence_interval_id": cadence_interval_id,
                        "max_repair_attempts": max_repair_attempts,
                        "failed_suite_ids": failed_ids,
                    },
                )

                raise _ExecutionError(
                    f"VERIFICATION_EXHAUSTED at boundary {boundary_id!r}: "
                    f"suites {failed_ids} still failing after "
                    f"{max_repair_attempts} repair attempts"
                )

            repair_attempt += 1

            # Emit repair_started event
            failed_suite_ids = [s.suite_id for s in failed_suites]
            self._emit_pulse_event(
                obs_ctx,
                "pulse_check.repair_started",
                f"Repair attempt {repair_attempt} for boundary {boundary_id!r}: {failed_suite_ids}",
                boundary_id=boundary_id,
                cadence_interval_id=cadence_interval_id,
                extra_attrs=(
                    ("repair_attempt", repair_attempt),
                    ("failed_suite_ids", failed_suite_ids),
                ),
            )

            # SIP-0077: pulse.repair_started
            self._cycle_event_bus.emit(
                EventType.PULSE_REPAIR_STARTED,
                entity_type="pulse",
                entity_id=boundary_id,
                context={
                    "cycle_id": cycle.cycle_id,
                    "run_id": run_id,
                    "project_id": cycle.project_id,
                },
                payload={
                    "boundary_id": boundary_id,
                    "cadence_interval_id": cadence_interval_id,
                    "repair_attempt": repair_attempt,
                    "max_repair_attempts": max_repair_attempts,
                    "failed_suite_ids": failed_suite_ids,
                },
            )

            # Build verification failure context for repair handlers
            verification_context = (
                f"Boundary: {boundary_id}\n"
                f"Failed suites: {failed_suite_ids}\n"
                f"Repair attempt: {repair_attempt} of {max_repair_attempts}\n"
            )

            # Build and dispatch repair chain (4 steps per D17)
            repair_envelopes = build_repair_task_envelopes(
                cycle_id=cycle.cycle_id,
                project_id=cycle.project_id,
                pulse_id=envelope.pulse_id,
                correlation_id=envelope.correlation_id,
                trace_id=envelope.trace_id,
                causation_id=envelope.task_id,
                run_id=run_id,
                repair_attempt=repair_attempt,
                boundary_id=boundary_id,
                cadence_interval_id=cadence_interval_id,
                failed_suite_ids=tuple(failed_suite_ids),
                agent_resolver=agent_resolver,
            )

            # Inject verification context + PRD into repair envelopes
            repair_prior = {
                **prior_outputs,
                "verification_context": verification_context,
            }
            for repair_env in repair_envelopes:
                enriched_repair = dataclasses.replace(
                    repair_env,
                    inputs={
                        "prd": cycle.prd_ref,
                        "prior_outputs": repair_prior,
                    },
                )

                # SIP-0087 B2: create the Prefect task_run before dispatch so
                # SIP-0086 pulse-repair handlers also stream logs to a per-task
                # UI pane and the bridge can transition terminal state.
                pulse_repair_task_run_id = await self._create_task_run_if_enabled(
                    flow_run_id, enriched_repair
                )
                role = repair_env.metadata.get("role", "unknown")
                pulse_repair_context = {
                    "cycle_id": cycle.cycle_id,
                    "run_id": run_id,
                    "flow_run_id": flow_run_id or "",
                    "task_run_id": pulse_repair_task_run_id or "",
                }
                self._cycle_event_bus.emit(
                    EventType.TASK_DISPATCHED,
                    entity_type="task",
                    entity_id=repair_env.task_id,
                    context=pulse_repair_context,
                    payload={
                        "task_type": repair_env.task_type,
                        "task_name": f"{role}: {repair_env.task_type} (repair #{repair_attempt})",
                    },
                )

                result = await self._dispatch_task(
                    enriched_repair,
                    run_id,
                    flow_run_id=flow_run_id,
                    task_run_id=pulse_repair_task_run_id,
                )

                # SIP-0077: task.succeeded or task.failed
                if result.status == "SUCCEEDED":
                    self._cycle_event_bus.emit(
                        EventType.TASK_SUCCEEDED,
                        entity_type="task",
                        entity_id=repair_env.task_id,
                        context=pulse_repair_context,
                        payload={"task_type": repair_env.task_type},
                    )
                else:
                    self._cycle_event_bus.emit(
                        EventType.TASK_FAILED,
                        entity_type="task",
                        entity_id=repair_env.task_id,
                        context=pulse_repair_context,
                        payload={
                            "task_type": repair_env.task_type,
                            "error": result.error or "",
                        },
                    )

                # Collect repair artifacts
                for art in (result.outputs or {}).get("artifacts", []):
                    ref = await self._store_artifact(
                        art,
                        cycle,
                        run_id,
                        enriched_repair,
                        producing_task_type=repair_env.task_type,
                    )
                    all_artifact_refs.append(ref.artifact_id)
                    stored_artifacts.append((ref.artifact_id, ref))

                # Chain repair outputs
                role = repair_env.metadata.get("role", "unknown")
                repair_prior[role] = {
                    k: v for k, v in (result.outputs or {}).items() if k != "artifacts"
                }

            # Rerun ONLY previously-failed suites
            decision, rerun_records = await self._run_boundary_verification(
                suites=failed_suites,
                boundary_id=boundary_id,
                cadence_interval_id=cadence_interval_id,
                run_id=run_id,
                cycle=cycle,
                obs_ctx=obs_ctx,
                engine=engine,
                context=context,
                repair_attempt_number=repair_attempt,
            )

            if decision == PulseDecision.PASS:
                return

            # Update failed_suites for next attempt — only keep still-failing
            failed_suites = [
                s
                for s, r in zip(failed_suites, rerun_records, strict=True)
                if r.suite_outcome == SuiteOutcome.FAIL
            ]

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

    async def _generate_run_report(
        self,
        cycle_id: str,
        run_id: str,
        terminal_status: str,
        cycle: Cycle | None = None,
        plan: list[TaskEnvelope] | None = None,
    ) -> None:
        """Generate run_report.md and store as a documentation artifact (D10).

        Best-effort: called in finally block, failures are logged but
        never affect the run's terminal status.
        """
        # Fetch latest run state for gate decisions and artifact refs
        run = await self._cycle_registry.get_run(run_id)

        lines = self._build_report_metadata_lines(cycle_id, run_id, run, terminal_status, cycle)

        # Task breakdown
        if plan:
            lines.append("")
            lines.append("## Task Plan")
            lines.append(f"Total tasks: {len(plan)}")
            lines.append("")
            for i, envelope in enumerate(plan):
                role = envelope.metadata.get("role", "unknown")
                lines.append(
                    f"{i + 1}. **{envelope.task_type}** (agent: {envelope.agent_id}, role: {role})"
                )

        # Gate decisions
        if run.gate_decisions:
            lines.append("")
            lines.append("## Gate Decisions")
            for gd in run.gate_decisions:
                lines.append(
                    f"- **{gd.gate_name}:** {gd.decision}" + (f" — {gd.notes}" if gd.notes else "")
                )

        # Artifact inventory
        if run.artifact_refs:
            lines.append("")
            lines.append("## Artifacts")
            lines.append(f"Total artifacts: {len(run.artifact_refs)}")

        # Pulse verification summary
        if self._pulse_report_entries:
            lines.extend(self._build_pulse_report_lines())

        # Quality notes
        lines.extend(self._build_report_quality_lines(terminal_status))

        content = "\n".join(lines)
        content_bytes = content.encode("utf-8")

        # Note: uses direct vault.store() instead of _store_artifact() because
        # the report is generated outside of any task context (no TaskEnvelope).
        ref = ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=cycle.project_id if cycle else "unknown",
            artifact_type="document",
            filename="run_report.md",
            content_hash=sha256(content_bytes).hexdigest(),
            size_bytes=len(content_bytes),
            media_type="text/markdown",
            created_at=datetime.now(UTC),
            cycle_id=cycle_id,
            run_id=run_id,
            metadata={"report_type": "run_report"},
        )

        await self._artifact_vault.store(ref, content_bytes)
        await self._cycle_registry.append_artifact_refs(run_id, (ref.artifact_id,))
        logger.info("Run report generated for %s", run_id)
