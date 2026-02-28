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
)
from squadops.api.runtime.agent_labels import get_role_label
from squadops.cycles.models import (
    ArtifactRef,
    Cycle,
    Project,
    Run,
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


def cycle_to_response(cycle: Cycle, runs: list[Run], status: str) -> CycleResponse:
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
        status=status,
        runs=[run_to_response(r) for r in runs],
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
    )
