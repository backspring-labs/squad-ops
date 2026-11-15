"""A plan task that names a contract, from the plan to the dispatched task (SIP-0116 §6.1): the
plan checks at dispatch, and what the envelope carries to the handler.

In the first milestone an operation is the framework's step (SIP-0117 R5.14), so the contract a
plan names here is one over a base-set type: ``game.unit_tests`` on ``qa.test``, in ``headless``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import yaml

from squadops.capabilities.capability_contracts import CAPABILITY_CONTRACTS, contract_errors
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
from squadops.cycles.task_plan import generate_task_plan
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 11, 10, tzinfo=UTC)
PROFILE = SquadProfile(
    profile_id="fixture-squad",
    name="F",
    description="",
    version=1,
    agents=tuple(
        AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
        for a, r in (
            ("max", "lead"),
            ("neo", "dev"),
            ("nat", "strat"),
            ("eve", "qa"),
            ("data", "data"),
        )
    ),
    created_at=NOW,
)
OFFER = {
    "contract": "game.unit_tests",
    "mode": "headless",
    "task_type": "qa.test",
    "role": "qa",
    "agent_id": "eve",
    "skillset": "fixture-qa",
}
ASSIGNMENT = {
    "role": "qa",
    "agent_id": "eve",
    "skillset": "fixture-qa",
    "version": 1,
    "digest": "digest-of-fixture-qa",
}
RECORD = {"base_set": {"version": "base@1"}, "offered": [OFFER], "assignment": [ASSIGNMENT]}
RUN = Run(
    run_id="run_1",
    cycle_id="cyc_op",
    run_number=1,
    status="queued",
    initiated_by="api",
    resolved_config_hash="h",
    workload_type=WorkloadType.IMPLEMENTATION,
)


def _cycle(record) -> Cycle:
    return Cycle(
        cycle_id="cyc_op",
        project_id="p",
        created_at=NOW,
        created_by="s",
        prd_ref="PRD",
        squad_profile_id="fixture-squad",
        squad_profile_snapshot_ref="sha",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"implementation_plan": True},
        execution_overrides={},
        skillset_record=record,
    )


def _plan(*, planned_operation: bool = False, **named) -> ImplementationPlan:
    """A develop task and a qa test task naming ``game.unit_tests`` (changed by ``named``), and,
    when asked, an operation task the planner wrote itself."""
    tasks = [
        {
            "task_index": 0,
            "task_type": "development.develop",
            "role": "dev",
            "focus": "map",
            "description": "implement the map",
            "expected_artifacts": ["src/map.py"],
        },
        {
            "task_index": 1,
            "task_type": "qa.test",
            "role": "qa",
            "focus": "suite",
            "description": "author the suite",
            "expected_artifacts": ["tests/test_map.py"],
            "depends_on": [0],
            "contract": "game.unit_tests",
            "mode": "headless",
            **named,
        },
    ]
    if planned_operation:
        tasks.append(
            {
                "task_index": 2,
                "task_type": "qa.run_remote_operation",
                "role": "qa",
                "focus": "open the map",
                "description": "play the scenario",
                "depends_on": [0],
            }
        )
    return ImplementationPlan.from_yaml(
        yaml.safe_dump(
            {
                "version": 1,
                "project_id": "p",
                "cycle_id": "cyc_op",
                "prd_hash": "h",
                "tasks": tasks,
                "summary": {
                    "total_dev_tasks": 1,
                    "total_qa_tasks": len(tasks) - 1,
                    "total_tasks": len(tasks),
                },
            }
        )
    )


def _named_envelope(envelopes):
    (envelope,) = [e for e in envelopes if e.task_type == TaskType.QA_TEST]
    return envelope


def test_the_dispatched_task_carries_its_contract_and_the_supplier_the_record_names():
    """Enters at ``generate_task_plan``, the caller the live run uses. Bug caught: the plan
    naming a contract and the envelope dropping it, so the handler has nothing to say which
    skillset supplies the operation and would have to look one up."""
    envelope = _named_envelope(generate_task_plan(_cycle(RECORD), RUN, PROFILE, plan=_plan()))

    assert envelope.inputs["operation"] == {
        "contract": "game.unit_tests",
        "mode": "headless",
        "role": "qa",
        "skillset": "fixture-qa",
        "skillset_digest": "digest-of-fixture-qa",
        "agent_id": "eve",
    }
    assert envelope.agent_id == "eve"
    assert "operation" not in [
        key
        for e in generate_task_plan(_cycle(RECORD), RUN, PROFILE, plan=_plan())
        if e.task_type != TaskType.QA_TEST
        for key in e.inputs
    ]


@pytest.mark.parametrize(
    ("record", "plan_change", "expected"),
    [
        (
            {"base_set": {"version": "base@1"}, "offered": [], "assignment": []},
            {},
            "isn't offered to this cycle",
        ),
        (None, {}, "isn't offered to this cycle"),
        (RECORD, {"mode": "editor"}, "in `editor` mode"),
        (
            RECORD,
            {"planned_operation": True},
            "runs an operation, which is the framework's step in this milestone",
        ),
    ],
    ids=["not offered", "no record", "another mode", "a planned operation"],
)
def test_dispatch_refuses_a_plan_the_gates_would_have_refused(record, plan_change, expected):
    """The raising backstop. Bug caught: a plan that reached dispatch without passing a gate
    (a resumed run, a seeded plan) carrying a contract its squad doesn't supply."""
    with pytest.raises(CycleError, match="skillset coverage") as refused:
        generate_task_plan(_cycle(record), RUN, PROFILE, plan=_plan(**plan_change))

    assert expected in str(refused.value)


def test_an_offer_with_no_recorded_supplier_is_refused_rather_than_dispatched_without_one():
    """Bug caught: a record that offers a contract and holds no assignment for it, so the
    envelope would name a skillset with no digest to check it against."""
    orphaned = {**RECORD, "assignment": []}

    with pytest.raises(CycleError, match="holds no supplier for it"):
        generate_task_plan(_cycle(orphaned), RUN, PROFILE, plan=_plan())


def test_a_plan_of_base_set_tasks_dispatches_as_before():
    plan = _plan(contract="", mode="")

    envelopes = generate_task_plan(_cycle(None), RUN, PROFILE, plan=plan)

    assert all("operation" not in e.inputs for e in envelopes)
    assert TaskType.QA_RUN_REMOTE_OPERATION not in {e.task_type for e in envelopes}


def test_the_declared_game_contracts_are_well_formed_and_only_one_needs_a_new_task_type():
    """Bug caught: a contract declared under the wrong key, with a repeated mode or with no
    evidence stated; or a second game contract quietly needing a task type of its own."""
    assert contract_errors(CAPABILITY_CONTRACTS) == []
    assert sorted(CAPABILITY_CONTRACTS) == [
        "game.gameplay_implementation",
        "game.increment_design",
        "game.scenario_verification",
        "game.unit_tests",
    ]
    assert [c.id for c in CAPABILITY_CONTRACTS.values() if c.task_type.runs_an_operation] == [
        "game.scenario_verification"
    ]
