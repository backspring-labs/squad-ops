"""Each new criterion of an increment is proven in its own test file (SIP-0109 §8.1, §8.2).

The reference capacity change adds C1 and C2 on endpoints and C3 on the run's page. On
``fullstack_fastapi_react`` their files are ``backend/tests/criteria/test_C1.py``,
``…/test_C2.py`` and ``frontend/src/__tests__/criteria/C3.test.jsx``. A qa task writes each;
its verifier bundle is later frozen from it (#1705 e).
"""

from __future__ import annotations

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
from squadops.campaigns.increment_tree import increment_criterion_files
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)

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
STORED = stored_change_request(_REQUEST)
CANDIDATE = apply_manifest_delta(BASELINE, _REQUEST.manifest_delta)
C1, C2 = "backend/tests/criteria/test_C1.py", "backend/tests/criteria/test_C2.py"
C3 = "frontend/src/__tests__/criteria/C3.test.jsx"


def _plan(*tasks: tuple[str, tuple[str, ...]]) -> ImplementationPlan:
    return ImplementationPlan.from_yaml(_plan_yaml(*tasks))


def _plan_yaml(*tasks: tuple[str, tuple[str, ...]]) -> str:
    return yaml.safe_dump(
        {
            "version": 1,
            "project_id": "group_run",
            "cycle_id": "cyc_inc",
            "prd_hash": "abc",
            "summary": {"total_dev_tasks": 0, "total_qa_tasks": 0, "total_tasks": len(tasks)},
            "tasks": [
                {
                    "task_index": i,
                    "task_type": task_type,
                    "role": task_type.partition(".")[0].replace("development", "dev"),
                    "focus": "f",
                    "description": "d",
                    "expected_artifacts": list(artifacts),
                    "acceptance_criteria": [],
                }
                for i, (task_type, artifacts) in enumerate(tasks)
            ],
        }
    )


def _cycle() -> Cycle:
    return Cycle(
        cycle_id="cyc_inc",
        project_id="group_run",
        created_at=NOW,
        created_by="launcher",
        prd_ref="the group_run PRD",
        squad_profile_id="full",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"implementation_plan": True, "build_profile": "fullstack_fastapi_react"},
        execution_overrides={
            "contract_ref": "art_contract",
            "plan_artifact_refs": ["art_seed", "art_cr"],
            "campaign_proposal": {"proposal_id": "prop_cap", "baseline_manifest": BASELINE},
        },
        campaign_id="cmp_1",
        kind="increment",
    )


def test_each_new_criterion_has_its_own_file_by_its_surface():
    files = increment_criterion_files(STORED, "fullstack_fastapi_react")

    assert [(f.criterion_id, f.path) for f in files] == [("C1", C1), ("C2", C2), ("C3", C3)]


@pytest.mark.parametrize(
    ("tasks", "missing"),
    [
        ((("qa.test", (C1, C2, C3)),), []),
        ((("qa.test", (C1,)), ("qa.test", (C2, C3))), []),
        ((("qa.test", (C1, C2)),), ["C3"]),
        # A dev task naming the file does not prove the criterion: the qa role writes it.
        ((("qa.test", (C1, C2)), ("development.develop", (C3,))), ["C3"]),
    ],
    ids=["one-qa-task", "split-across-qa-tasks", "one-unplanned", "claimed-by-dev"],
)
def test_every_new_criterion_file_is_written_by_a_qa_task(tasks, missing):
    """§8.2. Bug caught: a criterion with no test of its own — never discriminated on the
    baseline, so never met, found only when the increment is judged."""
    errors = _plan(*tasks).validate_increment_criterion_files(
        increment_criterion_files(STORED, "fullstack_fastapi_react")
    )

    assert [e.split()[1] for e in errors] == missing


def test_the_plan_authors_are_shown_each_criterions_file():
    """Teach, then enforce (#686), entered at ``generate_task_plan`` and rendered through the
    plan author's appendices. Bug caught: a plan refused for a file nobody named to it."""
    import asyncio

    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.capabilities.handlers._plan_authoring import contract_surface_sections
    from squadops.capabilities.scaffold import InterfaceManifest
    from squadops.cycles.task_plan import generate_task_plan
    from squadops.prompts.renderer import RequestTemplateRenderer

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
    contract.criteria_index_lines.return_value = ["- K1"]
    contract.behavioral.probes = ()
    run = Run("run_f", "cyc_inc", 2, "running", "system", "cfg", workload_type="framing")

    plan = generate_task_plan(
        _cycle(),
        run,
        profile,
        contract=contract,
        interface_manifest=InterfaceManifest.from_yaml(CANDIDATE),
        change_request=STORED,
    )
    [merge] = [e for e in plan if e.task_type == "governance.merge_plan"]
    text = asyncio.run(
        contract_surface_sections(
            RequestTemplateRenderer(create_prompt_asset_source("filesystem")), merge.inputs
        )
    )

    assert "Each new criterion is proven in its own test file" in text
    assert f"- C3 (client_route `/runs/:run_id`): `{C3}`" in text


