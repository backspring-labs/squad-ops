"""Assemble a cycle's :class:`CycleEvidence` from durable stores, and resolve its references.

The I/O half of SIP-0108 §4.1 (a): ``squadops.cycles.cycle_assessment.assess`` is pure and
reads only its arguments, so everything it reads is gathered here from the registry and the
vault — never from logs, never from a running process. The same two ports resolve an
assessment's evidence references back to the records they name, which is the acceptance check
("every observed indicator's evidence reference resolves").
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from squadops.cycles.cycle_assessment import (
    ArtifactRecord,
    AssessorIdentity,
    CycleAssessment,
    CycleEvidence,
    EvidenceRef,
    GateDecisionRecord,
    IndicatorState,
    RefKind,
    RejectionRecord,
    RunRecord,
    TerminationRecord,
    assess,
)
from squadops.cycles.cycle_outcome import resolve_cycle_outcome
from squadops.cycles.rejection_baseline import REJECTION_ARTIFACT_TYPE
from squadops.cycles.task_outcome import CORRECTION_TERMINATION_ARTIFACT_TYPE

if TYPE_CHECKING:
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.ports.cycles.cycle_registry import CycleRegistryPort

logger = logging.getLogger(__name__)

#: The registry pages runs; a cycle has a handful, but the read must not silently truncate.
_RUN_PAGE = 50


async def assess_cycle(
    registry: CycleRegistryPort,
    vault: ArtifactVaultPort,
    cycle_id: str,
    *,
    assessor: AssessorIdentity,
) -> CycleAssessment:
    """Read a cycle's outcome and evidence from the stores, then project them."""
    outcome = await resolve_cycle_outcome(registry, cycle_id)
    evidence = await assemble_cycle_evidence(registry, vault, cycle_id)
    return assess(outcome, evidence, assessor=assessor)


async def _all_runs(registry: CycleRegistryPort, cycle_id: str) -> list:
    runs: list = []
    while True:
        page = await registry.list_runs(cycle_id, limit=_RUN_PAGE, offset=len(runs))
        runs.extend(page)
        if len(page) < _RUN_PAGE:
            return runs


async def assemble_cycle_evidence(
    registry: CycleRegistryPort, vault: ArtifactVaultPort, cycle_id: str
) -> CycleEvidence:
    """Everything ``assess`` reads beside ``CycleOutcome``, from the registry and the vault."""
    cycle = await registry.get_cycle(cycle_id)
    runs = await _all_runs(registry, cycle_id)
    summary_runs: list[str] = []
    loop_summaries = {}
    for run in runs:
        if await registry.get_run_verification_summary(run.run_id) is not None:
            summary_runs.append(run.run_id)
        loop = await registry.get_run_loop_summary(run.run_id)
        if loop is not None:
            loop_summaries[run.run_id] = loop

    refs = await vault.list_artifacts(project_id=cycle.project_id, cycle_id=cycle_id)
    artifacts = []
    rejections = []
    terminations = []
    for ref in sorted(refs, key=lambda r: (str(r.run_id), r.created_at, r.artifact_id)):
        meta = ref.metadata or {}
        attempt = meta.get("attempt")
        artifacts.append(
            ArtifactRecord(
                artifact_id=ref.artifact_id,
                run_id=str(ref.run_id or ""),
                artifact_type=ref.artifact_type,
                producing_task_type=meta.get("producing_task_type"),
                task_id=meta.get("task_id"),
                emission_status=meta.get("emission_status"),
                attempt=int(attempt) if isinstance(attempt, int) else None,
            )
        )
        if ref.artifact_type == REJECTION_ARTIFACT_TYPE:
            payload = await _json_content(vault, ref.artifact_id)
            if payload is not None:
                rejections.append(
                    RejectionRecord(
                        artifact_id=ref.artifact_id,
                        run_id=str(ref.run_id or ""),
                        gate=str(payload.get("gate") or ""),
                        classes={str(k): int(v) for k, v in (payload.get("classes") or {}).items()},
                        proofs=(
                            {str(k): int(v) for k, v in (payload.get("proofs") or {}).items()}
                            if "proofs" in payload
                            else None
                        ),
                    )
                )
        elif ref.artifact_type == CORRECTION_TERMINATION_ARTIFACT_TYPE:
            payload = await _json_content(vault, ref.artifact_id)
            if payload is not None:
                terminations.append(
                    TerminationRecord(
                        artifact_id=ref.artifact_id,
                        run_id=str(ref.run_id or ""),
                        reason=str(payload.get("reason") or ""),
                        failed_task_id=str(payload.get("failed_task_id") or ""),
                    )
                )

    return CycleEvidence(
        cycle_id=cycle_id,
        runs=tuple(
            RunRecord(
                run_id=run.run_id,
                run_number=run.run_number,
                workload_type=run.workload_type,
                status=str(run.status),
                started_at=run.started_at,
                finished_at=run.finished_at,
                gate_decisions=tuple(
                    GateDecisionRecord(
                        gate_name=g.gate_name,
                        decision=str(g.decision),
                        decided_by=str(g.decided_by or ""),
                        waived_checks=tuple(g.waived_checks or ()),
                    )
                    for g in run.gate_decisions
                ),
            )
            for run in sorted(runs, key=lambda r: r.run_number)
        ),
        verification_summary_runs=tuple(summary_runs),
        loop_summaries=loop_summaries,
        artifacts=tuple(artifacts),
        rejection_records=tuple(rejections),
        terminations=tuple(terminations),
    )


async def _json_content(vault: ArtifactVaultPort, artifact_id: str) -> dict | None:
    """A JSON artifact's content, or ``None`` when it cannot be read — the record that needed
    it then reads unaskable, never a guessed value."""
    try:
        _, content = await vault.retrieve(artifact_id)
        payload = json.loads(content)
    except Exception:
        logger.warning("assessment evidence: artifact %s unreadable", artifact_id, exc_info=True)
        return None
    return payload if isinstance(payload, dict) else None


async def unresolved_refs(
    assessment: CycleAssessment, registry: CycleRegistryPort, vault: ArtifactVaultPort
) -> list[EvidenceRef]:
    """The observed indicators' and attribution's references that name no record in the stores.

    Empty is the acceptance condition (SIP-0108 §5, criterion 1).
    """
    wanted: set[EvidenceRef] = set()
    for group in (
        assessment.outcome,
        assessment.quality,
        assessment.coordination,
        assessment.efficiency,
    ):
        for ind in group:
            if ind.state != IndicatorState.UNASKABLE:
                wanted.update(ind.refs)
    if assessment.attribution.state != IndicatorState.UNASKABLE:
        wanted.update(assessment.attribution.refs)

    missing: list[EvidenceRef] = []
    for ref in sorted(wanted):
        if not await _resolves(ref, registry, vault):
            missing.append(ref)
    return missing


async def _resolves(
    ref: EvidenceRef, registry: CycleRegistryPort, vault: ArtifactVaultPort
) -> bool:
    try:
        if ref.kind == RefKind.RUN:
            await registry.get_run(ref.id)
            return True
        if ref.kind == RefKind.ARTIFACT:
            await vault.get_metadata(ref.id)
            return True
        if ref.kind == RefKind.VERIFICATION_SUMMARY:
            return await registry.get_run_verification_summary(ref.id) is not None
        if ref.kind == RefKind.RUN_SUMMARY:
            return await registry.get_run_loop_summary(ref.id) is not None
    except Exception:
        return False
    return False
