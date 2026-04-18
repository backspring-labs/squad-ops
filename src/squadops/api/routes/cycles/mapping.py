"""
Domain ↔ DTO mapping functions for SIP-0064.
"""

from __future__ import annotations

from squadops.api.routes.cycles.dtos import (
    AgentProfileEntryResponse,
    ArtifactRefResponse,
    CycleResponse,
    GateDecisionResponse,
    GateDTO,
    ProjectResponse,
    RunResponse,
    SquadProfileResponse,
    TaskFlowPolicyDTO,
    WorkloadProgressEntry,
)
from squadops.api.runtime.agent_labels import get_role_label
from squadops.cycles.lifecycle import resolve_cycle_status
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    GateDecisionValue,
    Project,
    Run,
    RunStatus,
    SquadProfile,
)


def project_to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        tags=list(project.tags),
        has_prd=project.prd_path is not None,
    )


def run_to_response(run: Run) -> RunResponse:
    return RunResponse(
        run_id=run.run_id,
        cycle_id=run.cycle_id,
        run_number=run.run_number,
        status=run.status,
        initiated_by=run.initiated_by,
        resolved_config_hash=run.resolved_config_hash,
        resolved_config_ref=run.resolved_config_ref,
        started_at=run.started_at,
        finished_at=run.finished_at,
        gate_decisions=[
            GateDecisionResponse(
                gate_name=gd.gate_name,
                decision=gd.decision,
                decided_by=gd.decided_by,
                decided_at=gd.decided_at,
                notes=gd.notes,
            )
            for gd in run.gate_decisions
        ],
        artifact_refs=list(run.artifact_refs),
        workload_type=run.workload_type,
    )


def _policy_to_dto(policy) -> TaskFlowPolicyDTO:
    return TaskFlowPolicyDTO(
        mode=policy.mode,
        gates=[
            GateDTO(
                name=g.name,
                description=g.description,
                after_task_types=list(g.after_task_types),
            )
            for g in policy.gates
        ],
    )


_RUN_STATUS_TO_PROGRESS: dict[str, str] = {
    RunStatus.QUEUED.value: "pending",
    RunStatus.RUNNING.value: "running",
    RunStatus.PAUSED.value: "gate_awaiting",
    RunStatus.COMPLETED.value: "completed",
    RunStatus.FAILED.value: "failed",
}


def compute_workload_progress(
    workload_sequence: list[dict],
    runs: list[Run],
) -> list[WorkloadProgressEntry]:
    """Derive workload_progress by positional alignment (SIP-0083 §5.8).

    Non-cancelled runs are sorted by run_number and aligned to
    workload_sequence entries positionally.  Domain run statuses are
    mapped to the DTO vocabulary; raw status values are never passed
    through.
    """
    non_cancelled = sorted(
        [r for r in runs if r.status != RunStatus.CANCELLED.value],
        key=lambda r: r.run_number,
    )
    entries = []
    for i, ws_entry in enumerate(workload_sequence):
        if i < len(non_cancelled):
            run = non_cancelled[i]
            gate_name = ws_entry.get("gate")
            rejected = gate_name and any(
                gd.decision == GateDecisionValue.REJECTED
                for gd in run.gate_decisions
                if gd.gate_name == gate_name
            )
            if rejected:
                status = "rejected"
            else:
                status = _RUN_STATUS_TO_PROGRESS.get(run.status, run.status)
            entries.append(
                WorkloadProgressEntry(
                    index=i,
                    workload_type=ws_entry.get("type", "unknown"),
                    run_id=run.run_id,
                    status=status,
                )
            )
        else:
            entries.append(
                WorkloadProgressEntry(
                    index=i,
                    workload_type=ws_entry.get("type", "unknown"),
                    run_id=None,
                    status="pending",
                )
            )
    return entries


def cycle_to_response(cycle: Cycle, runs: list[Run]) -> CycleResponse:
    ws = cycle.applied_defaults.get("workload_sequence", [])
    progress = compute_workload_progress(ws, runs)
    workload_statuses = [e.status for e in progress] if progress else None
    status = resolve_cycle_status(
        runs, cycle_cancelled=cycle.cancelled, workload_statuses=workload_statuses
    )
    return CycleResponse(
        cycle_id=cycle.cycle_id,
        project_id=cycle.project_id,
        created_at=cycle.created_at,
        created_by=cycle.created_by,
        prd_ref=cycle.prd_ref,
        squad_profile_id=cycle.squad_profile_id,
        squad_profile_snapshot_ref=cycle.squad_profile_snapshot_ref,
        task_flow_policy=_policy_to_dto(cycle.task_flow_policy),
        build_strategy=cycle.build_strategy,
        applied_defaults=cycle.applied_defaults,
        execution_overrides=cycle.execution_overrides,
        expected_artifact_types=list(cycle.expected_artifact_types),
        experiment_context=cycle.experiment_context,
        notes=cycle.notes,
        status=status.value,
        runs=[run_to_response(r) for r in runs],
        workload_progress=progress,
    )


def profile_to_response(
    profile: SquadProfile,
    *,
    is_active: bool = False,
    warnings: list[str] | None = None,
) -> SquadProfileResponse:
    return SquadProfileResponse(
        profile_id=profile.profile_id,
        name=profile.name,
        description=profile.description,
        version=profile.version,
        agents=[
            AgentProfileEntryResponse(
                agent_id=a.agent_id,
                role=a.role,
                role_label=get_role_label(a.role),
                display_name=a.agent_id.title(),
                model=a.model,
                enabled=a.enabled,
                config_overrides=a.config_overrides,
            )
            for a in profile.agents
        ],
        created_at=profile.created_at,
        is_active=is_active,
        warnings=warnings or [],
    )


def artifact_to_response(artifact: ArtifactRef) -> ArtifactRefResponse:
    return ArtifactRefResponse(
        artifact_id=artifact.artifact_id,
        project_id=artifact.project_id,
        cycle_id=artifact.cycle_id,
        run_id=artifact.run_id,
        artifact_type=artifact.artifact_type,
        filename=artifact.filename,
        content_hash=artifact.content_hash,
        size_bytes=artifact.size_bytes,
        media_type=artifact.media_type,
        created_at=artifact.created_at,
        metadata=artifact.metadata,
        vault_uri=artifact.vault_uri,
        promotion_status=artifact.promotion_status,
        # Prompt provenance (SIP-0084 §10)
        system_prompt_bundle_hash=artifact.system_prompt_bundle_hash,
        system_fragment_ids=artifact.system_fragment_ids,
        system_fragment_versions=artifact.system_fragment_versions,
        request_template_id=artifact.request_template_id,
        request_template_version=artifact.request_template_version,
        request_render_hash=artifact.request_render_hash,
        capability_supplement_ids=artifact.capability_supplement_ids,
        full_invocation_bundle_hash=artifact.full_invocation_bundle_hash,
        prompt_environment=artifact.prompt_environment,
    )
