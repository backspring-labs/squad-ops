"""Correction-protocol collaborator (SIP-0097 §6.3).

Owns the four-step correction protocol — analyze → decide → (patch) → done —
moved verbatim from ``DispatchedFlowExecutor._run_correction_protocol`` plus
its two helpers (``_store_correction_task_artifacts``,
``_checkpoint_correction_task``). Outcome *routing* (what the run does with
the returned correction path) stays with the executor's orchestration loop.

Task transport goes through the injected ``TaskDispatcher`` (§6.3 final
state — slice 5 retired the interim executor-supplied dispatch callables
per AC#9). ``store_artifact`` remains a narrow executor-supplied callable:
artifact plumbing is §6.7 executor residual, residual-but-watched.

Cancellation: the protocol performs no cancellation checks of its own (it
never did); it relies on the dispatch path's checks at dispatch/await
boundaries per the §6 cancellation ownership rule.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from squadops.cycles.agent_config import resolve_agent_config
from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.failure_evidence import build_failure_evidence, compose_failure_trigger
from squadops.cycles.models import ArtifactRef
from squadops.cycles.plan_delta import PlanDelta
from squadops.events.types import EventType
from squadops.tasks.models import TaskEnvelope

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from adapters.cycles.task_dispatcher import TaskDispatcher
    from squadops.cycles.models import Cycle
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort
    from squadops.tasks.models import TaskResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorrectionProtocolResult:
    """Outcome of one correction-protocol run.

    ``repair_artifacts`` carries the repair steps' emitted files (handler
    ``artifacts`` dicts, validate step excluded) so the executor can verify
    the patch behaviorally against them (#389) instead of re-dispatching
    the generative task and re-rolling its output.
    """

    correction_path: str
    repair_artifacts: list[dict[str, Any]] = field(default_factory=list)


class CorrectionRunner:
    """Runs the correction protocol for a failed task (SIP-0079 semantics).

    Plain injected collaborator (not a port); the executor composes a
    default from its own deps. Independently unit-testable without a
    ``DispatchedFlowExecutor`` instance.
    """

    def __init__(
        self,
        cycle_registry: CycleRegistryPort,
        artifact_vault: ArtifactVaultPort,
        event_bus: CycleEventBusPort,
        *,
        task_dispatcher: TaskDispatcher,
        store_artifact: Callable[..., Awaitable[ArtifactRef]],
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._event_bus = event_bus
        self._task_dispatcher = task_dispatcher
        self._store_artifact = store_artifact

    async def _store_correction_task_artifacts(
        self,
        result: TaskResult,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
    ) -> None:
        """Persist a correction-task or repair-task's output artifacts.

        Mirrors the artifact-storage loop in the executor's
        ``_collect_artifacts_and_checkpoint`` but is split out so the
        correction/repair success branches can call it before
        ``_checkpoint_correction_task`` — which only snapshots existing
        ``all_artifact_refs`` into a checkpoint and does not itself
        persist new artifacts. Without this call, repaired deliverables
        (e.g. the ``qa_handoff.md`` produced by ``builder.assemble_repair``
        or the ``correction_decision.md`` from the correction protocol)
        never reach the artifact registry, even though the cycle marks
        completed and the run_report counts them as repaired. This was
        observed across cycles 4b, 6, and prior gate-batch runs as the
        recurring "silent artifact-drop" pattern.
        """
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
        self._event_bus.emit(
            EventType.CHECKPOINT_CREATED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={
                "checkpoint_index": checkpoint_index,
                "completed_task_id": task_id,
            },
        )

    async def _dispatch_protocol_step(
        self,
        step_envelope: TaskEnvelope,
        run_id: str,
        cycle: Cycle,
        flow_run_id: str | None,
        *,
        prior_outputs: dict[str, Any],
        all_artifact_refs: list[str],
        stored_artifacts: list[tuple[str, ArtifactRef]],
        completed_task_ids: list[str],
        plan_delta_refs: list[str],
    ) -> TaskResult:
        """Dispatch one correction/repair step and handle its outcome.

        The shared per-step sequence both protocol loops used verbatim:
        create the Prefect task_run (SIP-0087 B2), emit TASK_DISPATCHED,
        dispatch, then on success emit TASK_SUCCEEDED + persist the step's
        output artifacts BEFORE checkpointing (the silent-artifact-drop
        guard), or on failure emit TASK_FAILED. Returns the step's result;
        output collection stays with the caller (the two loops bucket
        outputs differently — issue #95 vs. repair prior_outputs).
        """
        task_run_id = await self._task_dispatcher.create_task_run_if_enabled(
            flow_run_id, step_envelope
        )
        task_context = {
            "cycle_id": cycle.cycle_id,
            "run_id": run_id,
            "flow_run_id": flow_run_id or "",
            "task_run_id": task_run_id or "",
        }
        self._event_bus.emit(
            EventType.TASK_DISPATCHED,
            entity_type="task",
            entity_id=step_envelope.task_id,
            context=task_context,
            payload={"task_type": step_envelope.task_type},
        )

        result = await self._task_dispatcher.dispatch_task(
            step_envelope,
            run_id,
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
        )

        if result.status == "SUCCEEDED":
            self._event_bus.emit(
                EventType.TASK_SUCCEEDED,
                entity_type="task",
                entity_id=step_envelope.task_id,
                context=task_context,
                payload={"task_type": step_envelope.task_type},
            )
            # Persist the step's output artifacts BEFORE checkpointing —
            # _checkpoint_correction_task only snapshots existing refs and
            # would otherwise drop these silently.
            await self._store_correction_task_artifacts(
                result,
                step_envelope,
                cycle,
                run_id,
                all_artifact_refs,
                stored_artifacts,
            )
            await self._checkpoint_correction_task(
                step_envelope.task_id,
                run_id,
                cycle,
                completed_task_ids,
                prior_outputs,
                all_artifact_refs,
                plan_delta_refs,
            )
        else:
            self._event_bus.emit(
                EventType.TASK_FAILED,
                entity_type="task",
                entity_id=step_envelope.task_id,
                context=task_context,
                payload={"task_type": step_envelope.task_type, "error": result.error or ""},
            )
        return result

    async def run_correction_protocol(
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
    ) -> CorrectionProtocolResult:
        """Run the correction protocol: analyze → decide → act.

        Returns the correction_path chosen by the governance handler plus,
        on the patch path, the repair steps' emitted artifacts (#389).
        Side effects: dispatches correction/repair tasks, stores plan delta,
        emits correction events.
        """
        from uuid import uuid4

        from squadops.cycles.task_plan import CORRECTION_TASK_STEPS, repair_steps_for

        # 1. Emit CORRECTION_INITIATED
        self._event_bus.emit(
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
        failure_evidence = build_failure_evidence(
            envelope, result, prior_plan_deltas_count=len(plan_delta_refs)
        )

        # Issue #95: capture each correction step's outputs in its own variable
        # so the analyzer's classification/analysis_summary survive past the
        # subsequent governance.correction_decision step (which doesn't carry
        # those fields forward). Reusing a single variable used to mask the
        # analyzer's diagnosis with defaults at PlanDelta time.
        analysis_outputs: dict[str, Any] = {}
        decision_outputs: dict[str, Any] = {}
        corr_correlation_id = uuid4().hex

        for step_idx, (task_type, role) in enumerate(CORRECTION_TASK_STEPS):
            corr_task_id = f"corr-{run_id[:12]}-{correction_attempts:02d}-{task_type}"
            resolved = resolve_agent_config(role, profile)
            agent_id = resolved.agent_id
            agent_model = resolved.model
            agent_overrides = resolved.config_overrides

            # Issue #110: propagate squad-profile model + overrides so
            # correction-loop reasoning runs on the cycle's specified model
            # (e.g. the `full` profile pins data/lead to qwen3.6:27b)
            # rather than the agent container's instance default.
            corr_inputs: dict[str, Any] = {
                "prd": cycle.prd_ref,
                "failure_evidence": failure_evidence,
                "prior_outputs": prior_outputs,
                "artifact_refs": list(all_artifact_refs),
                "agent_model": agent_model,
                "agent_config_overrides": agent_overrides,
            }
            if analysis_outputs:
                corr_inputs["failure_analysis"] = analysis_outputs

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

            # 3. Dispatch correction task (task_run creation + task events
            # live in _dispatch_protocol_step, SIP-0087 B2).
            corr_result = await self._dispatch_protocol_step(
                corr_envelope,
                run_id,
                cycle,
                flow_run_id,
                prior_outputs=prior_outputs,
                all_artifact_refs=all_artifact_refs,
                stored_artifacts=stored_artifacts,
                completed_task_ids=completed_task_ids,
                plan_delta_refs=plan_delta_refs,
            )

            # Collect correction task outputs into the right named bucket so
            # downstream PlanDelta construction reads each field from the
            # handler that owns it (issue #95).
            step_outputs = {
                k: v for k, v in (corr_result.outputs or {}).items() if k != "artifacts"
            }
            if task_type == "data.analyze_failure":
                analysis_outputs = step_outputs
            elif task_type == "governance.correction_decision":
                decision_outputs = step_outputs

        # 4. Read correction_path — bounded by the deterministic policy guard
        # (#447): `continue` may not discard a required check that executed
        # and failed while this chain's repair slot is unspent. The model's
        # original rationale stays intact in the decision artifact; the
        # override is disclosed in the event payload below.
        from squadops.cycles.correction_policy import resolve_correction_path

        resolution = resolve_correction_path(
            decision_outputs.get("correction_path", "abort"),
            failure_evidence,
            cycle.applied_defaults,
        )
        correction_path = resolution.path
        if resolution.overridden_from:
            logger.warning(
                "correction_policy_override: %s -> patch (executed-failed required checks: %s)",
                resolution.overridden_from,
                ", ".join(resolution.failed_required_checks),
            )

        # 5. Emit CORRECTION_DECIDED
        decided_payload: dict[str, Any] = {
            "correction_path": correction_path,
            "decision_rationale": decision_outputs.get("decision_rationale", ""),
        }
        if resolution.overridden_from:
            decided_payload["policy_override"] = {
                "from": resolution.overridden_from,
                "reason": "executed_failed_required_checks",
                "checks": list(resolution.failed_required_checks),
            }
        self._event_bus.emit(
            EventType.CORRECTION_DECIDED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload=decided_payload,
        )

        # 6. Store plan delta as artifact
        delta = PlanDelta(
            delta_id=uuid4().hex,
            run_id=run_id,
            correction_path=correction_path,
            trigger=compose_failure_trigger(envelope, failure_evidence),
            failure_classification=analysis_outputs.get("classification", "unknown"),
            analysis_summary=analysis_outputs.get("analysis_summary", "N/A"),
            decision_rationale=decision_outputs.get("decision_rationale", "N/A"),
            changes=tuple(decision_outputs.get("affected_task_types", [])),
            affected_task_types=tuple(decision_outputs.get("affected_task_types", [])),
            created_at=datetime.now(UTC),
            # SIP-0092 M2 → M3 gate diagnostic.
            structural_plan_change_candidate=str(
                decision_outputs.get("structural_plan_change_candidate", "none")
            ),
            structural_plan_change_rationale=str(
                decision_outputs.get("structural_plan_change_rationale", "")
            ),
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
        # Repair-step selection is keyed on the failed task's task_type
        # (authoritative) rather than the LLM-emitted `affected_task_types`
        # field, which is free-text and previously caused builder failures
        # (`affected_task_types: ["QA Handoff"]`) to silently route to the
        # dev repair handler.
        repair_artifacts: list[dict[str, Any]] = []
        if correction_path == "patch":
            for step_idx, (task_type, role) in enumerate(repair_steps_for(envelope.task_type)):
                repair_task_id = f"repair-{run_id[:12]}-{correction_attempts:02d}-{task_type}"
                resolved = resolve_agent_config(role, profile)
                agent_id = resolved.agent_id
                agent_model = resolved.model
                agent_overrides = resolved.config_overrides

                # Plumb the failed task's contract through to the repair
                # envelope. Without this the repair handler only sees the
                # PRD + failure evidence and produces a generic "repair_output.md"
                # rather than re-emitting the named artifact (e.g. qa_handoff.md)
                # that originally failed acceptance.
                failed_inputs = envelope.inputs or {}
                repair_inputs: dict[str, Any] = {
                    "prd": cycle.prd_ref,
                    "failed_task_type": envelope.task_type,
                    "failure_evidence": failure_evidence,
                    "failure_analysis": analysis_outputs,
                    "correction_decision": decision_outputs,
                    "prior_outputs": prior_outputs,
                    "artifact_refs": list(all_artifact_refs),
                    "agent_model": agent_model,
                    "agent_config_overrides": agent_overrides,
                    "subtask_focus": failed_inputs.get("subtask_focus"),
                    "subtask_description": failed_inputs.get("subtask_description"),
                    "expected_artifacts": failed_inputs.get("expected_artifacts", []),
                    "acceptance_criteria": failed_inputs.get("acceptance_criteria", []),
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

                # Dispatch the repair step (task_run creation + task events
                # live in _dispatch_protocol_step, SIP-0087 B2 — so
                # correction-driven repairs appear in the Prefect UI).
                repair_result = await self._dispatch_protocol_step(
                    repair_envelope,
                    run_id,
                    cycle,
                    flow_run_id,
                    prior_outputs=prior_outputs,
                    all_artifact_refs=all_artifact_refs,
                    stored_artifacts=stored_artifacts,
                    completed_task_ids=completed_task_ids,
                    plan_delta_refs=plan_delta_refs,
                )

                # Collect repair outputs. Unlike the regular fan-in path
                # (executor fan-in), keep `artifacts` so the next step in this
                # sequence — `qa.validate_repair` — can see the actual
                # repaired files rather than only the role-keyed one-line
                # summary. Without this the qa role renders Verdict: FAIL
                # on repairs whose artifacts are already in the registry,
                # because the validate-repair prompt has no visibility
                # into what the upstream repair handler produced.
                role_key = repair_envelope.metadata.get("role", "unknown")
                prior_outputs[role_key] = dict(repair_result.outputs or {})

                # #389: surface the repair's emitted files to the executor for
                # behavioral patch verification. The validate step's output is
                # an LLM judgment document, not product content — excluded so
                # it can't shadow a product file in the overlay.
                if task_type != "qa.validate_repair":
                    step_artifacts = (repair_result.outputs or {}).get("artifacts") or []
                    repair_artifacts.extend(a for a in step_artifacts if isinstance(a, dict))

        # 8. Emit CORRECTION_COMPLETED
        self._event_bus.emit(
            EventType.CORRECTION_COMPLETED,
            entity_type="run",
            entity_id=run_id,
            context={"cycle_id": cycle.cycle_id, "run_id": run_id},
            payload={"correction_path": correction_path},
        )

        return CorrectionProtocolResult(
            correction_path=correction_path, repair_artifacts=repair_artifacts
        )
