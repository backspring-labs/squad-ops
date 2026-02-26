"""
In-process flow executor adapter (SIP-0064 T8, SIP-0066).

Drives cycle execution: generates task plan, dispatches tasks through
AgentOrchestrator, manages run status transitions, handles gates,
collects artifacts, and chains task outputs forward.

SIP-0066 Phases 2-7: Full implementation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from squadops.cycles.models import ArtifactRef, Cycle, RunStatus
from squadops.cycles.task_plan import generate_task_plan
from squadops.ports.cycles.flow_execution import FlowExecutionPort

if TYPE_CHECKING:
    from squadops.orchestration.orchestrator import AgentOrchestrator
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.cycles.squad_profile import SquadProfilePort
    from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)


class _ExecutionError(Exception):
    """Internal: task failure or gate rejection."""


class _CancellationError(Exception):
    """Internal: run was cancelled."""


class InProcessFlowExecutor(FlowExecutionPort):
    """In-process flow executor that interprets TaskFlowPolicy.

    SIP-0066: Constructor injection with required deps (D12).
    Orchestrator stays stateless about cycle lifecycle (§5.1).
    """

    def __init__(
        self,
        cycle_registry: CycleRegistryPort | None = None,
        artifact_vault: ArtifactVaultPort | None = None,
        orchestrator: AgentOrchestrator | None = None,
        squad_profile: SquadProfilePort | None = None,
        project_registry: ProjectRegistryPort | None = None,
    ) -> None:
        self._cycle_registry = cycle_registry
        self._artifact_vault = artifact_vault
        self._orchestrator = orchestrator
        self._squad_profile = squad_profile
        self._project_registry = project_registry
        self._cancelled: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_run(self, cycle_id: str, run_id: str, profile_id: str | None = None) -> None:
        """Execute a run by loading authoritative state from registry.

        SIP-0066 §5.3: Breaking signature change (cycle_id, run_id, profile_id).
        """
        try:
            cycle = await self._cycle_registry.get_cycle(cycle_id)
            run = await self._cycle_registry.get_run(run_id)
            profile, _ = await self._squad_profile.resolve_snapshot(profile_id)

            # Resolve PRD content: explicit prd_ref wins, else load from project config
            prd_content = cycle.prd_ref
            if not prd_content:
                prd_content = await self._resolve_prd_from_project(cycle.project_id)
            if prd_content and prd_content != cycle.prd_ref:
                import dataclasses as _dc

                cycle = _dc.replace(cycle, prd_ref=prd_content)

            # queued → running
            await self._cycle_registry.update_run_status(run_id, RunStatus.RUNNING)

            plan = generate_task_plan(cycle, run, profile)

            logger.info(
                "Executing run %s for cycle %s (%d tasks, mode=%s)",
                run_id,
                cycle_id,
                len(plan),
                cycle.task_flow_policy.mode,
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

            # Success → completed
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
        """Cancel an in-progress run (D9: registry-driven + local fast-path)."""
        self._cancelled.add(run_id)
        try:
            await self._cycle_registry.cancel_run(run_id)
        except Exception:
            logger.warning("cancel_run: registry cancel failed for %s", run_id, exc_info=True)

    # ------------------------------------------------------------------
    # Execution strategies
    # ------------------------------------------------------------------

    async def _execute_sequential(
        self,
        plan: list[TaskEnvelope],
        run_id: str,
        cycle: Cycle,
    ) -> None:
        """Sequential: submit one task at a time, fail-fast (§5.8)."""
        import dataclasses

        prior_outputs: dict[str, Any] = {}
        all_artifact_refs: list[str] = []

        for envelope in plan:
            # D9: check cancellation before each dispatch
            if await self._is_cancelled(run_id):
                raise _CancellationError(run_id)

            # D6: inject chain context via dataclasses.replace
            enriched = dataclasses.replace(
                envelope,
                inputs={
                    **envelope.inputs,
                    "prior_outputs": prior_outputs,
                    "artifact_refs": list(all_artifact_refs),
                },
            )

            # Dispatch through orchestrator
            result = await self._orchestrator.submit_task(enriched)

            # Fail-fast: first failure → run failed (§5.8)
            if result.status != "SUCCEEDED":
                raise _ExecutionError(
                    f"Task {envelope.task_id} ({envelope.task_type}) failed: {result.error}"
                )

            # Collect artifacts — only new refs for this step (Tightening #1)
            new_refs: list[str] = []
            for art in (result.outputs or {}).get("artifacts", []):
                ref = await self._store_artifact(art, cycle, run_id, envelope)
                new_refs.append(ref.artifact_id)
                all_artifact_refs.append(ref.artifact_id)

            # Persist only this step's new refs (avoids duplicate explosion)
            if new_refs:
                await self._cycle_registry.append_artifact_refs(run_id, tuple(new_refs))

            # Chain outputs by role_id (strat/dev/qa/data/lead)
            role = envelope.metadata.get("role", "unknown")
            prior_outputs[role] = {
                k: v for k, v in (result.outputs or {}).items() if k != "artifacts"
            }

            # D11: post-task gate check
            if self._is_gate_boundary(cycle, envelope.task_type):
                await self._handle_gate(run_id, cycle, envelope.task_type)

    async def _execute_fan_out(
        self,
        plan: list[TaskEnvelope],
        run_id: str,
        cycle: Cycle,
    ) -> None:
        """Fan-out/fan-in: submit all, await all (§5.6)."""
        import dataclasses

        if await self._is_cancelled(run_id):
            raise _CancellationError(run_id)

        tasks = []
        for envelope in plan:
            enriched = dataclasses.replace(
                envelope,
                inputs={**envelope.inputs, "prior_outputs": {}, "artifact_refs": []},
            )
            tasks.append(self._orchestrator.submit_task(enriched))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_artifact_refs: list[str] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise _ExecutionError(f"Task {plan[i].task_id} raised exception: {result}")
            if result.status != "SUCCEEDED":
                raise _ExecutionError(f"Task {plan[i].task_id} failed: {result.error}")
            # Collect artifacts
            for art in (result.outputs or {}).get("artifacts", []):
                ref = await self._store_artifact(art, cycle, run_id, plan[i])
                all_artifact_refs.append(ref.artifact_id)

        if all_artifact_refs:
            await self._cycle_registry.append_artifact_refs(run_id, tuple(all_artifact_refs))

    # ------------------------------------------------------------------
    # Gate handling (Phase 6)
    # ------------------------------------------------------------------

    def _is_gate_boundary(self, cycle: Cycle, task_type: str) -> bool:
        """Check if completed task_type triggers a gate (D11: post-task)."""
        for gate in cycle.task_flow_policy.gates:
            if task_type in gate.after_task_types:
                return True
        return False

    async def _handle_gate(self, run_id: str, cycle: Cycle, task_type: str) -> None:
        """Pause, poll for decision, resume or reject (§5.7)."""
        gate_names = [
            g.name for g in cycle.task_flow_policy.gates if task_type in g.after_task_types
        ]
        logger.info("Run %s paused at gate(s): %s", run_id, gate_names)
        await self._cycle_registry.update_run_status(run_id, RunStatus.PAUSED)

        poll_interval = 2.0  # seconds
        while True:
            # D9: check cancellation between polls
            if await self._is_cancelled(run_id):
                raise _CancellationError(run_id)

            run = await self._cycle_registry.get_run(run_id)
            for gate_name in gate_names:
                for decision in run.gate_decisions:
                    if decision.gate_name == gate_name:
                        if decision.decision == "approved":
                            await self._cycle_registry.update_run_status(run_id, RunStatus.RUNNING)
                            logger.info("Gate %r approved, resuming run %s", gate_name, run_id)
                            return  # Resume
                        elif decision.decision == "rejected":
                            raise _ExecutionError(f"Gate {gate_name!r} rejected: {decision.notes}")

            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _is_cancelled(self, run_id: str) -> bool:
        """D9: check local fast-path set AND registry state (source of truth)."""
        if run_id in self._cancelled:
            return True
        run = await self._cycle_registry.get_run(run_id)
        if run.status == RunStatus.CANCELLED.value:
            self._cancelled.add(run_id)  # cache for fast path
            return True
        return False

    async def _store_artifact(
        self,
        art_dict: dict[str, Any],
        cycle: Cycle,
        run_id: str,
        envelope: TaskEnvelope,
    ) -> ArtifactRef:
        """Store a task output artifact in the vault (Discovery #12)."""
        content = art_dict.get("content", "").encode("utf-8")
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
                "Failed to transition run %s to %s",
                run_id,
                status.value,
                exc_info=True,
            )
