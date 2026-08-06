"""#663 S2 golden harness — correction-path envelope equivalence.

Pins the EXACT repair-envelope and retest-envelope inputs the correction
protocol produces, as canonical JSON goldens captured BEFORE the S2
extraction (correction-path context declarations move beside the
context-assembly registry). Same contract as
``test_context_assembly_golden.py``: every #663 slice keeps these
byte-identical — a deliberate context change must regenerate the golden in
the same PR and read as a behavior change, never a silent refactor side
effect.

The capture seam is ``_dispatch_protocol_step`` (mocked): envelopes arrive
there with final inputs, un-enriched — exactly the composition S2 relocates.

Regenerate: UPDATE_CONTEXT_GOLDENS=1 pytest tests/unit/cycles/test_correction_context_golden.py
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.correction_runner import CorrectionRunner
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_orchestration]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "correction_context.json"
_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)

_CYCLE = SimpleNamespace(
    cycle_id="cyc_golden",
    project_id="proj",
    prd_ref="PRD-CONTENT",
    resolved_config=lambda: {},
)

_RUN_ID = "run_abcdef123456"

# Deterministic protocol-step results keyed by task type: the analyzer and
# the governance decision drive the protocol to the patch path; repair and
# retest steps return empty artifact sets (their outputs are not under test —
# their INPUTS are).
_STEP_OUTPUTS: dict[str, dict] = {
    "data.analyze_failure": {
        "classification": "work_product",
        "analysis_summary": "the emitted routes module fails its endpoint check",
    },
    "governance.correction_decision": {
        "correction_path": "patch",
        "decision_rationale": "patch the failing artifact",
        "affected_task_types": ["development.develop"],
        "structural_plan_change_candidate": "none",
    },
}


def _failed_envelope(task_type: str, inputs: dict, role: str) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=f"task-{task_type}",
        agent_id="agent",
        cycle_id="cyc_golden",
        pulse_id="p1",
        project_id="proj",
        task_type=task_type,
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
        inputs=dict(inputs),
        metadata={"role": role},
    )


_DEV_FAILED_INPUTS = {
    "prd": "PRD-CONTENT",
    "resolved_config": {"build_profile": "fastapi_react_vite"},
    "subtask_focus": "Backend API",
    "subtask_description": "Create endpoints",
    "expected_artifacts": ["backend/routes.py"],
    "implementation_artifacts": ["backend/routes.py", "backend/models.py"],
    "acceptance_criteria": [
        {"check": "endpoint_defined", "params": {"method": "GET", "path": "/api/runs"}}
    ],
    "artifact_contents": {"backend/models.py": "class Run: ..."},
}

_DEV_FAILED_RESULT = TaskResult(
    task_id="task-development.develop",
    status="FAILED",
    outputs={
        "outcome_class": "SEMANTIC_FAILURE",
        "failure_classification": "work_product",
        "validation_result": {
            "passed": False,
            "summary": "1/2 checks passed",
            "missing_components": [],
            "checks": [
                {"check": "endpoint_defined", "passed": False, "detail": "GET /api/runs missing"}
            ],
        },
        "artifacts": [
            {"name": "backend/routes.py", "type": "source", "content": "def broken(): ..."}
        ],
    },
    error="validation failed",
)

_QA_FAILED_INPUTS = {
    "prd": "PRD-CONTENT",
    "resolved_config": {"build_profile": "fastapi_react_vite"},
    "subtask_focus": "API tests",
    "subtask_description": "Write tests",
    "expected_artifacts": ["tests/test_api.py"],
    "acceptance_criteria": [{"check": "expected_artifacts", "params": {}}],
    "artifact_contents": {"backend/routes.py": "def ok(): ..."},
    "acceptance_workspace_files": {"backend/routes.py": "def ok(): ...", "backend/models.py": "x"},
    "contract_probes": [{"probe": "GET /api/runs", "expect_status": 200}],
    "dom_testid_surface": ["run-list", "run-form-submit"],
}

# Zero-extraction marker → OWN_ARTIFACT locus → qa re-produces its own suite.
_QA_FAILED_RESULT = TaskResult(
    task_id="task-qa.test",
    status="FAILED",
    outputs={
        "outcome_class": "SEMANTIC_FAILURE",
        "emission_failure": {"reason": "zero_extraction", "raw_response_chars": 812},
        "validation_result": {"passed": False, "summary": "no artifacts", "checks": []},
        "artifacts": [],
    },
    error="no artifacts extracted",
)


@pytest.fixture(scope="module")
def manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def harness(monkeypatch):
    """A CorrectionRunner with the dispatch seam mocked to capture envelope
    inputs (deep-copied at capture — ``prior_outputs`` mutates between steps)
    and uuids pinned so the plan-delta artifact id in ``artifact_refs`` is
    stable."""
    runner = CorrectionRunner(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        event_bus=MagicMock(),
        task_dispatcher=AsyncMock(),
        store_artifact=AsyncMock(),
    )
    captured: list[tuple[str, str, dict]] = []

    async def _capture_dispatch(step_envelope, *args, **kwargs):
        captured.append(
            (step_envelope.task_id, step_envelope.task_type, copy.deepcopy(step_envelope.inputs))
        )
        outputs = _STEP_OUTPUTS.get(step_envelope.task_type, {"artifacts": []})
        return TaskResult(task_id=step_envelope.task_id, status="SUCCEEDED", outputs=dict(outputs))

    monkeypatch.setattr(runner, "_dispatch_protocol_step", _capture_dispatch)

    counter = iter(range(10_000))
    monkeypatch.setattr("uuid.uuid4", lambda: SimpleNamespace(hex=f"{next(counter):032d}"))
    return runner, captured


async def _run_repair_scenario(
    harness, manifest_obj, *, envelope, result, scaffold_enforcement_carry=None
):
    runner, captured = harness
    await runner.run_correction_protocol(
        run_id=_RUN_ID,
        cycle=_CYCLE,
        envelope=envelope,
        result=result,
        correction_attempts=0,
        prior_outputs={"dev": {"summary": "[dev] built"}},
        all_artifact_refs=["art_routes"],
        stored_artifacts=[],
        completed_task_ids=["task-development.develop"],
        plan_delta_refs=[],
        profile=None,
        flow_run_id=None,
        interface_manifest=manifest_obj,
        artifact_contents=None,
        scaffold_enforcement_carry=scaffold_enforcement_carry,
        budget_guard=None,
        signature_state=None,
    )
    return {
        "repair_steps": [
            {"task_type": task_type, "inputs": inputs}
            for task_id, task_type, inputs in captured
            if task_id.startswith("repair-")
        ]
    }


async def _run_retest_scenario(harness, *, failed_inputs, patched_artifacts):
    runner, captured = harness
    result = await runner.reexecute_repaired_suite(
        run_id=_RUN_ID,
        cycle=_CYCLE,
        envelope=_failed_envelope("qa.test", failed_inputs, "qa"),
        patched_artifacts=patched_artifacts,
        correction_attempts=1,
        prior_outputs={},
        all_artifact_refs=[],
        stored_artifacts=[],
        completed_task_ids=[],
        plan_delta_refs=[],
        profile=None,
    )
    assert result is not None, "retest unexpectedly skipped — scenario broken"
    retests = [inputs for task_id, _, inputs in captured if task_id.startswith("retest-")]
    assert len(retests) == 1
    return {"retest_inputs": retests[0]}


_PATCHED = [
    {"name": "tests/test_api.py", "type": "source", "content": "def test_runs(): pass"},
    # *about*-the-run artifact: excluded from the re-executed workspace (#456)
    {"name": "report.md", "type": "test_report", "content": "1 failed"},
]


async def _scenario_repair_dev_with_manifest(harness, manifest_obj):
    """Dev-locus repair with a manifest: testid anchors ride both key
    variants; error-contract/model-surface evidence derives from the manifest;
    prior enforcement instructions carry."""
    return await _run_repair_scenario(
        harness,
        manifest_obj,
        envelope=_failed_envelope("development.develop", _DEV_FAILED_INPUTS, "dev"),
        result=_DEV_FAILED_RESULT,
        scaffold_enforcement_carry=["restore: backend/app.py is scaffold-owned"],
    )


async def _scenario_repair_dev_no_manifest(harness, manifest_obj):
    """No manifest → no testid keys, no manifest-derived evidence — the
    presence-gated shape."""
    return await _run_repair_scenario(
        harness,
        None,
        envelope=_failed_envelope("development.develop", _DEV_FAILED_INPUTS, "dev"),
        result=_DEV_FAILED_RESULT,
    )


async def _scenario_repair_qa_own_artifact(harness, manifest_obj):
    """Zero-extraction qa.test failure → OWN_ARTIFACT locus: qa re-produces
    its own suite; the repair target is the failed task's own contract."""
    return await _run_repair_scenario(
        harness,
        manifest_obj,
        envelope=_failed_envelope("qa.test", _QA_FAILED_INPUTS, "qa"),
        result=_QA_FAILED_RESULT,
    )


