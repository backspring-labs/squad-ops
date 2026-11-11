"""The plan gate's skillset check and the plannable property (SIP-0116 §6.3, §9; phase 2),
on the first plannable type outside the base set, ``qa.run_remote_operation`` (SIP-0117 R4.4).
The contract and the offer are fixtures: no profile requires anything yet."""

from __future__ import annotations

import pytest
import yaml

from squadops.cycles.implementation_plan import ImplementationPlan, planner_build_task_types
from squadops.tasks.base_set import BASE_SETS, base_plannable_task_types
from squadops.tasks.task_types import TaskType, plannable

pytestmark = [pytest.mark.domain_orchestration]

FIXTURE_TYPE = TaskType.QA_RUN_REMOTE_OPERATION
OFFER = {
    "contract": "fixture.scenario_verification",
    "mode": "play",
    "task_type": FIXTURE_TYPE.value,
    "role": "qa",
    "agent_id": "eve",
    "skillset": "fixture-qa",
}
RECORD = {"base_set": {"version": "base@1"}, "offered": [OFFER]}


def _plan(*tasks: dict) -> str:
    rows = [
        {"task_index": i, "focus": f"focus {i}", "description": "d", **task}
        for i, task in enumerate(tasks)
    ]
    return yaml.safe_dump(
        {
            "version": 1,
            "project_id": "p",
            "cycle_id": "c",
            "prd_hash": "h",
            "tasks": rows,
            "summary": {"total_dev_tasks": 1, "total_qa_tasks": 1, "total_tasks": len(rows)},
        }
    )


DEV = {"task_type": "development.develop", "role": "dev", "expected_artifacts": ["a.py"]}
SCENARIO = {
    "task_type": FIXTURE_TYPE.value,
    "role": "qa",
    "contract": "fixture.scenario_verification",
    "mode": "play",
}


def test_every_base_set_type_is_plannable_and_only_one_type_is_plannable_outside_it():
    """Bug caught: a type added to the base set without being plannable, so the planner is
    offered a type its own parser refuses; or a second plannable type slipping in without its
    own proposal (SIP-0116 §6.3), which this exact set makes a deliberate edit."""
    for version, members in BASE_SETS.items():
        assert all(t.plannable for t in members), version
    assert {t for t in TaskType if t.plannable} - set(base_plannable_task_types()) == {
        TaskType.QA_RUN_REMOTE_OPERATION
    }
    assert TaskType.QA_RUN_REMOTE_OPERATION not in base_plannable_task_types()
    assert plannable("not.a.task_type") is False


def test_a_type_outside_the_plannable_set_is_refused_when_the_plan_is_parsed():
    with pytest.raises(ValueError, match="unknown task_type 'qa.validate'"):
        ImplementationPlan.from_yaml(_plan(DEV, {**SCENARIO, "task_type": "qa.validate"}))


def test_an_ordinary_cycle_is_not_offered_a_registered_plannable_type():
    """§14's proof: with a fixture capability plannable, a cycle whose work requires nothing
    isn't offered it. Bug caught: registration reading as enablement, so every stack's
    planner and gate accept a step only one stack's squad can take."""
    plan = ImplementationPlan.from_yaml(_plan(DEV, SCENARIO))
    ordinary = {"base_set": {"version": "base@1"}, "offered": []}

    assert planner_build_task_types(offer_builder=True) == {
        "development.develop",
        "qa.test",
        "builder.assemble",
    }
    assert plan.validate_against_offered(ordinary) == [
        "Task 1: `fixture.scenario_verification` in `play` mode as `qa.run_remote_operation` for `qa` "
        "isn't offered to this cycle. Its requirements name no contract"
    ]
    assert plan.validate_against_offered(None) == plan.validate_against_offered(ordinary)


