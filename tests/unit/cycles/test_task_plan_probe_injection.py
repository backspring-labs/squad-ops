"""Bind-mode probe injection into qa.test task inputs (SIP-0098 phase 98.5).

The deferred half of 98.4: for probe evidence to land in a *live* cycle (not just the
CI gate), ``generate_task_plan`` must carry the seeded contract's ``behavioral.probes``
onto the qa.test envelope — serialized ``Probe`` dicts, since envelope inputs cross the
A2A wire as JSON. The qa handler reconstructs and executes them (§6.4).

Mirrors the 98.3 criteria-index injection tests in
``tests/unit/capabilities/test_bind_criteria_proposer.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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

_PROBE_CREATE = {
    "id": "vc-probe-create",
    "subject": "backend",
    "request": {"method": "POST", "path": "/items", "json": {"title": "x"}},
    "expect": {"status": 200, "json_has": ["id"]},
}
_PROBE_DUP = {
    "id": "vc-probe-dup",
    "subject": "backend",
    "request": {"method": "POST", "path": "/items", "json": {"title": "x"}},
    "expect": {"status": 409, "error_code": "duplicate_item"},
}


def _contract(*, with_probes: bool = True) -> VerificationContract:
    return VerificationContract.from_dict(
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
                "probes": [_PROBE_CREATE, _PROBE_DUP] if with_probes else [],
            },
        }
    )


def _implementation_setup() -> tuple[Cycle, Run, SquadProfile]:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    cycle = Cycle(
        cycle_id="cy",
        project_id="p",
        created_at=now,
        created_by="s",
        prd_ref="prd",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={},
        execution_overrides={"contract_ref": "art_c"},
        expected_artifact_types=["source"],
    )
    run = Run(
        run_id="run_abcdef123456",
        cycle_id="cy",
        run_number=1,
        status="running",
        initiated_by="api",
        resolved_config_hash="h",
        workload_type=WorkloadType.IMPLEMENTATION,
    )
    profile = SquadProfile(
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
        created_at=now,
    )
    return cycle, run, profile


def test_bind_mode_injects_serialized_probes_into_qa_test_only():
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=_contract())

    qa_envs = [e for e in envs if e.task_type == "qa.test"]
    assert qa_envs, "implementation workload must contain a qa.test step"
    # Exact wire shape: Probe.to_dict round-trip material for the qa handler.
    assert qa_envs[0].inputs["contract_probes"] == [_PROBE_CREATE, _PROBE_DUP]
    # No other task type receives probes — they execute only where the app boots.
    for env in envs:
        if env.task_type != "qa.test":
            assert "contract_probes" not in env.inputs


def test_author_mode_injects_no_probes():
    # contract-less cycles must stay byte-identical (SIP-0098 §6.6 / 98.3 regression bar)
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=None)
    assert all("contract_probes" not in e.inputs for e in envs)


def test_probe_less_contract_injects_no_key():
    # bind mode with an empty probes section must not plant an empty list — the qa
    # handler keys on the input's presence, and an empty key would imply a contract
    # promised probes it does not have.
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=_contract(with_probes=False))
    assert all("contract_probes" not in e.inputs for e in envs)
