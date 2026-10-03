"""An increment's plan covers only its approved change (SIP-0109 §7.3; #1705 step d).

The reference capacity proposal's footprint, derived as its own was: ``backend/{errors,models,
routes}.py``, ``RunDetailView.jsx`` and the stack's test namespaces. ``RunListView.jsx`` is a
fill slot the change does not touch — the accepted implementation keeps it.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from squadops.campaigns.change_request import (
    ProposalContext,
    apply_manifest_delta,
    stored_change_request,
    validate_proposal,
)
from squadops.cycles.models import ArtifactRef, Cycle, Run, TaskFlowPolicy

NOW = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)
_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "campaigns"
BASELINE = (_FIXTURES / "baseline-cyc_7a4b7a6fbf0e-interface_manifest.yaml").read_text()
_REQUEST = validate_proposal(
    yaml.safe_load((_FIXTURES / "reference-capacity-change-request.yaml").read_text()),
    ProposalContext(
        "prop_cap",
        1,
        "sha-accepted",
        BASELINE,
        "fullstack_fastapi_react",
        ("backend/**", "frontend/**"),
        (),
    ),
).change_request
CANDIDATE = apply_manifest_delta(BASELINE, _REQUEST.manifest_delta)
STORED_REQUEST = stored_change_request(_REQUEST)


def _plan(*artifacts: str) -> str:
    return yaml.safe_dump(
        {
            "version": 1,
            "project_id": "group_run",
            "cycle_id": "cyc_inc",
            "prd_hash": "abc",
            "summary": {
                "total_dev_tasks": len(artifacts),
                "total_qa_tasks": 0,
                "total_tasks": len(artifacts),
            },
            "tasks": [
                {
                    "task_index": i,
                    "task_type": "development.develop",
                    "role": "dev",
                    "focus": f"fill {a}",
                    "description": "fill the slot",
                    "expected_artifacts": [a],
                    "acceptance_criteria": [],
                }
                for i, a in enumerate(artifacts)
            ],
        }
    )


class _Vault:
    def __init__(self, plan: str) -> None:
        self.stored = {
            "art_plan": (
                ArtifactRef(
                    "art_plan",
                    "group_run",
                    "control_implementation_plan",
                    "implementation_plan.yaml",
                    "h",
                    1,
                    "text/yaml",
                    NOW,
                    cycle_id="cyc_inc",
                    run_id="run_f",
                ),
                plan.encode(),
            ),
            "art_seed": (
                ArtifactRef(
                    "art_seed",
                    "group_run",
                    "interface_manifest",
                    "interface_manifest.yaml",
                    "h",
                    1,
                    "text/yaml",
                    NOW,
                    cycle_id="cyc_inc",
                    run_id="run_p",
                ),
                CANDIDATE.encode(),
            ),
        }

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def list_artifacts(self, **_):
        return [r for r, _ in self.stored.values()]


def _cycle(increment: bool) -> Cycle:
    overrides = {"plan_artifact_refs": ["art_seed"]}
    if increment:
        overrides["campaign_proposal"] = {"proposal_id": "prop_cap", "baseline_manifest": BASELINE}
    return Cycle(
        cycle_id="cyc_inc",
        project_id="group_run",
        created_at=NOW,
        created_by="launcher",
        prd_ref=None,
        squad_profile_id="full-38",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"implementation_plan": True, "build_profile": "fullstack_fastapi_react"},
        execution_overrides=overrides,
        campaign_id="cmp_1" if increment else None,
        kind="increment" if increment else None,
    )


async def _gate_errors(plan: str, increment: bool = True) -> list[str]:
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=_Vault(plan),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
    )
    executor._cycle_event_bus = MagicMock()
    run = Run(
        "run_f",
        "cyc_inc",
        2,
        "completed",
        "system",
        "cfg",
        workload_type="framing",
        artifact_refs=("art_plan",),
    )
    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, _cycle(increment), "progress_plan_review"
    )
    return [e for e in errors if "approved change does not touch" in e]


async def test_an_increment_plan_reaching_outside_its_change_is_rejected_at_the_gate():
    """§7.3, the gate the framing re-roll keys on (#522). Bug caught: an increment's plan
    rewriting a view the approved change never touched — accepted work rebuilt unruled."""
    [error] = await _gate_errors(
        _plan("frontend/src/views/RunDetailView.jsx", "frontend/src/views/RunListView.jsx")
    )
    assert "'frontend/src/views/RunListView.jsx'" in error
    assert "backend/routes.py" in error  # the footprint is named, so the re-roll can comply


@pytest.mark.parametrize(
    ("artifacts", "increment"),
    [
        (("backend/routes.py", "frontend/src/views/RunDetailView.jsx"), True),
        (("frontend/src/views/RunListView.jsx",), False),  # not an increment: not checked
    ],
    ids=["inside-the-footprint", "an-ordinary-cycle"],
)
async def test_a_plan_inside_its_footprint_or_outside_a_campaign_passes(artifacts, increment):
    assert await _gate_errors(_plan(*artifacts), increment) == []


async def test_the_plan_author_is_shown_the_footprint_before_the_gate_refuses():
    """Teach, then enforce (#686). Bug caught: an author refused for a rule it was never
    shown — a framing re-roll spent on a footprint nobody told it about."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.campaigns.increment_tree import increment_footprint
    from squadops.capabilities.handlers._plan_authoring import contract_surface_sections
    from squadops.capabilities.scaffold import InterfaceManifest
    from squadops.cycles.task_plan import inject_contract_inputs
    from squadops.prompts.renderer import RequestTemplateRenderer

    footprint = increment_footprint(
        _cycle(True).resolved_config(), InterfaceManifest.from_yaml(CANDIDATE)
    )
    inputs: dict = {}
    contract = MagicMock()
    contract.criteria_index_lines.return_value = ["- C1"]
    contract.behavioral.probes = ()
    inject_contract_inputs(
        inputs,
        contract,
        "governance.merge_plan",
        InterfaceManifest.from_yaml(CANDIDATE),
        footprint,
    )

    text = await contract_surface_sections(
        RequestTemplateRenderer(create_prompt_asset_source("filesystem")), inputs
    )

    assert "This is an increment: plan only the approved change" in text
    assert "- `backend/routes.py`" in text
    assert "RunListView.jsx" not in inputs["increment_footprint_index"]


def test_an_increment_framing_plan_carries_its_footprint_to_the_plan_author():
    """Wiring, entered at ``generate_task_plan`` — what a framing run's provisioning calls.
    Bug caught: the footprint derived nowhere on the live path, so the appendix a test
    renders by hand never reaches an author."""
    from squadops.capabilities.scaffold import InterfaceManifest
    from squadops.cycles.models import AgentProfileEntry, SquadProfile
    from squadops.cycles.task_plan import generate_task_plan

    profile = SquadProfile(
        profile_id="full",
        name="full",
        description="",
        version=1,
        created_at=NOW,
        agents=tuple(
            AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
            for a, r in (
                ("nat", "strat"),
                ("neo", "dev"),
                ("eve", "qa"),
                ("data", "data"),
                ("max", "lead"),
            )
        ),
    )
    contract = MagicMock()
    contract.criteria_index_lines.return_value = ["- C1"]
    contract.behavioral.probes = ()
    run = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")

    # As the approval forwards them (#1840): the candidate manifest's contract and the change
    # request ride the framing run's overrides.
    cycle = _cycle(True)
    cycle = dataclasses.replace(
        cycle, execution_overrides={**cycle.execution_overrides, "contract_ref": "art_contract"}
    )
    plan = generate_task_plan(
        cycle,
        run,
        profile,
        contract=contract,
        interface_manifest=InterfaceManifest.from_yaml(CANDIDATE),
        change_request=STORED_REQUEST,
    )

    [merge] = [e for e in plan if e.task_type == "governance.merge_plan"]
    assert "- `backend/routes.py`" in merge.inputs["increment_footprint_index"]
    assert "RunListView.jsx" not in merge.inputs["increment_footprint_index"]


async def test_the_footprint_names_apart_the_files_the_scaffold_regenerates():
    """#1868, entered at ``generate_task_plan`` with the real contract the candidate manifest
    derives — the set the gate refuses a claim on. Shakeout 2's first framing claimed
    ``backend/models.py`` and ``backend/errors.py`` because the footprint told it to plan tasks
    for them, while the frozen rule forbade it. Bugs caught: a frozen file taught as one to plan
    for; or dropped from what the author is shown altogether, so it is not told they change."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers._plan_authoring import contract_surface_sections
    from squadops.capabilities.scaffold import InterfaceManifest
    from squadops.capabilities.scaffold_contract import emit_contract_yaml
    from squadops.cycles.models import AgentProfileEntry, SquadProfile
    from squadops.cycles.task_plan import generate_task_plan
    from squadops.cycles.verification_contract import VerificationContract
    from squadops.prompts.renderer import RequestTemplateRenderer

    candidate = InterfaceManifest.from_yaml(CANDIDATE)
    contract = VerificationContract.from_yaml(emit_contract_yaml(candidate))
    frozen = {ff.path for ff in contract.frozen_files}
    profile = SquadProfile(
        profile_id="full",
        name="full",
        description="",
        version=1,
        created_at=NOW,
        agents=tuple(
            AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
            for a, r in (
                ("nat", "strat"),
                ("neo", "dev"),
                ("eve", "qa"),
                ("data", "data"),
                ("max", "lead"),
            )
        ),
    )
    cycle = _cycle(True)
    cycle = dataclasses.replace(
        cycle, execution_overrides={**cycle.execution_overrides, "contract_ref": "art_contract"}
    )
    run = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")

    plan = generate_task_plan(
        cycle,
        run,
        profile,
        contract=contract,
        interface_manifest=candidate,
        change_request=STORED_REQUEST,
    )
    [merge] = [e for e in plan if e.task_type == "governance.merge_plan"]
    text = await contract_surface_sections(
        RequestTemplateRenderer(create_prompt_asset_source("filesystem")), merge.inputs
    )

    assert {"backend/models.py", "backend/errors.py"} <= frozen
    assert "backend/models.py" not in merge.inputs["increment_footprint_index"]
    assert "- `backend/routes.py`" in merge.inputs["increment_footprint_index"]
    assert "- `backend/models.py`" in merge.inputs["increment_regenerated_index"]
    regenerated = text.split("Files this change touches that the scaffold writes")[1]
    assert "- `backend/models.py`" in regenerated and "- `backend/errors.py`" in regenerated


async def test_the_proposers_are_shown_the_regenerated_files_too():
    """#1868: the dev and qa proposers render the footprint through their own section. Bug
    caught: the merger told which files the scaffold writes while the proposers, who author the
    tasks, are told only the footprint."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers.planning_tasks import DevelopmentProposePlanTasksHandler
    from squadops.prompts.renderer import RequestTemplateRenderer

    section = await DevelopmentProposePlanTasksHandler()._increment_sections(
        RequestTemplateRenderer(create_prompt_asset_source("filesystem")),
        {
            "increment_footprint_index": "- `backend/routes.py`",
            "increment_regenerated_index": "- `backend/models.py`",
        },
    )

    assert "- `backend/routes.py`" in section
    assert "Files this change touches that the scaffold writes" in section
    assert section.index("- `backend/models.py`") > section.index("scaffold writes")


@pytest.mark.parametrize("profile_name", ["campaign-increment", "campaign-reference"])
def test_an_increments_framing_runs_the_plan_proposers(profile_name):
    """SIP-0109 §7.3 (#1870), on each campaign profile's own defaults: the framing table names
    the plan proposers, which is where the footprint, criteria and frozen indexes are taught.
    Bugs caught: a campaign increment framed by the merger alone (shakeout 2's three framings);
    or the reference increment refused at creation, as #762 refuses a bind-mode cycle no
    proposer can author."""
    from squadops.contracts.cycle_request_profiles import load_profile
    from squadops.cycles.models import AgentProfileEntry, SquadProfile
    from squadops.cycles.preflight import bind_mode_authoring_decision
    from squadops.cycles.task_plan import generate_task_plan

    defaults = dict(load_profile(profile_name).defaults)
    squad = SquadProfile(
        profile_id="full",
        name="full",
        description="",
        version=1,
        created_at=NOW,
        agents=tuple(
            AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
            for a, r in (
                ("nat", "strat"),
                ("neo", "dev"),
                ("eve", "qa"),
                ("data", "data"),
                ("max", "lead"),
                ("bob", "builder"),
            )
        ),
    )
    from squadops.capabilities.scaffold import InterfaceManifest

    cycle = _cycle(True)
    cycle = dataclasses.replace(
        cycle,
        applied_defaults=defaults,
        execution_overrides={**cycle.execution_overrides, "contract_ref": "art_contract"},
    )
    run = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")
    contract = MagicMock()
    contract.criteria_index_lines.return_value = ["- C1"]
    contract.behavioral.probes = ()

    plan = generate_task_plan(
        cycle,
        run,
        squad,
        contract=contract,
        interface_manifest=InterfaceManifest.from_yaml(CANDIDATE),
        change_request=STORED_REQUEST,
    )

    assert {
        "development.propose_plan_tasks",
        "qa.propose_plan_tasks",
        "strategy.propose_plan_guidance",
    } <= {e.task_type for e in plan}
    assert not bind_mode_authoring_decision({**defaults, "contract_ref": "art_contract"}).rejected


async def test_the_qa_proposer_is_shown_each_criterions_own_test_file():
    """#1874, entered at the qa proposer's real ``handle()`` on the shipped templates. The first
    multi-role increment framing (the reference, ``cyc_d4438834b2c3``) was refused because no qa
    task wrote the criteria's own test files: the qa proposer was handed that index as data and
    never shown its instruction. Bug caught: a surface the merger renders and the proposer who
    writes the qa tasks never sees — two copies of one list, drifted."""
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers.planning_tasks import QaProposePlanTasksHandler
    from squadops.prompts.renderer import RequestTemplateRenderer
    from tests.unit.capabilities.test_propose_plan_tasks import (
        _QA_PROPOSAL_RESPONSE,
        _make_context,
        _seeded_inputs,
    )

    context = _make_context(_QA_PROPOSAL_RESPONSE)
    context.ports.request_renderer = RequestTemplateRenderer(
        create_prompt_asset_source("filesystem")
    )
    inputs = {
        **_seeded_inputs(),
        "increment_footprint_index": "- `backend/routes.py`",
        "increment_criterion_files_index": "- C1 (endpoint `POST /runs`): "
        "`backend/tests/criteria/test_C1.py`",
        "increment_frozen_files_index": "- F1: `backend/tests/criteria/test_F1.py`",
    }

    await QaProposePlanTasksHandler().handle(context, inputs)

    messages = context.ports.llm.chat_stream_with_usage.call_args.args[0]
    prompt = "\n".join(str(m.content) for m in messages)
    assert "Each new criterion is proven in its own test file" in prompt
    assert "`backend/tests/criteria/test_C1.py`" in prompt
    # #1884: three live launches of the capacity change planned tests for rules it never stated.
    assert "What this increment's tests assert" in prompt
    assert "- F1: `backend/tests/criteria/test_F1.py`" in prompt


async def test_an_increment_plan_with_a_suiteless_qa_task_is_rejected_at_its_gate():
    """#1912, at the seam campaign shakeout 5's increment plan gate went through. Bug caught: a
    "full-suite regression" qa task with nothing expected passes the gate, fails whatever it
    returns, and ends the increment blocked_unverified. The control is the same plan with the
    task naming its suite."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    def plan(qa_expected: list[str]) -> str:
        d = yaml.safe_load(_plan("backend/routes.py"))
        d["tasks"].append(
            {
                "task_index": 1,
                "task_type": "qa.test",
                "role": "qa",
                "focus": "Full-suite regression and sort-mutation verification",
                "description": "verify",
                "expected_artifacts": qa_expected,
                "acceptance_criteria": [],
            }
        )
        return yaml.safe_dump(d)

    async def errors(qa_expected: list[str]) -> list[str]:
        executor = DispatchedFlowExecutor(
            cycle_registry=AsyncMock(),
            artifact_vault=_Vault(plan(qa_expected)),
            queue=AsyncMock(),
            squad_profile=AsyncMock(),
            task_timeout=5.0,
        )
        executor._cycle_event_bus = MagicMock()
        run = Run(
            "run_f",
            "cyc_inc",
            2,
            "completed",
            "system",
            "cfg",
            workload_type="framing",
            artifact_refs=("art_plan",),
        )
        found = await executor._reject_invalid_plan_before_workload_gate(
            run, _cycle(True), "progress_plan_review"
        )
        return [e for e in found if "declares no expected artifact" in e]

    [error] = await errors([])
    assert error.startswith("Task 1 (Full-suite regression and sort-mutation verification)")
    assert await errors(["backend/tests/test_runs.py"]) == []