def test_a_contract_the_cycles_requirements_name_is_accepted():
    plan = ImplementationPlan.from_yaml(_plan(DEV, SCENARIO))

    assert plan.validate_against_offered(RECORD) == []
    assert (plan.tasks[1].contract, plan.tasks[1].mode) == ("fixture.scenario_verification", "play")


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            {"mode": "multiplayer"},
            "Task 1: `fixture.scenario_verification` in `multiplayer` mode as `qa.run_remote_operation` for "
            "`qa` isn't offered to this cycle. Its requirements name "
            "`fixture.scenario_verification` in `play` mode as `qa.run_remote_operation` for `qa`",
        ),
        (
            {"role": "dev"},
            "Task 1: `fixture.scenario_verification` in `play` mode as `qa.run_remote_operation` for `dev` "
            "isn't offered to this cycle.",
        ),
        (
            {"contract": "fixture.capture"},
            "Task 1: `fixture.capture` in `play` mode as `qa.run_remote_operation` for `qa` isn't offered",
        ),
        (
            {"contract": "", "mode": ""},
            "Task 1: `qa.run_remote_operation` is outside the base set, so the task names the contract and "
            "mode it runs as",
        ),
    ],
    ids=["another mode", "another role's agent", "another contract", "no contract"],
)
def test_a_task_the_record_does_not_offer_is_refused_by_name(change, expected):
    """One mode never implies another, and the supplier is the task's routed agent. Bug
    caught: a plan taking a contract in a mode nobody declared, or handing it to a role whose
    agent doesn't carry the skillset."""
    plan = ImplementationPlan.from_yaml(_plan(DEV, {**SCENARIO, **change}))

    (error,) = plan.validate_against_offered(RECORD)
    assert error.startswith(expected)


def test_a_base_set_task_naming_an_unoffered_contract_is_refused():
    plan = ImplementationPlan.from_yaml(
        _plan({**DEV, "contract": "fixture.gameplay_implementation"})
    )

    (error,) = plan.validate_against_offered(RECORD)
    assert error.startswith(
        "Task 0: `fixture.gameplay_implementation` as `development.develop` for `dev` isn't offered"
    )


def test_a_plan_of_base_set_tasks_serializes_as_it_did_before_the_fields_existed():
    """Bug caught: two new keys entering every stored plan, which moves every plan's canonical
    hash and the byte-identity SIP-0116 §14 holds existing stacks to."""
    base = ImplementationPlan.from_yaml(_plan(DEV)).to_dict()
    with_contract = ImplementationPlan.from_yaml(_plan(DEV, SCENARIO)).to_dict()

    assert "contract" not in base["tasks"][0] and "mode" not in base["tasks"][0]
    assert with_contract["tasks"][1]["contract"] == "fixture.scenario_verification"
    assert with_contract["tasks"][1]["mode"] == "play"
    round_tripped = ImplementationPlan.from_yaml(yaml.safe_dump(with_contract))
    assert round_tripped.to_dict() == with_contract


def test_a_contract_that_is_not_text_is_refused_when_the_plan_is_parsed():
    with pytest.raises(ValueError, match="Task 0: contract and mode must be strings"):
        ImplementationPlan.from_yaml(_plan({**DEV, "contract": ["a"]}))


@pytest.mark.parametrize(
    "record",
    [
        {},
        {"offered": []},
        {"base_set": {}, "offered": []},
        {"base_set": {"version": "base@1"}},
        {"base_set": {"version": "base@1"}, "offered": None},
        "base@1",
        {"base_set": {"version": "base@1"}, "offered": ["fixture.scenario_verification"]},
        {"base_set": {"version": "base@1"}, "offered": [{"contract": "c", "role": "qa"}]},
    ],
    ids=[
        "empty",
        "no base set",
        "no version",
        "no offered",
        "offered null",
        "not a mapping",
        "an offer that is not a mapping",
        "an offer with no task type",
    ],
)
def test_a_record_with_a_part_missing_is_refused_never_filled_in(record):
    """Bug caught: the gate defaulting a missing base set to the current one, or a missing
    ``offered`` to "nothing offered", and passing a plan on a record nobody can vouch for."""
    plan = ImplementationPlan.from_yaml(_plan(DEV))

    (error,) = plan.validate_against_offered(record)
    assert error.startswith("The cycle's skillset record can't be read")


def test_a_record_naming_a_base_set_this_deploy_does_not_hold_is_refused():
    plan = ImplementationPlan.from_yaml(_plan(DEV))

    (error,) = plan.validate_against_offered({"base_set": {"version": "base@9"}, "offered": []})
    assert "Unknown base set 'base@9'" in error


def test_only_a_cycle_with_no_record_at_all_is_read_as_the_legacy_base_set():
    plan = ImplementationPlan.from_yaml(_plan(DEV))

    assert plan.validate_against_offered(None) == []
