"""#663 S3 golden harness — plan-time envelope equivalence.

Pins the EXACT envelope inputs ``generate_task_plan`` produces for the
framing and implementation sequences, as canonical JSON goldens captured
BEFORE the S3 extraction (the plan-time membership tables —
which task types receive bind-mode contract inputs and re-roll rejection
context — move onto the context-assembly registry's contracts). Same
contract as the S1/S2 harnesses: every #663 slice keeps these
byte-identical — a deliberate context change must regenerate the golden in
the same PR and read as a behavior change, never a silent refactor side
effect.

Envelope inputs only (lineage uuids are envelope fields, outside the
capture); ``TypedCheck`` instances render via their deterministic dataclass
repr (``default=str``).

Regenerate: UPDATE_CONTEXT_GOLDENS=1 pytest tests/unit/cycles/test_plan_context_golden.py
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.cycles.task_plan import generate_task_plan
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_capabilities]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "plan_context.json"
_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)
_NOW = datetime(2026, 7, 18, tzinfo=UTC)

_CONTRACT = VerificationContract.from_dict(
    {
        "contract_version": 1,
        "skeleton": {
            "expander": "fullstack_fastapi_react",
            "interface_manifest_hash": "a" * 64,
        },
        "capabilities": ["python"],
        "frozen": [],
        "fill_files": {
            "backend/routes.py": {
                "interface": [
                    {
                        "check": "endpoint_defined",
                        "id": "vc-routes-endpoints",
                        "methods_paths": ["POST /items"],
                    }
                ],
                "implementation": [],
            }
        },
        "behavioral": {
            "build": [],
            "suite": {"checks": [], "coverage_expectations": []},
            "probes": [
                {
                    "id": "vc-probe-create",
                    "subject": "backend",
                    "request": {"method": "POST", "path": "/items", "json": {"title": "x"}},
                    "expect": {"status": 201, "json_has": ["id"]},
                },
                {
                    "id": "vc-probe-dup",
                    "subject": "backend",
                    "request": {"method": "POST", "path": "/items", "json": {"title": "x"}},
                    "expect": {"status": 409, "error_code": "duplicate_item"},
                },
            ],
        },
    }
)

_REJECTION_CONTEXT = {
    "rejection_reasons": [
        "plan_task 2 claims frozen file backend/app.py",
        "qa.test task binds no runnable suite artifact",
    ],
    "rejected_plan_yaml": "version: 1\ntasks: []\n",
}

_PLAN = ImplementationPlan.from_yaml(
    yaml.safe_dump(
        {
            "version": 1,
            "project_id": "p",
            "cycle_id": "cyc_golden",
            "prd_hash": "h",
            "tasks": [
                {
                    "task_index": 0,
                    "task_type": "development.develop",
                    "role": "dev",
                    "focus": "routes",
                    "description": "implement the routes fill slot",
                    "expected_artifacts": ["backend/routes.py"],
                    "acceptance_criteria": [],
                    "depends_on": [],
                    "criteria_refs": [],
                },
                {
                    "task_index": 1,
                    "task_type": "qa.test",
                    "role": "qa",
                    "focus": "suite",
                    "description": "author the API suite",
                    "expected_artifacts": ["backend/tests/test_items.py"],
                    "acceptance_criteria": [],
                    "depends_on": [0],
                    "criteria_refs": [],
                },
            ],
            "summary": {"total_dev_tasks": 1, "total_qa_tasks": 1, "total_tasks": 2},
        }
    )
)


def _cycle(applied_defaults: dict, execution_overrides: dict) -> Cycle:
    return Cycle(
        cycle_id="cyc_golden",
        project_id="proj",
        created_at=_NOW,
        created_by="s",
        prd_ref="PRD-CONTENT",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=applied_defaults,
        execution_overrides=execution_overrides,
        expected_artifact_types=["source"],
    )


def _run(workload_type: str) -> Run:
    return Run(
        run_id="run_abcdef123456",
        cycle_id="cyc_golden",
        run_number=1,
        status="running",
        initiated_by="api",
        resolved_config_hash="confhash",
        workload_type=workload_type,
    )


_PROFILE = SquadProfile(
    profile_id="full",
    name="F",
    description="d",
    version=1,
    agents=[
        AgentProfileEntry(agent_id="max", role="lead", model="m", enabled=True),
        AgentProfileEntry(agent_id="neo", role="dev", model="m", enabled=True),
        AgentProfileEntry(agent_id="nat", role="strat", model="m", enabled=True),
        AgentProfileEntry(agent_id="eve", role="qa", model="m", enabled=True),
        AgentProfileEntry(agent_id="data", role="data", model="m", enabled=True),
    ],
    created_at=_NOW,
)


@pytest.fixture(scope="module")
def manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _scenario_framing_bind_with_rejection(manifest_obj):
    """A #522 framing re-roll in bind mode: proposers get the criteria/frozen
    indexes (98.3/pf-42), all four authoring types get the prior rejection
    (#669), the merger and sign-off get neither."""
    cycle = _cycle(
        {"plan_authoring_contributors": ["development", "qa", "strategy"]},
        {"contract_ref": "art_c", "framing_rejection_context": dict(_REJECTION_CONTEXT)},
    )
    return generate_task_plan(
        cycle,
        _run(WorkloadType.FRAMING),
        _PROFILE,
        plan=None,
        contract=_CONTRACT,
        interface_manifest=manifest_obj,
    )


def _scenario_implementation_bind(manifest_obj):
    """Bind-mode implementation: qa.test carries the contract's behavioral
    surface (probes #98.5, endpoint owners #688, pinned statuses #629, DOM
    anchors #659); dev carries contract-resolved criteria."""
    cycle = _cycle({"implementation_plan": True}, {"contract_ref": "art_c"})
    return generate_task_plan(
        cycle,
        _run(WorkloadType.IMPLEMENTATION),
        _PROFILE,
        plan=_PLAN,
        contract=_CONTRACT,
        interface_manifest=manifest_obj,
    )


def _scenario_implementation_author(manifest_obj):
    """Author mode (no contract): no bind keys anywhere — the SIP-0098 §6.6
    byte-identical guarantee for contract-less cycles."""
    cycle = _cycle({"implementation_plan": True}, {})
    return generate_task_plan(
        cycle,
        _run(WorkloadType.IMPLEMENTATION),
        _PROFILE,
        plan=_PLAN,
        contract=None,
        interface_manifest=None,
    )


_SCENARIOS = {
    "framing_bind_with_rejection": _scenario_framing_bind_with_rejection,
    "implementation_bind": _scenario_implementation_bind,
    "implementation_author": _scenario_implementation_author,
}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, indent=1, default=str)


@pytest.mark.parametrize("scenario", sorted(_SCENARIOS))
def test_plan_envelope_inputs_match_golden(manifest, scenario):
    envelopes = _SCENARIOS[scenario](manifest)
    value = {f"{i:02d}:{env.task_type}": env.inputs for i, env in enumerate(envelopes)}
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
        f"plan-time envelope inputs for {scenario!r} drifted from the pre-S3 golden — if "
        "this context change is DELIBERATE, regenerate the golden in the same PR so it "
        "reads as a behavior change, never a silent refactor side effect"
    )
