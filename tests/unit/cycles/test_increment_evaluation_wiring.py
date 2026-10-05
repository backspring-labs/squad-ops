"""An increment's implementation ends in its evaluation (SIP-0109 §8; #1705 e, part 1).

Wiring, at the two moments the inputs are composed: plan generation (what the implementation
run's provisioning calls) and dispatch-time enrichment (what every dispatched task passes).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import yaml

from squadops.campaigns.change_request import (
    ProposalContext,
    apply_manifest_delta,
    stored_change_request,
    validate_proposal,
)
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_plan import generate_task_plan

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
CANDIDATE = InterfaceManifest.from_yaml(apply_manifest_delta(BASELINE, _REQUEST.manifest_delta))
PROFILE = SquadProfile(
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
_PLAN = ImplementationPlan.from_yaml(
    yaml.safe_dump(
        {
            "version": 1,
            "project_id": "group_run",
            "cycle_id": "cyc_inc",
            "prd_hash": "abc",
            "summary": {"total_dev_tasks": 1, "total_qa_tasks": 1, "total_tasks": 2},
            "tasks": [
                {
                    "task_index": 0,
                    "task_type": "development.develop",
                    "role": "dev",
                    "focus": "the capacity limit",
                    "description": "d",
                    "expected_artifacts": ["backend/routes.py"],
                    "acceptance_criteria": [],
                },
                {
                    "task_index": 1,
                    "task_type": "qa.test",
                    "role": "qa",
                    "focus": "the criteria",
                    "description": "d",
                    "expected_artifacts": ["backend/tests/criteria/test_C1.py"],
                    "acceptance_criteria": [],
                    "depends_on": [0],
                },
            ],
        }
    )
)


def _cycle(increment: bool) -> Cycle:
    overrides: dict = {}
    if increment:
        overrides["campaign_proposal"] = {
            "proposal_id": "prop_cap",
            "baseline_manifest": BASELINE,
            "accepted_cycle_id": "cyc_accepted",
        }
    return Cycle(
        cycle_id="cyc_inc",
        project_id="group_run",
        created_at=NOW,
        created_by="launcher",
        prd_ref="the PRD",
        squad_profile_id="full",
        squad_profile_snapshot_ref="x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"build_profile": "fullstack_fastapi_react", "implementation_plan": True},
        execution_overrides=overrides,
        campaign_id="cmp_1" if increment else None,
        kind="increment" if increment else None,
    )


def _implementation(increment: bool, change_request: str | None):
    run = Run("run_i", "cyc_inc", 3, "running", "system", "cfg", workload_type="implementation")
    return generate_task_plan(
        _cycle(increment),
        run,
        PROFILE,
        plan=_PLAN,
        interface_manifest=CANDIDATE,
        change_request=change_request,
    )


def test_an_increments_implementation_ends_in_its_evaluation_with_what_it_judges():
    """Entered at ``generate_task_plan``. Bugs caught: the evaluation never planned, planned
    before the work it judges, or planned without the criteria and routes it judges."""
    plan = _implementation(True, STORED)

    *_, last = plan
    assert last.task_type == "qa.evaluate_increment"
    assert last.inputs["increment_id"] == "prop_cap"
    assert [f["path"] for f in last.inputs["increment_criterion_files"]] == [
        "backend/tests/criteria/test_C1.py",
        "backend/tests/criteria/test_C2.py",
        "frontend/src/__tests__/criteria/C3.test.jsx",
    ]
    assert "capacity-status" in last.inputs["increment_declared_routes"]["/runs/:run_id"]
    # Handed to the evaluation alone: the build tasks are not given the change request.
    assert not any(
        "increment_criterion_files" in e.inputs or "increment_change_request" in e.inputs
        for e in plan[:-1]
    )


def test_an_ordinary_implementation_has_no_evaluation():
    assert "qa.evaluate_increment" not in [e.task_type for e in _implementation(False, None)]


class _Vault:
    def __init__(self, stored: dict[str, tuple[ArtifactRef, bytes]]) -> None:
        self.stored = stored

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]

    async def list_artifacts(self, *, cycle_id=None, **_):
        return [r for r, _ in self.stored.values() if cycle_id is None or r.cycle_id == cycle_id]


def _ref(artifact_id: str, filename: str, cycle_id: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id,
        "group_run",
        "source",
        filename,
        "h",
        1,
        "text/plain",
        NOW,
        cycle_id=cycle_id,
        run_id="r",
    )


async def test_the_evaluation_is_handed_the_accepted_tree_as_the_increment_seeded_it():
    """Entered at ``_enrich_envelope``, as every dispatch passes it. Bug caught: the accepted
    tree read from the candidate — the increment's own edits as the baseline, so nothing
    ever discriminates — or from nothing at all."""
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    stored = {
        "a_routes": (_ref("a_routes", "backend/routes.py", "cyc_accepted"), b"accepted routes"),
        "i_routes": (_ref("i_routes", "backend/routes.py", "cyc_inc"), b"increment routes"),
        "a_view": (_ref("a_view", "frontend/src/views/RunListView.jsx", "cyc_accepted"), b"list"),
        # #1876: the accepted tree's own scaffold-frozen file. The increment's seed leaves it out
        # (the candidate regenerates it), but the baseline overlay needs the baseline's.
        "a_models": (_ref("a_models", "backend/models.py", "cyc_accepted"), b"baseline models"),
    }
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=_Vault(stored),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
    )
    executor._cycle_event_bus = MagicMock()
    [evaluation] = [
        e for e in _implementation(True, STORED) if e.task_type == "qa.evaluate_increment"
    ]

    enriched = await executor._enrich_envelope(
        evaluation, {}, list(stored), [(i, r) for i, (r, _) in stored.items()]
    )

    assert enriched.inputs["accepted_tree_files"] == {
        "backend/routes.py": "accepted routes",
        "frontend/src/views/RunListView.jsx": "list",
        "backend/models.py": "baseline models",
    }
    assert enriched.inputs["acceptance_workspace_files"]["backend/routes.py"] == "increment routes"


async def test_the_evaluation_is_handed_the_bundles_its_launch_pinned():
    """§8.1, entered at ``_enrich_envelope``. Bugs caught: a pinned bundle never read, so every
    frozen criterion is blocked; or an unreadable one crashing the dispatch instead of being
    judged blocked."""
    import dataclasses
    import json

    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    bundle = {"files": {"backend/tests/criteria/test_F1.py": "def test(): ..."}, "invocation": []}
    stored = {
        "art_f1": (
            _ref("art_f1", "verifier_bundle_F1.json", "cyc_prior"),
            json.dumps(bundle).encode(),
        )
    }
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=_Vault(stored),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
    )
    executor._cycle_event_bus = MagicMock()
    [evaluation] = [
        e for e in _implementation(True, STORED) if e.task_type == "qa.evaluate_increment"
    ]
    config = dict(evaluation.inputs["resolved_config"])
    config["campaign_proposal"] = {
        **config["campaign_proposal"],
        "frozen_criteria": [
            {"criterion_id": "F1", "bundle_ref": "art_f1"},
            {"criterion_id": "F2", "bundle_ref": "art_gone"},
        ],
    }
    evaluation = dataclasses.replace(
        evaluation, inputs={**evaluation.inputs, "resolved_config": config}
    )

    enriched = await executor._enrich_envelope(evaluation, {}, [], [])

    assert enriched.inputs["frozen_bundles"] == {"F1": bundle}


def test_a_parameterized_route_is_seeded_by_its_collections_create():
    """§8.3. Bugs caught: the run page read at ``/runs/:run_id`` literally (never the view), or
    seeded with a body the create probe would not send."""
    from squadops.campaigns.increment_tree import route_seeds
    from squadops.capabilities.scaffold_contract import create_request_body

    seeds = route_seeds(CANDIDATE)

    [create] = [ep for ep in CANDIDATE.api.endpoints if (ep.method, ep.path) == ("POST", "/runs")]
    assert seeds == {
        "/runs/:run_id": {
            "method": "POST",
            "path": "/runs",
            "json": create_request_body(CANDIDATE, create),
            "param": "run_id",
        }
    }
    [evaluation] = [
        e for e in _implementation(True, STORED) if e.task_type == "qa.evaluate_increment"
    ]
    assert evaluation.inputs["increment_route_seeds"] == seeds


def test_a_replaced_verifier_reaches_the_evaluation_at_the_file_its_launch_pinned():
    """§8.1, entered at ``generate_task_plan``. Bugs caught: the evaluation never told which
    verifier was replaced, so the new one is never frozen; or told a path other than the pinned
    one, so it freezes a file nobody wrote."""
    import dataclasses

    authored = yaml.safe_load((_FIXTURES / "reference-capacity-change-request.yaml").read_text())
    authored["replaces_verifiers"] = [{"criterion_id": "F1", "reason": "a full run now refuses"}]
    replacing = stored_change_request(
        validate_proposal(
            authored,
            ProposalContext(
                "prop_cap",
                1,
                "sha-accepted",
                BASELINE,
                "fullstack_fastapi_react",
                ("backend/**", "frontend/**"),
                ("F1", "F2"),
            ),
        ).change_request
    )
    cycle = _cycle(True)
    block = {
        **cycle.execution_overrides["campaign_proposal"],
        "frozen_criteria": [
            {"criterion_id": "F1", "test_path": "backend/tests/criteria/test_F1.py"},
            {"criterion_id": "F2", "test_path": "backend/tests/criteria/test_F2.py"},
        ],
    }
    cycle = dataclasses.replace(cycle, execution_overrides={"campaign_proposal": block})
    run = Run("run_i", "cyc_inc", 3, "running", "system", "cfg", workload_type="implementation")

    *_, last = generate_task_plan(
        cycle, run, PROFILE, plan=_PLAN, interface_manifest=CANDIDATE, change_request=replacing
    )

    assert last.inputs["increment_replaced_criteria"] == [
        {"criterion_id": "F1", "path": "backend/tests/criteria/test_F1.py"}
    ]
    assert last.inputs["increment_retired_criteria"] == ["F1"]


async def test_the_evaluation_judges_the_candidate_with_its_qa_suites():
    """#1880, entered at ``_enrich_envelope``. The reference increment's evaluation froze no
    criterion — each ``not_run``, ``<test_path> is not in the tree`` — because the candidate it
    was handed was cut to source and config, and the criteria's own files are qa suites. Bugs
    caught: the evaluation's candidate without the criterion files; or every acceptance workspace
    widened to tests, which the typed-acceptance checks were never meant to read."""
    import dataclasses

    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    suite = dataclasses.replace(
        _ref("i_c1", "backend/tests/criteria/test_C1.py", "cyc_inc"),
        artifact_type="test",
        metadata={"producing_task_type": "qa.test"},
    )
    routes = dataclasses.replace(
        _ref("i_routes", "backend/routes.py", "cyc_inc"),
        metadata={"producing_task_type": "development.develop"},
    )
    stored = {
        "i_routes": (routes, b"increment routes"),
        "i_c1": (suite, b"def test_c1(): ..."),
        "a_routes": (_ref("a_routes", "backend/routes.py", "cyc_accepted"), b"accepted routes"),
    }
    executor = DispatchedFlowExecutor(
        cycle_registry=AsyncMock(),
        artifact_vault=_Vault(stored),
        queue=AsyncMock(),
        squad_profile=AsyncMock(),
        task_timeout=5.0,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
    )
    executor._cycle_event_bus = MagicMock()
    plan = _implementation(True, STORED)
    [evaluation] = [e for e in plan if e.task_type == "qa.evaluate_increment"]
    [develop] = [e for e in plan if e.task_type == "development.develop"]
    listed = [(i, r) for i, (r, _) in stored.items() if r.cycle_id == "cyc_inc"]

    judged = await executor._enrich_envelope(evaluation, {}, [i for i, _ in listed], listed)
    built = await executor._enrich_envelope(develop, {}, [i for i, _ in listed], listed)

    candidate = judged.inputs["acceptance_workspace_files"]
    assert candidate["backend/tests/criteria/test_C1.py"] == "def test_c1(): ..."
    assert candidate["backend/routes.py"] == "increment routes"
    assert "backend/tests/criteria/test_C1.py" not in built.inputs["acceptance_workspace_files"]