class _Vault:
    def __init__(self, plan: str) -> None:
        def ref(artifact_id, artifact_type, filename, run_id):
            return ArtifactRef(
                artifact_id,
                "group_run",
                artifact_type,
                filename,
                "h",
                1,
                "text/yaml",
                NOW,
                cycle_id="cyc_inc",
                run_id=run_id,
            )

        self.stored = {
            "art_plan": (
                ref("art_plan", "control_implementation_plan", "implementation_plan.yaml", "run_f"),
                plan.encode(),
            ),
            "art_seed": (
                ref("art_seed", "interface_manifest", "interface_manifest.yaml", "run_p"),
                CANDIDATE.encode(),
            ),
            "art_cr": (
                ref("art_cr", "change_request", "change_request.yaml", "run_p"),
                STORED.encode(),
            ),
        }

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def list_artifacts(self, **_):
        return [r for r, _ in self.stored.values()]


@pytest.mark.parametrize(("qa_files", "refused"), [((C1, C2, C3), []), ((C1, C2), ["C3"])])
async def test_the_plan_gate_refuses_a_plan_that_leaves_a_criterion_unproven(qa_files, refused):
    """Wiring, entered at the inter-workload plan gate the framing re-roll keys on (#522), with
    the cycle as the framing run saw it (#1849)."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    plan = _plan_yaml(("qa.test", qa_files))
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=_Vault(plan),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
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
        artifact_refs=("art_plan", "art_seed", "art_cr"),
    )

    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, _cycle(), "progress_plan_review"
    )

    assert [e.split()[1] for e in errors if "is proven in its own test file" in e] == refused


_F1 = "backend/tests/criteria/test_F1.py"


def _with_frozen_f1(cycle: Cycle) -> Cycle:
    import dataclasses

    overrides = dict(cycle.execution_overrides)
    overrides["campaign_proposal"] = {
        **overrides["campaign_proposal"],
        "frozen_criteria": [{"criterion_id": "F1", "test_path": _F1, "bundle_ref": "art_f1"}],
    }
    return dataclasses.replace(cycle, execution_overrides=overrides)


def _retiring_f1() -> str:
    """The reference change request, retiring the frozen F1 (a known earlier criterion)."""
    authored = yaml.safe_load((_FIXTURES / "reference-capacity-change-request.yaml").read_text())
    authored["retires"] = [{"criterion_id": "F1", "reason": "capacity replaces the open join"}]
    request = validate_proposal(
        authored,
        ProposalContext(
            "prop_cap",
            1,
            "sha-accepted",
            BASELINE,
            "fullstack_fastapi_react",
            ("backend/**", "frontend/**"),
            ("F1",),
        ),
    ).change_request
    return stored_change_request(request)


@pytest.mark.parametrize(
    ("qa_files", "change_request", "refused"),
    [
        ((C1, C2, C3, _F1), STORED, ["F1"]),
        ((C1, C2, C3), STORED, []),
        ((C1, C2, C3, _F1), "retiring", []),
    ],
    ids=["rewrites-a-frozen-verifier", "leaves-it-alone", "the-change-retires-it"],
)
async def test_the_plan_gate_refuses_a_plan_that_rewrites_a_frozen_verifier(
    qa_files, change_request, refused
):
    """§8.1, SIP-0109 §19 item 12e, entered at the plan gate. Bug caught: an increment's qa task
    rewriting an earlier criterion's test to agree with the new change, so the regression it
    exists to catch is edited away."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    document = _retiring_f1() if change_request == "retiring" else change_request
    vault = _Vault(_plan_yaml(("qa.test", qa_files)))
    vault.stored["art_cr"] = (vault.stored["art_cr"][0], document.encode())
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=vault,
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
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
        artifact_refs=("art_plan", "art_seed", "art_cr"),
    )

    errors = await executor._reject_invalid_plan_before_workload_gate(
        run, _with_frozen_f1(_cycle()), "progress_plan_review"
    )

    assert [
        e.split("criterion ")[1].split(".")[0] for e in errors if "frozen verifier" in e
    ] == refused


def test_the_plan_authors_are_shown_the_frozen_verifiers():
    from squadops.cycles.task_plan import inject_contract_inputs

    contract = MagicMock()
    contract.criteria_index_lines.return_value = ["- K1"]
    contract.behavioral.probes = ()
    inputs: dict = {}

    inject_contract_inputs(
        inputs, contract, "governance.merge_plan", None, None, (), (("F1", _F1),)
    )

    assert inputs["increment_frozen_files_index"] == f"- F1: `{_F1}`"
