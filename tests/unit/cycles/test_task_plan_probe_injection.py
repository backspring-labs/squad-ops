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


# ---------------------------------------------------------------------------
# #629: behavior-expectation injection (pf-54)
# ---------------------------------------------------------------------------


def test_bind_mode_injects_behavior_expectations_into_qa_test_only():
    # pf-54: five authored suite versions asserted 200-on-create against a pinned
    # 201 — the pins never reached suite AUTHORING. Exact rendered lines, probe
    # order preserved, error_code carried.
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=_contract())

    qa_envs = [e for e in envs if e.task_type == "qa.test"]
    assert qa_envs, "implementation workload must contain a qa.test step"
    assert qa_envs[0].inputs["api_behavior_contract"] == [
        "POST /items → HTTP 200",
        "POST /items (rejection case) → HTTP 409 (error_code: duplicate_item)",
    ]
    for env in envs:
        if env.task_type != "qa.test":
            assert "api_behavior_contract" not in env.inputs


def test_author_mode_injects_no_behavior_expectations():
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=None)
    assert all("api_behavior_contract" not in e.inputs for e in envs)


def test_behaviorless_contract_injects_no_behavior_key():
    # No probes and no coverage_expectations → no key; the handler keys on
    # presence, and an empty block would render an authoritative header over
    # nothing.
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=_contract(with_probes=False))
    assert all("api_behavior_contract" not in e.inputs for e in envs)


# ---------------------------------------------------------------------------
# #509: deterministic criterion binding
# ---------------------------------------------------------------------------


def _plan_with_refs(refs):
    import yaml as _yaml

    from squadops.cycles.implementation_plan import ImplementationPlan

    return ImplementationPlan.from_yaml(
        _yaml.safe_dump(
            {
                "version": 1,
                "project_id": "p",
                "cycle_id": "cy",
                "prd_hash": "h",
                "tasks": [
                    {
                        "task_index": 0,
                        "task_type": "development.develop",
                        "role": "dev",
                        "focus": "routes",
                        "description": "d",
                        "expected_artifacts": ["backend/routes.py"],
                        "acceptance_criteria": [],
                        "depends_on": [],
                        "criteria_refs": refs,
                    },
                    {
                        "task_index": 1,
                        "task_type": "qa.test",
                        "role": "qa",
                        "focus": "suite",
                        "description": "d",
                        "expected_artifacts": ["backend/tests/test_runs.py"],
                        "acceptance_criteria": [],
                        "depends_on": [],
                        "criteria_refs": [],
                    },
                ],
                "summary": {"total_dev_tasks": 1, "total_qa_tasks": 1, "total_tasks": 2},
            }
        )
    )


def test_under_bound_plan_gains_the_missing_refs_and_passes_validation():
    # The pf-54 run-2 killer: one missing ref auto-rejected the whole plan and
    # burned a framing re-roll. Binding is now derived, not transcribed.
    contract = _contract()
    plan = _plan_with_refs([])
    bound, notes = plan.with_contract_criteria_bound(contract)
    assert bound.tasks[0].criteria_refs == ["vc-routes-endpoints"]
    assert notes == ["Task 0 (routes): auto-bound ['vc-routes-endpoints']"]
    assert bound.validate_criteria_refs(contract) == []
    # Non-covered artifacts (the qa namespace) gain nothing.
    assert bound.tasks[1].criteria_refs == []


def test_fully_bound_plan_is_unchanged_and_binding_is_idempotent():
    contract = _contract()
    plan = _plan_with_refs(["vc-routes-endpoints"])
    bound, notes = plan.with_contract_criteria_bound(contract)
    assert notes == []
    assert bound is plan
    again, notes2 = bound.with_contract_criteria_bound(contract)
    assert notes2 == []
    assert again.tasks[0].criteria_refs == ["vc-routes-endpoints"]