async def _scenario_retest_full(harness, manifest_obj):
    """Every presence-keyed forwarding input set: probes (#639), acceptance
    workspace (#643), DOM anchor surface (#667) all survive into the retest."""
    return await _run_retest_scenario(
        harness, failed_inputs=_QA_FAILED_INPUTS, patched_artifacts=_PATCHED
    )


async def _scenario_retest_minimal(harness, manifest_obj):
    """Presence keys absent on the failed envelope → absent on the retest."""
    minimal = {
        "artifact_contents": {"backend/routes.py": "def ok(): ..."},
        "expected_artifacts": ["tests/test_api.py"],
    }
    return await _run_retest_scenario(harness, failed_inputs=minimal, patched_artifacts=_PATCHED)


_SCENARIOS = {
    "repair_dev_with_manifest": _scenario_repair_dev_with_manifest,
    "repair_dev_no_manifest": _scenario_repair_dev_no_manifest,
    "repair_qa_own_artifact": _scenario_repair_qa_own_artifact,
    "retest_full": _scenario_retest_full,
    "retest_minimal": _scenario_retest_minimal,
}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, indent=1, default=str)


@pytest.mark.parametrize("scenario", sorted(_SCENARIOS))
async def test_correction_context_matches_golden(harness, manifest, scenario):
    value = await _SCENARIOS[scenario](harness, manifest)
    rendered = _canonical(value)

    goldens = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
    if os.environ.get("UPDATE_CONTEXT_GOLDENS"):
        goldens[scenario] = json.loads(rendered)
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(json.dumps(goldens, sort_keys=True, indent=1) + "\n")
        return

    assert scenario in goldens, (
        f"no golden for {scenario!r} — run UPDATE_CONTEXT_GOLDENS=1 pytest {__file__}"
    )
    assert rendered == _canonical(goldens[scenario]), (
        f"correction-path inputs for {scenario!r} drifted from the pre-S2 golden — if this "
        "context change is DELIBERATE, regenerate the golden in the same PR so it "
        "reads as a behavior change, never a silent refactor side effect"
    )
