"""The task-plan builder's envelopes, recorded before #1994 splits it (extraction map §4e, step 0).

``generate_task_plan`` builds a run's envelopes, one per step. The plan golden
(``test_plan_context_golden.py``) pins every envelope's inputs, but it compares them with their
keys sorted, it records nothing but the inputs, and none of its scenarios is an increment. Map
§4e moves the run's facts into ``_PlanFacts``, the acceptance families into
``_plan_task_acceptance`` and an envelope's inputs into ``_step_inputs``. Those moves touch the
order an envelope's input keys are inserted in (which is the order an agent receives them), the
envelope's other fields, and the increment facts. This records them, from
``generate_task_plan``'s return value, with ``uuid4`` counted so the lineage ids record the order
they were drawn in:
- each envelope's ids, agent, type and metadata;
- its input keys, in order, and its inputs;
- or the error a run is refused with.

Regenerate (only for a DELIBERATE behaviour change, in the PR that makes it):
    UPDATE_TASK_PLAN_GOLDENS=1 pytest tests/unit/cycles/test_task_plan_characterization.py
"""

from __future__ import annotations

import itertools
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from squadops.campaigns.change_request import (
    ProposalContext,
    apply_manifest_delta,
    stored_change_request,
    validate_proposal,
)
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    CycleError,
    Run,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.cycles.task_plan import builder_assembles, generate_task_plan
from squadops.cycles.verification_contract import VerificationContract
from squadops.stacks.scaffold import InterfaceManifest

pytestmark = [pytest.mark.domain_capabilities]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "task_plan_characterization.json"
_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = InterfaceManifest.from_yaml(
    (_REPO / "examples" / "03_group_run" / "interface_manifest.yaml").read_text(encoding="utf-8")
)
_CAMPAIGNS = _REPO / "tests" / "fixtures" / "campaigns"
_BASELINE = (_CAMPAIGNS / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text()
_REQUEST = validate_proposal(
    yaml.safe_load((_CAMPAIGNS / "reference-capacity-change-request.yaml").read_text()),
    ProposalContext(
        "prop_cap",
        1,
        "sha-accepted",
        _BASELINE,
        "fullstack_fastapi_react",
        ("backend/**", "frontend/**"),
        (),
    ),
).change_request
_STORED_REQUEST = stored_change_request(_REQUEST)
_CANDIDATE = InterfaceManifest.from_yaml(apply_manifest_delta(_BASELINE, _REQUEST.manifest_delta))
_NOW = datetime(2026, 10, 15, tzinfo=UTC)

_PROFILE = SquadProfile(
    profile_id="full",
    name="F",
    description="d",
    version=1,
    agents=tuple(
        AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
        for a, r in (
            ("max", "lead"),
            ("neo", "dev"),
            ("nat", "strat"),
            ("eve", "qa"),
            ("data", "data"),
            ("bob", "builder"),
        )
    ),
    created_at=_NOW,
)

_CONTRACT = VerificationContract.from_dict(
    {
        "contract_version": 1,
        "skeleton": {"expander": "fullstack_fastapi_react", "interface_manifest_hash": "a" * 64},
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
                }
            ],
        },
    }
)

_REJECTION_CONTEXT = {
    "rejection_reasons": ["plan_task 2 claims frozen file backend/app.py"],
    "rejected_plan_yaml": "version: 1\ntasks: []\n",
}


