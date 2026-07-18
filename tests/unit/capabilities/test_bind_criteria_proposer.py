"""Bind-mode proposer chain (SIP-0098 phase 98.3, slice D).

In bind mode the dev/qa proposers receive the contract's criteria index and are told
to *bind* (list criteria_refs) rather than author covered-file criteria; the proposal
model + deterministic merger carry those refs onto the merged implementation plan.
Data-driven: no seeded contract -> no index injected -> today's author-mode prompt and
byte-identical merged plan.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.planning_tasks import (
    DevelopmentProposePlanTasksHandler,
    QaProposePlanTasksHandler,
    StrategyProposePlanGuidanceHandler,
)
from squadops.cycles.proposed_role_tasks import ProposedRoleTasks, ProposedTask
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_capabilities]


def _contract() -> VerificationContract:
    return VerificationContract.from_dict(
        {
            "contract_version": 1,
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "a" * 64,
            },
            "capabilities": ["python", "node"],
            "frozen": [],
            "fill_files": {
                "backend/routes.py": {
                    "interface": [
                        {
                            "check": "endpoint_defined",
                            "id": "vc-routes-endpoints",
                            "methods_paths": ["GET /x"],
                        },
                        {
                            "check": "import_present",
                            "id": "vc-routes-apierror",
                            "module": ".errors",
                            "symbol": "ApiError",
                        },
                    ],
                    "implementation": [],
                },
                "frontend/src/views/ListView.jsx": {"interface": [], "implementation": []},
            },
            "behavioral": {
                "build": [],
                "suite": {"checks": [], "coverage_expectations": []},
                "probes": [],
            },
        }
    )


# --------------------------------------------------------------------------- #
# criteria_index_lines — the data the proposer prompt renders
# --------------------------------------------------------------------------- #


def test_criteria_index_lines_lists_ids_for_covered_files():
    lines = _contract().criteria_index_lines()
    assert lines == [
        "- backend/routes.py: bind vc-routes-endpoints (endpoint_defined), "
        "vc-routes-apierror (import_present)",
        "- frontend/src/views/ListView.jsx: contract-owned (no per-file typed criteria); "
        "do not author your own for this file",
    ]


# --------------------------------------------------------------------------- #
# _bind_criteria_section — dev/qa only, bind-mode only
# --------------------------------------------------------------------------- #


async def test_bind_section_rendered_for_dev_in_bind_mode():
    handler = DevelopmentProposePlanTasksHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="BIND INSTRUCTION")

    out = await handler._bind_criteria_section(
        renderer, {"contract_criteria_index": "- backend/routes.py: bind x"}
    )

    assert out == "BIND INSTRUCTION"
    renderer.render.assert_awaited_once_with(
        "request.plan_bind_criteria_appendix", {"criteria_index": "- backend/routes.py: bind x"}
    )


async def test_bind_section_rendered_for_qa_in_bind_mode():
    handler = QaProposePlanTasksHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="BIND INSTRUCTION")
    out = await handler._bind_criteria_section(renderer, {"contract_criteria_index": "- x"})
    assert out == "BIND INSTRUCTION"


async def test_bind_section_empty_in_author_mode():
    # no contract seeded -> executor injected no index -> today's author prompt exactly
    handler = DevelopmentProposePlanTasksHandler()
    renderer = AsyncMock()
    out = await handler._bind_criteria_section(renderer, {})
    assert out == ""
    renderer.render.assert_not_awaited()


async def test_bind_section_empty_for_strategy_proposer():
    # strategy proposes guidance, not build tasks — it binds no fill-file criteria
    handler = StrategyProposePlanGuidanceHandler()
    renderer = AsyncMock()
    out = await handler._bind_criteria_section(renderer, {"contract_criteria_index": "- x"})
    assert out == ""
    renderer.render.assert_not_awaited()


# --------------------------------------------------------------------------- #
# ProposedTask.criteria_refs — parse
# --------------------------------------------------------------------------- #


def _proposal_yaml(refs_line: str) -> str:
    return f"""
version: 1
proposing_role: development
proposal_id: prop-1
source_brief_id: brief-1
scope_statement: propose the routes task
tasks:
  - task_type: development.develop
    role: dev
    focus: routes
    description: fill routes
    expected_artifacts: [backend/routes.py]
    {refs_line}
    acceptance_criteria: []
    depends_on_focus: []
