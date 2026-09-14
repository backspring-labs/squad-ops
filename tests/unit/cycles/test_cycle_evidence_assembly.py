"""SIP-0108 §4.1 (a) — the cycle's evidence assembled from the stores, and resolved back to them.

Entry point: ``assess_cycle`` over a real ``MemoryCycleRegistry`` and a real
``FilesystemArtifactVault`` — the same two ports the live stores implement — so what reaches
``assess`` is what the stores hold, and every reference it cites is checked against them.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from datetime import UTC, datetime, timedelta

import pytest

from adapters.cycles.cycle_evidence import assess_cycle, unresolved_refs
from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.cycle_assessment import (
    UNRECORDED_PROOFS,
    UNRECORDED_ROUND_FAILURE_EVENTS,
    AssessorIdentity,
    EvidenceRef,
    Indicator,
    IndicatorState,
    RefKind,
)
from squadops.cycles.failure_attribution import AttributionClass, TerminalKind
from squadops.cycles.llm_usage import RunUsage, UsageTotals
from squadops.cycles.models import ArtifactRef, Cycle, GateDecision, Run, TaskFlowPolicy
from squadops.cycles.run_loop_summary import MovementRecord, RunLoopSummary, RunTerminalDecision
from squadops.cycles.verification_integrity import aggregate_verification

pytestmark = [pytest.mark.domain_orchestration]

T0 = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
ASSESSOR = AssessorIdentity(framework_version="1.8.0", git_sha="abc1234")


async def _store(vault, artifact_id, run_id, artifact_type, filename, content, **metadata):
    await vault.store(
        ArtifactRef(
            artifact_id=artifact_id,
            project_id="proj",
            artifact_type=artifact_type,
            filename=filename,
            content_hash="",
            size_bytes=0,
            media_type="application/json",
            created_at=T0,
            cycle_id="cyc_1",
            run_id=run_id,
            metadata=metadata,
        ),
        content.encode("utf-8"),
    )


@pytest.fixture
async def stores(tmp_path):
    registry = MemoryCycleRegistry()
    vault = FilesystemArtifactVault(tmp_path / "vault")
    await registry.create_cycle(
        Cycle(
            cycle_id="cyc_1",
            project_id="proj",
            created_at=T0,
            created_by="admin",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )
    )
    refused = GateDecision(
        gate_name="progress_plan_review",
        decision="rejected",
        decided_by="system:plan_validation",
        decided_at=T0,
    )
    for run_id, number, workload, status, gates in (
        ("run_f1", 1, "framing", "cancelled", (refused,)),
        ("run_f2", 2, "framing", "completed", ()),
        ("run_i1", 3, "implementation", "failed", ()),
    ):
        await registry.create_run(
            Run(
                run_id=run_id,
                cycle_id="cyc_1",
                run_number=number,
                status=status,
                initiated_by="api",
                resolved_config_hash="h",
                started_at=T0,
                finished_at=T0 + timedelta(minutes=10 * number),
                gate_decisions=gates,
                workload_type=workload,
            )
        )
    for run_id in ("run_f2", "run_i1"):
        await registry.record_run_verification_summary(run_id, aggregate_verification([]))
    await registry.record_run_loop_summary(
        "run_i1",
        RunLoopSummary(
            run_id="run_i1",
            usage=RunUsage(
                by_task_type={"qa.test": UsageTotals(calls=5)},
                tasks_reported=1,
                tasks_unreported=(),
            ),
            movements=(MovementRecord("t-qa", 0, "new"), MovementRecord("t-qa", 1, "repeat")),
            terminal=RunTerminalDecision(
                kind=TerminalKind.CORRECTION_TERMINATED,
                termination_reason="exhausted",
                task_id="t-qa",
            ),
        ),
    )
    await _store(
        vault,
        "art_rej",
        "run_f1",
        "rejection_record",
        "rejection_record.json",
        json.dumps(
            {
                "gate": "progress_plan_review",
                "classes": {"validate_criteria_scope": 1},
                "proofs": {},
                "errors": ["x"],
            }
        ),
    )
    await _store(
        vault,
        "art_dec",
        "run_i1",
        "document",
        "correction_decision.md",
        "# decision",
        producing_task_type="governance.correction_decision",
        task_id="t-dec",
    )
    await _store(
        vault,
        "art_fail",
        "run_i1",
        "document",
        "notes.md",
        "draft",
        producing_task_type="qa.test",
        task_id="t-qa",
        emission_status="failed",
        attempt=1,
    )
    return registry, vault


async def test_the_stores_assemble_into_an_assessment_whose_every_reference_resolves(stores):
    """SIP-0108 §5 criterion 1, on the ports the live stores implement. Bug caught: an indicator
    citing a record the stores do not hold, or an assembled fact the projection never saw."""
    registry, vault = stores

    assessment = await assess_cycle(registry, vault, "cyc_1", assessor=ASSESSOR)

    assert assessment.indicator("framing_rerolls").refs == (EvidenceRef(RefKind.RUN, "run_f2"),)
    assert assessment.indicator("correction_rounds").refs == (
        EvidenceRef(RefKind.ARTIFACT, "art_dec"),
    )
    assert assessment.indicator("failed_emissions").value == 1
    tokens = assessment.indicator("tokens_by_run")
    assert (tokens.state, tokens.reason) == (
        IndicatorState.UNASKABLE,
        "no_run_summary: run_f1, run_f2",
    )
    reading = assessment.attribution
    assert reading.terminal_kind == TerminalKind.CORRECTION_TERMINATED
    assert reading.attribution.primary == AttributionClass.BUDGET_EXHAUSTION
    assert reading.unrecorded == (UNRECORDED_ROUND_FAILURE_EVENTS,)

    assert await unresolved_refs(assessment, registry, vault) == []


async def test_a_reference_to_a_record_no_longer_in_the_vault_is_reported(stores, tmp_path):
    """Bug caught: the resolution check passing on a reference that names nothing."""
    registry, vault = stores
    assessment = await assess_cycle(registry, vault, "cyc_1", assessor=ASSESSOR)
    shutil.rmtree(next((tmp_path / "vault").rglob("art_dec")))
    fresh = FilesystemArtifactVault(tmp_path / "vault")

    assert await unresolved_refs(assessment, registry, fresh) == [
        EvidenceRef(RefKind.ARTIFACT, "art_dec")
    ]


async def test_the_last_framing_runs_refusal_is_read_from_its_rejection_record(stores):
    """The gate path: a cycle whose final run is the refused framing run reads the record's
    validators, not the note."""
    registry, vault = stores
    for run_id in ("run_f2", "run_i1"):
        registry._runs.pop(run_id)

    reading = (await assess_cycle(registry, vault, "cyc_1", assessor=ASSESSOR)).attribution

    assert reading.terminal_kind == TerminalKind.PLAN_GATE_REFUSED
    assert [c.value for c in reading.attribution.contributing] == ["validate_criteria_scope"]
    assert EvidenceRef(RefKind.ARTIFACT, "art_rej") in reading.refs


async def test_a_rejection_record_older_than_its_proofs_is_read_as_such(stores, tmp_path):
    """Bug caught: a record written before the gate recorded proofs assembled as ``proofs: {}``
    — "no proof failed" — when the record simply cannot say."""
    registry, vault = stores
    for run_id in ("run_f2", "run_i1"):
        registry._runs.pop(run_id)
    (record_file,) = (tmp_path / "vault").rglob("rejection_record.json")
    record_file.write_text(json.dumps({"gate": "g", "classes": {"validate_criteria_scope": 1}}))

    reading = (await assess_cycle(registry, vault, "cyc_1", assessor=ASSESSOR)).attribution

    assert reading.unrecorded == (UNRECORDED_PROOFS,)


@pytest.mark.parametrize(
    "ref",
    [
        EvidenceRef(RefKind.RUN, "run_missing"),
        EvidenceRef(RefKind.ARTIFACT, "art_missing"),
        EvidenceRef(RefKind.VERIFICATION_SUMMARY, "run_f1"),
        EvidenceRef(RefKind.RUN_SUMMARY, "run_f2"),
    ],
    ids=["run", "artifact", "verification summary", "run summary"],
)
async def test_each_kind_of_reference_resolves_only_against_a_record_that_exists(stores, ref):
    """Bug caught: a reference kind the resolver waves through — a run-summary key for a run
    that has no row read as resolved."""
    registry, vault = stores
    assessment = await assess_cycle(registry, vault, "cyc_1", assessor=ASSESSOR)
    probe = dataclasses.replace(
        assessment,
        outcome=(Indicator("probe", IndicatorState.OBSERVED, value=1, refs=(ref,)),),
        quality=(),
        coordination=(),
        efficiency=(),
    )

    assert await unresolved_refs(probe, registry, vault) == [ref]
