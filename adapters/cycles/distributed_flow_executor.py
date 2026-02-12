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
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.cycles.squad_profile import SquadProfilePort

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
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._queue = queue
        self._squad_profile = squad_profile
        self._project_registry = project_registry
        self._task_timeout = task_timeout
        self._cancelled: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_run(
        self, cycle_id: str, run_id: str, profile_id: str | None = None
    ) -> None:
        """Execute a run by dispatching tasks to agent containers via RabbitMQ."""
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

            logger.info(
                "Executing run %s for cycle %s (%d tasks, mode=%s, dispatch=distributed)",
                run_id, cycle_id, len(plan), cycle.task_flow_policy.mode,
            )

            # Dispatch based on policy mode
            mode = cycle.task_flow_policy.mode
            if mode == "sequential":
                await self._execute_sequential(plan, run_id, cycle)
            elif mode == "fan_out_fan_in":
                await self._execute_fan_out(plan, run_id, cycle)
            elif mode == "fan_out_soft_gates":
                await self._execute_sequential(plan, run_id, cycle)
            else:
                await self._execute_sequential(plan, run_id, cycle)

            # Success -> completed
            await self._cycle_registry.update_run_status(run_id, RunStatus.COMPLETED)
            logger.info("Run %s completed successfully", run_id)

        except _CancellationError:
            await self._safe_transition(run_id, RunStatus.CANCELLED)
            logger.info("Run %s cancelled", run_id)

        except _ExecutionError as exc:
            await self._safe_transition(run_id, RunStatus.FAILED)
            logger.error("Run %s failed: %s", run_id, exc)

        except Exception as exc:
            await self._safe_transition(run_id, RunStatus.FAILED)
            logger.exception("Run %s failed with unexpected error: %s", run_id, exc)

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

    async def _execute_sequential(
        self,
        plan: list[TaskEnvelope],
        run_id: str,
        cycle: Cycle,
    ) -> None:
        """Sequential: dispatch one task at a time, fail-fast."""
        import dataclasses

        prior_outputs: dict[str, Any] = {}
        all_artifact_refs: list[str] = []

        for envelope in plan:
            if await self._is_cancelled(run_id):
                raise _CancellationError(run_id)

            # Inject chain context
            enriched = dataclasses.replace(
                envelope,
                inputs={
                    **envelope.inputs,
                    "prior_outputs": prior_outputs,
                    "artifact_refs": list(all_artifact_refs),
                },
            )

            # Dispatch through RabbitMQ
            result = await self._dispatch_task(enriched, run_id)

            # Fail-fast
            if result.status != "SUCCEEDED":
                raise _ExecutionError(
                    f"Task {envelope.task_id} ({envelope.task_type}) failed: {result.error}"
                )

            # Collect artifacts
            new_refs: list[str] = []
            for art in (result.outputs or {}).get("artifacts", []):
                ref = await self._store_artifact(art, cycle, run_id, envelope)
                new_refs.append(ref.artifact_id)
                all_artifact_refs.append(ref.artifact_id)

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
    ) -> None:
        """Fan-out/fan-in: dispatch all tasks concurrently, await all."""
        import dataclasses

        if await self._is_cancelled(run_id):
            raise _CancellationError(run_id)

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
                raise _ExecutionError(
                    f"Task {plan[i].task_id} raised exception: {result}"
                )
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
    ) -> ArtifactRef:
        """Store a task output artifact in the vault."""
        content = art_dict.get("content", "").encode("utf-8")
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
            metadata={
                "task_id": envelope.task_id,
                "role": envelope.metadata.get("role"),
            },
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