def _plan(criteria_refs: list[str]) -> ImplementationPlan:
    return ImplementationPlan.from_yaml(
        yaml.safe_dump(
            {
                "version": 1,
                "project_id": "p",
                "cycle_id": "cyc_char",
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
                        "criteria_refs": criteria_refs,
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


def _cycle(
    applied_defaults: dict[str, Any], overrides: dict[str, Any], *, increment: bool = False
) -> Cycle:
    if increment:
        overrides = {
            **overrides,
            "campaign_proposal": {
                "proposal_id": "prop_cap",
                "baseline_manifest": _BASELINE,
                "accepted_cycle_id": "cyc_accepted",
            },
        }
    return Cycle(
        cycle_id="cyc_char",
        project_id="proj",
        created_at=_NOW,
        created_by="s",
        prd_ref="PRD-CONTENT",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults=applied_defaults,
        execution_overrides=overrides,
        expected_artifact_types=["source"],
        campaign_id="cmp_1" if increment else None,
        kind="increment" if increment else None,
    )


def _run(workload_type: str | None) -> Run:
    return Run(
        run_id="run_abcdef123456",
        cycle_id="cyc_char",
        run_number=1,
        status="running",
        initiated_by="api",
        resolved_config_hash="confhash",
        workload_type=workload_type,
    )


def _cases() -> dict[str, dict[str, Any]]:
    """Each case is ``generate_task_plan``'s arguments."""
    return {
        "framing_rebind_with_rejection": dict(
            cycle=_cycle(
                {"plan_authoring_contributors": ["development", "qa", "strategy"]},
                {"contract_ref": "art_c", "framing_rejection_context": dict(_REJECTION_CONTEXT)},
            ),
            run=_run(WorkloadType.FRAMING),
            contract=_CONTRACT,
            interface_manifest=_MANIFEST,
        ),
        "implementation_bind": dict(
            cycle=_cycle(
                {"build_profile": "fullstack_fastapi_react", "implementation_plan": True},
                {"contract_ref": "art_c"},
            ),
            run=_run(WorkloadType.IMPLEMENTATION),
            plan=_plan(["vc-routes-endpoints"]),
            contract=_CONTRACT,
            interface_manifest=_MANIFEST,
        ),
        "implementation_author": dict(
            cycle=_cycle(
                {"build_profile": "fullstack_fastapi_react", "implementation_plan": True}, {}
            ),
            run=_run(WorkloadType.IMPLEMENTATION),
            plan=_plan([]),
        ),
        "increment_framing": dict(
            cycle=_cycle(
                {"build_profile": "fullstack_fastapi_react"},
                {"contract_ref": "art_contract"},
                increment=True,
            ),
            run=_run(WorkloadType.FRAMING),
            change_request=_STORED_REQUEST,
        ),
        "increment_implementation_with_evaluation": dict(
            cycle=_cycle(
                {"build_profile": "fullstack_fastapi_react", "implementation_plan": True},
                {},
                increment=True,
            ),
            run=_run(WorkloadType.IMPLEMENTATION),
            plan=_plan([]),
            interface_manifest=_CANDIDATE,
            change_request=_STORED_REQUEST,
        ),
        "increment_without_its_change_request": dict(
            cycle=_cycle({"build_profile": "fullstack_fastapi_react"}, {}, increment=True),
            run=_run(WorkloadType.FRAMING),
        ),
        "builder_without_a_build_profile": dict(
            cycle=_cycle({"build_tasks": True}, {}),
            run=_run(None),
        ),
    }


def _envelope_record(envelope: Any) -> dict[str, Any]:
    return {
        "task_id": envelope.task_id,
        "agent_id": envelope.agent_id,
        "task_type": envelope.task_type,
        "correlation_id": envelope.correlation_id,
        "causation_id": envelope.causation_id,
        "trace_id": envelope.trace_id,
        "span_id": envelope.span_id,
        "pulse_id": envelope.pulse_id,
        "metadata": envelope.metadata,
        "input_keys": list(envelope.inputs),
        "inputs": envelope.inputs,
    }


def _observe(case: dict[str, Any], monkeypatch) -> dict[str, Any]:
    counter = itertools.count()
    monkeypatch.setattr(
        "squadops.cycles.task_plan.uuid4", lambda: SimpleNamespace(hex=f"{next(counter):032d}")
    )
    args = {"profile": _PROFILE, **case}
    try:
        envelopes = generate_task_plan(**args)
    except CycleError as exc:
        return {"envelopes": None, "raised": f"{type(exc).__name__}: {exc}"}
    # The golden is JSON: typed checks render as their deterministic dataclass repr (as the
    # plan golden does), and tuples read back as lists.
    return json.loads(
        json.dumps(
            {"envelopes": [_envelope_record(e) for e in envelopes], "raised": None}, default=str
        )
    )


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    if os.environ.get("UPDATE_TASK_PLAN_GOLDENS") or not _GOLDEN_PATH.exists():
        return {}
    return json.loads(_GOLDEN_PATH.read_text())


@pytest.mark.parametrize("case_name", list(_cases()))
def test_the_task_plan_matches_its_golden(case_name, golden, monkeypatch):
    observed = _observe(_cases()[case_name], monkeypatch)
    if os.environ.get("UPDATE_TASK_PLAN_GOLDENS"):
        recorded = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
        recorded[case_name] = observed
        _GOLDEN_PATH.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n")
        pytest.skip("golden regenerated")
    assert case_name in golden, f"no golden for {case_name}: regenerate deliberately"
    assert observed == golden[case_name]


def test_each_task_is_caused_by_the_one_before_it(monkeypatch):
    """Bug caught: the causation chain reset per step once the loop body moves, which breaks the
    order a trace of the run is read in. The first task is caused by the plan's correlation id."""
    envelopes = _observe(_cases()["implementation_bind"], monkeypatch)["envelopes"]
    assert envelopes[0]["causation_id"] == envelopes[0]["correlation_id"]
    for before, after in itertools.pairwise(envelopes):
        assert after["causation_id"] == before["task_id"]
    assert len({e["correlation_id"] for e in envelopes}) == 1


def test_only_the_evaluation_is_handed_the_increments_change_request(monkeypatch):
    """Bug caught: the increment's facts handed to every task once they are built in one place,
    or to none. The evaluation, last, judges the criteria; the build tasks are not told them."""
    envelopes = _observe(_cases()["increment_implementation_with_evaluation"], monkeypatch)[
        "envelopes"
    ]
    *build, last = envelopes
    assert last["task_type"] == "qa.evaluate_increment"
    assert "increment_criterion_files" in last["input_keys"]
    assert not any("increment_criterion_files" in e["input_keys"] for e in build)


def test_an_increment_without_its_change_request_is_refused(monkeypatch):
    """Bug caught: the change-request requirement dropped or reordered when the run's facts move
    together. An increment framed without its request would design the accepted app again."""
    observed = _observe(_cases()["increment_without_its_change_request"], monkeypatch)
    assert observed["envelopes"] is None
    assert "has no approved change request" in observed["raised"]


@pytest.mark.parametrize(
    ("defaults", "workload", "with_builder"),
    [
        ({"build_tasks": True}, None, True),
        ({"build_tasks": True}, None, False),
        ({}, None, True),
        (
            {"implementation_plan": True, "workload_sequence": [{"type": "implementation"}]},
            WorkloadType.IMPLEMENTATION,
            True,
        ),
        (
            {"implementation_plan": True, "workload_sequence": [{"type": "implementation"}]},
            WorkloadType.IMPLEMENTATION,
            False,
        ),
        ({"workload_sequence": [{"type": "framing"}]}, WorkloadType.FRAMING, True),
    ],
    ids=[
        "legacy-build-builder",
        "legacy-build-no-builder",
        "legacy-plan-only",
        "implementation-builder",
        "implementation-no-builder",
        "framing-only",
    ],
)
def test_preflight_reads_builder_assembly_as_plan_generation_does(
    defaults, workload, with_builder, monkeypatch
):
    """#2437: create-time preflight refuses exactly the cycles whose plan the #392 check would
    refuse, by asking ``builder_assembles``. Entered at ``generate_task_plan`` with no
    ``build_profile``. Bug caught: the two readings drifting, so preflight refuses a cycle that
    would have run, or accepts one that fails after framing."""
    import dataclasses

    profile = (
        _PROFILE
        if with_builder
        else dataclasses.replace(
            _PROFILE, agents=tuple(a for a in _PROFILE.agents if "builder" not in a.serves_roles)
        )
    )
    cycle = _cycle(defaults, {})
    case: dict[str, Any] = {"cycle": cycle, "run": _run(workload)}
    if workload == WorkloadType.IMPLEMENTATION:
        case["plan"] = _plan([])
    observed = _observe({**case, "profile": profile}, monkeypatch)
    refused = observed["raised"] is not None and "build_profile is required" in observed["raised"]

    assert builder_assembles(profile, cycle.resolved_config()) is refused


@pytest.mark.parametrize(
    ("defaults", "workload"),
    [
        ({"build_tasks": True}, None),
        (
            {"implementation_plan": True, "workload_sequence": [{"type": "implementation"}]},
            WorkloadType.IMPLEMENTATION,
        ),
    ],
    ids=["legacy-build", "implementation"],
)
def test_a_source_backed_cycle_never_assembles_with_the_builder(defaults, workload, monkeypatch):
    """SIP-0112 E.4.3: an external product builds itself, by its own declared commands.
    Entered at ``generate_task_plan`` on a squad serving the builder role. Bugs caught: the
    builder dispatched on an external product, and refused there for a ``build_profile`` the
    product can't have; preflight and the plan reading it differently."""
    import dataclasses

    from squadops.projects.source_context import parse_source_context
    from tests.fixtures.shared_contract.repository import recorded

    context = parse_source_context(recorded("project_source_context", "valid"))
    cycle = dataclasses.replace(_cycle(defaults, {}), source_context=context)
    case: dict[str, Any] = {"cycle": cycle, "run": _run(workload), "profile": _PROFILE}
    if workload == WorkloadType.IMPLEMENTATION:
        case["plan"] = _plan([])

    observed = _observe(case, monkeypatch)

    assert observed["raised"] is None
    assert not [e for e in observed["envelopes"] if e["task_type"].startswith("builder.")]
    assert builder_assembles(_PROFILE, cycle.resolved_config(), source_backed=True) is False
    assert builder_assembles(_PROFILE, cycle.resolved_config()) is True