"""


def test_proposed_task_parses_criteria_refs():
    proposal = ProposedRoleTasks.from_yaml(
        _proposal_yaml("criteria_refs: [vc-routes-endpoints, vc-routes-apierror]")
    )
    assert proposal.tasks[0].criteria_refs == ["vc-routes-endpoints", "vc-routes-apierror"]


def test_proposed_task_criteria_refs_default_empty():
    proposal = ProposedRoleTasks.from_yaml(_proposal_yaml("depends_on_focus: []"))
    assert proposal.tasks[0].criteria_refs == []


def test_proposed_task_rejects_non_string_refs():
    with pytest.raises(ValueError, match="criteria_refs must be a list of strings"):
        ProposedRoleTasks.from_yaml(_proposal_yaml("criteria_refs: [1, 2]"))


# --------------------------------------------------------------------------- #
# merger carries criteria_refs onto the PlanTask + serialized plan
# --------------------------------------------------------------------------- #


def test_merger_carries_criteria_refs_to_plan_task():
    from squadops.capabilities.handlers._plan_merger import (
        _build_canonical_pair,
        _plan_task_to_dict,
    )

    ptask = ProposedTask(
        task_type="development.develop",
        role="dev",
        focus="routes",
        description="fill",
        expected_artifacts=["backend/routes.py"],
        criteria_refs=["vc-routes-endpoints", "vc-routes-apierror"],
    )
    plan_task, _, _ = _build_canonical_pair(ptask, proposing_role="development")
    assert plan_task.criteria_refs == ["vc-routes-endpoints", "vc-routes-apierror"]
    assert _plan_task_to_dict(plan_task)["criteria_refs"] == [
        "vc-routes-endpoints",
        "vc-routes-apierror",
    ]


def test_merger_omits_criteria_refs_when_absent():
    # author-mode task -> serialized dict has no criteria_refs key (byte-identical to today)
    from squadops.capabilities.handlers._plan_merger import (
        _build_canonical_pair,
        _plan_task_to_dict,
    )

    ptask = ProposedTask(
        task_type="development.develop",
        role="dev",
        focus="f",
        description="d",
        expected_artifacts=["a.py"],
    )
    plan_task, _, _ = _build_canonical_pair(ptask, proposing_role="development")
    assert plan_task.criteria_refs == []
    assert "criteria_refs" not in _plan_task_to_dict(plan_task)


# --------------------------------------------------------------------------- #
# generate_task_plan injects the criteria index into dev/qa proposer inputs
# --------------------------------------------------------------------------- #


def _framing_setup():
    from datetime import UTC, datetime

    from squadops.cycles.models import (
        AgentProfileEntry,
        Cycle,
        Run,
        SquadProfile,
        TaskFlowPolicy,
        WorkloadType,
    )

    now = datetime(2026, 3, 31, tzinfo=UTC)
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
        applied_defaults={"plan_authoring_contributors": ["development", "qa", "strategy"]},
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
        workload_type=WorkloadType.FRAMING,
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


def test_bind_mode_injects_index_into_dev_and_qa_proposers_only():
    from squadops.cycles.task_plan import generate_task_plan

    cycle, run, profile = _framing_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=_contract())
    injected = {
        e.task_type: ("contract_criteria_index" in e.inputs)
        for e in envs
        if "propose_plan" in e.task_type
    }
    assert injected == {
        "development.propose_plan_tasks": True,
        "qa.propose_plan_tasks": True,
        "strategy.propose_plan_guidance": False,  # strategy proposes guidance, not tasks
    }
    dev_env = next(e for e in envs if e.task_type == "development.propose_plan_tasks")
    assert (
        "backend/routes.py: bind vc-routes-endpoints" in dev_env.inputs["contract_criteria_index"]
    )


def test_author_mode_injects_no_index():
    from squadops.cycles.task_plan import generate_task_plan

    cycle, run, profile = _framing_setup()
    envs = generate_task_plan(cycle, run, profile, plan=None, contract=None)
    assert all("contract_criteria_index" not in e.inputs for e in envs)
