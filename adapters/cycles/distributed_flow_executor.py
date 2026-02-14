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
import json
import logging
import time
from datetime import datetime, timezone
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from squadops.cycles.models import ArtifactRef, Cycle, Run, RunStatus
from squadops.cycles.task_plan import generate_task_plan
from squadops.ports.cycles.flow_execution import FlowExecutionPort
from squadops.tasks.models import TaskEnvelope, TaskResult

if TYPE_CHECKING:
    from adapters.cycles.prefect_reporter import PrefectReporter
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.cycles.squad_profile import SquadProfilePort
    from squadops.ports.telemetry.llm_observability import LLMObservabilityPort

logger = logging.getLogger(__name__)


class _ExecutionError(Exception):
    """Internal: task failure or gate rejection."""


class _CancellationError(Exception):
    """Internal: run was cancelled."""


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
        prefect_reporter: PrefectReporter | None = None,
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._queue = queue
        self._squad_profile = squad_profile
        self._project_registry = project_registry
        self._task_timeout = task_timeout
        self._llm_observability = llm_observability
        self._prefect = prefect_reporter
        self._cancelled: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_run(
        self, cycle_id: str, run_id: str, profile_id: str | None = None
    ) -> None:
        """Execute a run by dispatching tasks to agent containers via RabbitMQ."""
        obs_ctx = None
        flow_run_id = None
        terminal_status = "COMPLETED"

        try:
            cycle = await self._cycle_registry.get_cycle(cycle_id)
            run = await self._cycle_registry.get_run(run_id)
            profile, _ = await self._squad_profile.resolve_snapshot(profile_id)

            # Resolve PRD content
            prd_content = cycle.prd_ref
            if not prd_content:
                prd_content = await self._resolve_prd_from_project(cycle.project_id)
            if prd_content and prd_content != cycle.prd_ref:
                import dataclasses as _dc
                cycle = _dc.replace(cycle, prd_ref=prd_content)

            # queued -> running
            await self._cycle_registry.update_run_status(run_id, RunStatus.RUNNING)

            plan = generate_task_plan(cycle, run, profile)

            # Build-only validation (D6): require plan_artifact_refs
            include_plan = bool(cycle.applied_defaults.get("plan_tasks", True))
            include_build = bool(cycle.applied_defaults.get("build_tasks"))
            seed_artifact_refs: list[str] = []
            if include_build and not include_plan:
                plan_refs = cycle.execution_overrides.get("plan_artifact_refs")
                if not plan_refs:
                    raise _ExecutionError(
                        "plan_artifact_refs required for build-only cycle"
                    )
                # Seed working set so pre-resolution can find plan artifacts
                seed_artifact_refs = list(plan_refs)

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
            if self._prefect:
                try:
                    flow_id = await self._prefect.ensure_flow()
                    flow_run_id = await self._prefect.create_flow_run(
                        flow_id,
                        run_name=f"{cycle.project_id}/{cycle_id[:12]}/{run_id[:12]}",
                        parameters={"cycle_id": cycle_id, "run_id": run_id, "project_id": cycle.project_id},
                    )
                    await self._prefect.set_flow_run_state(
                        flow_run_id, "RUNNING", "Running"
                    )
                except Exception:
                    logger.warning("Prefect flow run creation failed", exc_info=True)

            logger.info(
                "Executing run %s for cycle %s (%d tasks, mode=%s, dispatch=distributed)",
                run_id, cycle_id, len(plan), cycle.task_flow_policy.mode,
            )

            # Dispatch based on policy mode
            mode = cycle.task_flow_policy.mode
            if mode == "sequential":
                await self._execute_sequential(
                    plan, run_id, cycle, flow_run_id, seed_artifact_refs,
                )
            elif mode == "fan_out_fan_in":
                await self._execute_fan_out(plan, run_id, cycle, flow_run_id)
            elif mode == "fan_out_soft_gates":
                await self._execute_sequential(
                    plan, run_id, cycle, flow_run_id, seed_artifact_refs,
                )
            else:
                await self._execute_sequential(
                    plan, run_id, cycle, flow_run_id, seed_artifact_refs,
                )

            # Success -> completed
            await self._cycle_registry.update_run_status(run_id, RunStatus.COMPLETED)
            logger.info("Run %s completed successfully", run_id)

        except _CancellationError:
            terminal_status = "CANCELLED"
            await self._safe_transition(run_id, RunStatus.CANCELLED)
            logger.info("Run %s cancelled", run_id)

        except _ExecutionError as exc:
            terminal_status = "FAILED"
            await self._safe_transition(run_id, RunStatus.FAILED)
            logger.error("Run %s failed: %s", run_id, exc)

        except Exception as exc:
            terminal_status = "FAILED"
            await self._safe_transition(run_id, RunStatus.FAILED)
            logger.exception("Run %s failed with unexpected error: %s", run_id, exc)

        finally:
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
            if self._prefect and flow_run_id:
                try:
                    await self._prefect.set_flow_run_state(
                        flow_run_id, terminal_status, terminal_status.title()
                    )
                except Exception:
                    logger.warning("Prefect terminal state update failed", exc_info=True)

            # Run report: best-effort (D10)
            try:
                if cycle_id and run_id:
                    cycle_obj = locals().get("cycle")
                    plan_obj = locals().get("plan")
                    await self._generate_run_report(
                        cycle_id, run_id, terminal_status,
                        cycle=cycle_obj, plan=plan_obj,
                    )
            except Exception:
                logger.warning("Run report generation failed", exc_info=True)

    async def cancel_run(self, run_id: str) -> None:
        """Cancel an in-progress run."""
        self._cancelled.add(run_id)
        try:
            await self._cycle_registry.cancel_run(run_id)
        except Exception:
            logger.warning("cancel_run: registry cancel failed for %s", run_id, exc_info=True)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch_task(
        self, envelope: TaskEnvelope, run_id: str,
    ) -> TaskResult:
        """Publish task to agent queue, wait for result on reply queue."""
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
            envelope.task_id, envelope.task_type, queue_name, reply_queue,
        )

        # Poll reply queue for result
        deadline = time.monotonic() + self._task_timeout
        while time.monotonic() < deadline:
            messages = await self._queue.consume(reply_queue, max_messages=1)
            for msg in messages:
                data = json.loads(msg.payload)
                result_data = data.get("payload", {})
                if result_data.get("task_id") == envelope.task_id:
                    await self._queue.ack(msg)
                    return TaskResult.from_dict(result_data)
                # Not our message — ack to avoid blocking
                await self._queue.ack(msg)
            await asyncio.sleep(0.5)

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
        "development.build": {
            "by_producing_task": ["strategy.analyze_prd", "development.implement"],
            "by_type_fallback": ["document", "documentation"],
        },
        "qa.build_validate": {
            "by_producing_task": ["qa.validate"],
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
                        total_bytes, task_type,
                    )
                    break
                contents[ref.filename] = decoded
            except Exception:
                logger.warning(
                    "Failed to retrieve artifact %s for build task %s",
                    art_id, task_type, exc_info=True,
                )

        return contents

    async def _execute_sequential(
        self,
        plan: list[TaskEnvelope],
        run_id: str,
        cycle: Cycle,
        flow_run_id: str | None = None,
        seed_artifact_refs: list[str] | None = None,
    ) -> None:
        """Sequential: dispatch one task at a time, fail-fast."""
        import dataclasses

        prior_outputs: dict[str, Any] = {}
        all_artifact_refs: list[str] = []
        # Track stored artifacts with their refs for build pre-resolution
        stored_artifacts: list[tuple[str, ArtifactRef]] = []

        # Seed from prior plan artifacts for build-only runs (§2.3)
        if seed_artifact_refs:
            for art_id in seed_artifact_refs:
                try:
                    ref, _ = await self._artifact_vault.retrieve(art_id)
                    stored_artifacts.append((art_id, ref))
                    all_artifact_refs.append(art_id)
                except Exception:
                    logger.warning(
                        "Failed to seed artifact %s for build-only run", art_id,
                        exc_info=True,
                    )

        for envelope in plan:
            if await self._is_cancelled(run_id):
                raise _CancellationError(run_id)

            # Build extra inputs for chain context
            extra_inputs: dict[str, Any] = {
                "prior_outputs": prior_outputs,
                "artifact_refs": list(all_artifact_refs),
            }

            # Pre-resolve artifact contents for build tasks (D3)
            if envelope.task_type in self._BUILD_ARTIFACT_FILTER:
                artifact_contents = await self._resolve_artifact_contents(
                    envelope.task_type, stored_artifacts,
                )
                if artifact_contents:
                    extra_inputs["artifact_contents"] = artifact_contents

            # Inject chain context
            enriched = dataclasses.replace(
                envelope,
                inputs={
                    **envelope.inputs,
                    **extra_inputs,
                },
            )

            # Prefect: create task run
            task_run_id = None
            if self._prefect and flow_run_id:
                try:
                    role = envelope.metadata.get("role", "unknown")
                    task_run_id = await self._prefect.create_task_run(
                        flow_run_id,
                        task_key=envelope.task_type,
                        task_name=f"{role}: {envelope.task_type}",
                    )
                    await self._prefect.set_task_run_state(
                        task_run_id, "RUNNING", "Running"
                    )
                except Exception:
                    logger.warning("Prefect task run creation failed", exc_info=True)

            # Dispatch through RabbitMQ
            result = await self._dispatch_task(enriched, run_id)

            # Prefect: update task state
            if self._prefect and task_run_id:
                try:
                    state = "COMPLETED" if result.status == "SUCCEEDED" else "FAILED"
                    await self._prefect.set_task_run_state(
                        task_run_id, state, state.title()
                    )
                except Exception:
                    logger.warning("Prefect task state update failed", exc_info=True)

            # Fail-fast
            if result.status != "SUCCEEDED":
                raise _ExecutionError(
                    f"Task {envelope.task_id} ({envelope.task_type}) failed: {result.error}"
                )

            # Collect artifacts (with producing_task_type metadata)
            new_refs: list[str] = []
            for art in (result.outputs or {}).get("artifacts", []):
                ref = await self._store_artifact(
                    art, cycle, run_id, envelope,
                    producing_task_type=envelope.task_type,
                )
                new_refs.append(ref.artifact_id)
                all_artifact_refs.append(ref.artifact_id)
                stored_artifacts.append((ref.artifact_id, ref))

            if new_refs:
                await self._cycle_registry.append_artifact_refs(run_id, tuple(new_refs))

            # Chain outputs by role
            role = envelope.metadata.get("role", "unknown")
            prior_outputs[role] = {
                k: v for k, v in (result.outputs or {}).items() if k != "artifacts"
            }

            # Post-task gate check
            if self._is_gate_boundary(cycle, envelope.task_type):
                await self._handle_gate(run_id, cycle, envelope.task_type)

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

        # Prefect: pre-create task runs for all concurrent tasks
        task_run_ids: list[str | None] = [None] * len(plan)
        if self._prefect and flow_run_id:
            for i, envelope in enumerate(plan):
                try:
                    role = envelope.metadata.get("role", "unknown")
                    task_run_ids[i] = await self._prefect.create_task_run(
                        flow_run_id,
                        task_key=envelope.task_type,
                        task_name=f"{role}: {envelope.task_type}",
                    )
                    await self._prefect.set_task_run_state(
                        task_run_ids[i], "RUNNING", "Running"
                    )
                except Exception:
                    logger.warning("Prefect task run creation failed", exc_info=True)

        tasks = []
        for envelope in plan:
            enriched = dataclasses.replace(
                envelope,
                inputs={**envelope.inputs, "prior_outputs": {}, "artifact_refs": []},
            )
            tasks.append(self._dispatch_task(enriched, run_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_artifact_refs: list[str] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                if self._prefect and task_run_ids[i]:
                    try:
                        await self._prefect.set_task_run_state(
                            task_run_ids[i], "FAILED", "Failed"
                        )
                    except Exception:
                        logger.warning("Prefect task state update failed", exc_info=True)
                raise _ExecutionError(
                    f"Task {plan[i].task_id} raised exception: {result}"
                )
            # Prefect: update task state
            if self._prefect and task_run_ids[i]:
                try:
                    state = "COMPLETED" if result.status == "SUCCEEDED" else "FAILED"
                    await self._prefect.set_task_run_state(
                        task_run_ids[i], state, state.title()
                    )
                except Exception:
                    logger.warning("Prefect task state update failed", exc_info=True)
            if result.status != "SUCCEEDED":
                raise _ExecutionError(
                    f"Task {plan[i].task_id} failed: {result.error}"
                )
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
        self, run_id: str, cycle: Cycle, task_type: str
    ) -> None:
        """Pause, poll for decision, resume or reject."""
        gate_names = [
            g.name
            for g in cycle.task_flow_policy.gates
            if task_type in g.after_task_types
        ]
        logger.info("Run %s paused at gate(s): %s", run_id, gate_names)
        await self._cycle_registry.update_run_status(run_id, RunStatus.PAUSED)

        poll_interval = 2.0
        while True:
            if await self._is_cancelled(run_id):
                raise _CancellationError(run_id)

            run = await self._cycle_registry.get_run(run_id)
            for gate_name in gate_names:
                for decision in run.gate_decisions:
                    if decision.gate_name == gate_name:
                        if decision.decision == "approved":
                            await self._cycle_registry.update_run_status(
                                run_id, RunStatus.RUNNING
                            )
                            logger.info("Gate %r approved, resuming run %s", gate_name, run_id)
                            return
                        elif decision.decision == "rejected":
                            raise _ExecutionError(
                                f"Gate {gate_name!r} rejected: {decision.notes}"
                            )

            await asyncio.sleep(poll_interval)

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
            created_at=datetime.now(timezone.utc),
            cycle_id=cycle.cycle_id,
            run_id=run_id,
            metadata=metadata,
        )
        return await self._artifact_vault.store(ref, content)

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
                "Failed to transition run %s to %s", run_id, status.value,
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
                    f"- **{gd.gate_name}:** {gd.decision}"
                    + (f" — {gd.notes}" if gd.notes else "")
                )

        # Artifact inventory
        if run.artifact_refs:
            lines.append("")
            lines.append("## Artifacts")
            lines.append(f"Total artifacts: {len(run.artifact_refs)}")

        # Quality notes
        lines.append("")
        lines.append("## Quality Notes")
        if terminal_status == "COMPLETED":
            lines.append("All tasks completed successfully.")
        elif terminal_status == "FAILED":
            lines.append("One or more tasks failed. Check task artifacts for details.")
        elif terminal_status == "CANCELLED":
            lines.append("Run was cancelled before completion.")
        else:
            lines.append(f"Terminal status: {terminal_status}")

        lines.append("")

        content = "\n".join(lines)
        content_bytes = content.encode("utf-8")

        # Note: uses direct vault.store() instead of _store_artifact() because
        # the report is generated outside of any task context (no TaskEnvelope).
        ref = ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=cycle.project_id if cycle else "unknown",
            artifact_type="documentation",
            filename="run_report.md",
            content_hash=sha256(content_bytes).hexdigest(),
            size_bytes=len(content_bytes),
            media_type="text/markdown",
            created_at=datetime.now(timezone.utc),
            cycle_id=cycle_id,
            run_id=run_id,
            metadata={"report_type": "run_report"},
        )

        await self._artifact_vault.store(ref, content_bytes)
        await self._cycle_registry.append_artifact_refs(run_id, (ref.artifact_id,))
        logger.info("Run report generated for %s", run_id)
