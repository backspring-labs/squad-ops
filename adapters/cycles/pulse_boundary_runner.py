"""Pulse-boundary collaborator (SIP-0097 §6.2).

Owns boundary verification and the bounded repair loop (SIP-0070 pulse
checks + SIP-0086 repair chain), moved verbatim from
``DispatchedFlowExecutor``: ``setup_pulse_context`` /
``evaluate_pulse_boundaries`` / ``run_pulse_evaluations`` (the executor's
three call sites) and the internal ``_verify_with_repair`` /
``_run_boundary_verification`` / ``_emit_pulse_event``.

Verification summaries are appended to the ``RunLedger`` passed in by the
executor (§6.6); verification exhaustion surfaces as the same
``_ExecutionError`` the run loop already converts to FAILED.

Per the SIP-0097 observability ownership rule this collaborator only
*emits* events through the LLM observability port — it never opens or
closes observability scopes.

Task transport goes through the injected ``TaskDispatcher`` (§6.2 final
state — slice 5 retired the interim executor-supplied dispatch callables
per AC#9). ``store_artifact`` remains a narrow executor-supplied callable:
artifact plumbing is §6.7 executor residual, residual-but-watched.

Cancellation: the pulse path performs no cancellation checks of its own (it
never did); it relies on the dispatch path's checks at dispatch/await
boundaries per the §6 cancellation ownership rule.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from adapters.cycles.execution_errors import _ExecutionError
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
from squadops.events.types import EventType

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from adapters.cycles.task_dispatcher import TaskDispatcher
    from squadops.capabilities.acceptance import AcceptanceCheckEngine
    from squadops.capabilities.models import AcceptanceContext
    from squadops.cycles.models import ArtifactRef, Cycle
    from squadops.cycles.pulse_models import PulseCheckDefinition, PulseVerificationRecord
    from squadops.cycles.run_ledger import RunLedger
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort
    from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)


class PulseBoundaryRunner:
    """Runs pulse-check verification at task boundaries (SIP-0070/0086).

    Plain injected collaborator (not a port); the executor composes a
    default from its own deps. Independently unit-testable without a
    ``DispatchedFlowExecutor`` instance.
    """

    def __init__(
        self,
        cycle_registry: CycleRegistryPort,
        event_bus: CycleEventBusPort,
        llm_observability: LLMObservabilityPort | None = None,
        *,
        task_dispatcher: TaskDispatcher,
        store_artifact: Callable[..., Awaitable[ArtifactRef]],
    ) -> None:
        self._cycle_registry = cycle_registry
        self._event_bus = event_bus
        self._llm_observability = llm_observability
        self._task_dispatcher = task_dispatcher
        self._store_artifact = store_artifact

    def setup_pulse_context(
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

    def evaluate_pulse_boundaries(
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

    async def run_pulse_evaluations(
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
        *,
        ledger: RunLedger,
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
                    ledger=ledger,
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
                ledger=ledger,
            )

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
        *,
        ledger: RunLedger,
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
        self._event_bus.emit(
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
            self._event_bus.emit(
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

        # Accumulate for run report (SIP-0097 §6.6: on the RunLedger)
        ledger.record_pulse_boundary(
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
        self._event_bus.emit(
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
        *,
        ledger: RunLedger,
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
            ledger=ledger,
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
                self._event_bus.emit(
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
            self._event_bus.emit(
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
                pulse_repair_task_run_id = await self._task_dispatcher.create_task_run_if_enabled(
                    flow_run_id, enriched_repair
                )
                role = repair_env.metadata.get("role", "unknown")
                pulse_repair_context = {
                    "cycle_id": cycle.cycle_id,
                    "run_id": run_id,
                    "flow_run_id": flow_run_id or "",
                    "task_run_id": pulse_repair_task_run_id or "",
                }
                self._event_bus.emit(
                    EventType.TASK_DISPATCHED,
                    entity_type="task",
                    entity_id=repair_env.task_id,
                    context=pulse_repair_context,
                    payload={
                        "task_type": repair_env.task_type,
                        "task_name": f"{role}: {repair_env.task_type} (repair #{repair_attempt})",
                    },
                )

                result = await self._task_dispatcher.dispatch_task(
                    enriched_repair,
                    run_id,
                    flow_run_id=flow_run_id,
                    task_run_id=pulse_repair_task_run_id,
                )

                # SIP-0077: task.succeeded or task.failed
                if result.status == "SUCCEEDED":
                    self._event_bus.emit(
                        EventType.TASK_SUCCEEDED,
                        entity_type="task",
                        entity_id=repair_env.task_id,
                        context=pulse_repair_context,
                        payload={"task_type": repair_env.task_type},
                    )
                else:
                    self._event_bus.emit(
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
                ledger=ledger,
            )

            if decision == PulseDecision.PASS:
                return

            # Update failed_suites for next attempt — only keep still-failing
            failed_suites = [
                s
                for s, r in zip(failed_suites, rerun_records, strict=True)
                if r.suite_outcome == SuiteOutcome.FAIL
            ]