def test_authored_ref_order_is_preserved_missing_appended():
    # Authors may bind extra-file refs (e.g. a qa task binding routes criteria);
    # binding appends what's missing, never reorders what was written.
    contract = _contract()
    plan = _plan_with_refs(["vc-probe-create"])  # resolvable id, not the file's own
    bound, _ = plan.with_contract_criteria_bound(contract)
    assert bound.tasks[0].criteria_refs == ["vc-probe-create", "vc-routes-endpoints"]


def test_generate_task_plan_binds_before_resolving_refs():
    # End-to-end: an under-bound plan still dispatches routes tasks with the
    # contract's typed checks resolved into acceptance.
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=_plan_with_refs([]), contract=_contract())
    dev_envs = [e for e in envs if e.task_type == "development.develop"]
    assert dev_envs, "plan-derived dev step expected"
    from squadops.cycles.implementation_plan import TypedCheck

    checks = [
        c
        for c in dev_envs[0].inputs.get("acceptance_criteria", [])
        if isinstance(c, TypedCheck) and c.check == "endpoint_defined"
    ]
    assert checks, "contract-resolved endpoint_defined must reach the envelope"
    assert checks[0].id == "vc-routes-endpoints"


# ---------------------------------------------------------------------------
# #659: DOM anchor surface injection
# ---------------------------------------------------------------------------


def _testid_manifest():
    from pathlib import Path

    from squadops.capabilities.scaffold import InterfaceManifest

    path = (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "03_group_run"
        / "interface_manifest.yaml"
    )
    return InterfaceManifest.from_yaml(path.read_text(encoding="utf-8"))


def test_bind_mode_injects_dom_testid_surface_into_qa_test_only():
    """Bug caught (fay-6/fay-12): the anchor inventory reaching only one prompt
    side (or neither) re-opens the DOM war — suites invent render details and
    every correction round chases them."""
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(
        cycle, run, profile, plan=None, contract=_contract(), interface_manifest=_testid_manifest()
    )

    qa_envs = [e for e in envs if e.task_type == "qa.test"]
    assert qa_envs, "implementation workload must contain a qa.test step"
    lines = qa_envs[0].inputs["dom_testid_surface"]
    assert any("`RunsListView`" in line and "`runs-list`" in line for line in lines)
    for env in envs:
        if env.task_type != "qa.test":
            assert "dom_testid_surface" not in env.inputs


def test_manifest_without_testids_injects_no_dom_key():
    """The handler keys on presence — an empty inventory must not render an
    authoritative header over nothing."""
    import dataclasses

    m = _testid_manifest()
    bare_routes = tuple(dataclasses.replace(r, testids=()) for r in m.frontend.routes)
    bare = dataclasses.replace(m, frontend=dataclasses.replace(m.frontend, routes=bare_routes))

    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(
        cycle, run, profile, plan=None, contract=_contract(), interface_manifest=bare
    )
    assert all("dom_testid_surface" not in e.inputs for e in envs)


# ---------------------------------------------------------------------------
# #688: endpoint → fill-slot ownership injection
# ---------------------------------------------------------------------------


def test_bind_mode_injects_endpoint_owners_into_qa_test_only():
    """Bug caught (shk-2): without this key the correction runner has no way to name
    the fill slot behind a failing probe, and the repair chases drift-named files
    while the defect site sits untargeted for the whole correction budget."""
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=_contract())

    qa_envs = [e for e in envs if e.task_type == "qa.test"]
    assert qa_envs, "implementation workload must contain a qa.test step"
    assert qa_envs[0].inputs["contract_endpoint_owners"] == {"POST /items": "backend/routes.py"}
    for env in envs:
        if env.task_type != "qa.test":
            assert "contract_endpoint_owners" not in env.inputs


def test_author_mode_injects_no_endpoint_owners():
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=None)
    assert all("contract_endpoint_owners" not in e.inputs for e in envs)


def test_probe_less_contract_injects_no_endpoint_owners():
    # The map is only actionable alongside probe evidence; injecting it without
    # probes would plant a key the correction path can never key on.
    cycle, run, profile = _implementation_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=_contract(with_probes=False))
    assert all("contract_endpoint_owners" not in e.inputs for e in envs)
