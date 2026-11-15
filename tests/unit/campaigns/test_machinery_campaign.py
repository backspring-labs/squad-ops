"""A scripted squad's two-increment Campaign through a worker, from its start to its objective
(#3050, slice 2, part 2).

Entered where the runtime enters a Campaign: its calibration record heard
(``CampaignProgress.calibration_recorded``), which launches its first increment through the
launch service and the cycle-create path; each cycle's end heard by the completion boundary the
executor composes; every launch after it decided by the Campaign. The test rules each gate as an
operator's route does. See ``machinery`` for what is composed and what isn't.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import json
from datetime import UTC, datetime

import pytest
import yaml

from adapters.remote_execution.fixture_operation_runner import WORLD_PATH
from squadops.campaigns.calibration_record import record_for
from squadops.campaigns.campaign_branch import head
from squadops.campaigns.gate import ruling_transition
from squadops.campaigns.increment_tree import INCREMENT_EVALUATION_ARTIFACT_TYPE
from squadops.campaigns.launch_requests import start_transition
from squadops.campaigns.models import CampaignState
from squadops.cycles.gate_decisions import record_gate_decision
from squadops.cycles.models import GateDecision, GateDecisionValue
from squadops.llm.script import script_version
from tests.unit.campaigns.builders import campaign, policy
from tests.unit.campaigns.machinery import PROJECT, answer, compose, emitted
from tests.unit.remote_execution.scenario_fixture import DOOR_OPENS, OPEN, SHUT

pytestmark = [pytest.mark.domain_orchestration]

CID = "cmp_machinery1"
SCOPE = ("tally/**", ".fixture/**")
INCREMENT_RULING = "progress_increment_ruling"
PLAN_REVIEW = "progress_plan_review"

LAMP_LIGHTS = {
    **copy.deepcopy(DOOR_OPENS),
    "scenario_id": "C-3",
    "steps": [{"action": "click_gui", "path": "PlayerGui.LampPanel.Switch"}],
    "assertions": [
        DOOR_OPENS["assertions"][0],
        {
            "id": "lamp-lit",
            "observe": {
                "kind": "property",
                "path": "Workspace.Lamp",
                "name": "Enabled",
                "context": "server",
            },
            "expect": {"op": "equals", "value": True},
        },
    ],
    "named_assertion": "lamp-lit",
}
_SWITCH = {"PlayerGui.LampPanel.Switch": {"gui": {"visible": True}}}
#: Increment two's candidate: the lamp lights, and the door collides again.
LIT_SHUT = {
    "client": {**OPEN["client"], **_SWITCH},
    "server": {**SHUT["server"], "Workspace.Lamp": {"properties": {"Enabled": True}}},
}
#: The repair's: the lamp lights and the door stays open.
LIT_OPEN = {
    "client": {**OPEN["client"], **_SWITCH},
    "server": {**OPEN["server"], "Workspace.Lamp": {"properties": {"Enabled": True}}},
}


def _yaml(document: dict) -> str:
    return yaml.safe_dump(document, sort_keys=False, width=1000).strip()


def _proposal(criterion: str, statement: str, scenario: dict, surface: str) -> str:
    request = {
        "kind": "feature",
        "prd_delta": [{"id": criterion.lower(), "op": "add", "text": statement}],
        "manifest_delta": [],
        "criteria": [
            {
                "id": criterion,
                "statement": statement,
                "surface_kind": "scenario",
                "surface": surface,
                "observable": statement,
                "scenario": scenario,
            }
        ],
        "must_not_break": [],
        "retires": [],
        "replaces_verifiers": [],
        "footprint": [WORLD_PATH],
    }
    return emitted("change_request.yaml", _yaml(request), "yaml")


def _develop_task(focus: str) -> dict:
    return {
        "task_type": "development.develop", "role": "dev", "focus": focus,
        "description": f"{focus}, in the world file.", "expected_artifacts": [WORLD_PATH],
        "acceptance_criteria": [], "depends_on_focus": [],
    }  # fmt: skip


def _framing(focus: str) -> list[dict]:
    """The framing run's answers, in its order: one develop task writing the world."""
    brief = {
        "version": 1, "brief_id": "brief-1", "objective_summary": focus,
        "accepted_stack": {"backend": "Python"}, "must_cover_requirements": [focus],
        "scope_cuts": [], "risk_areas": [], "source_artifact_refs": ["change_request.yaml"],
        "major_components": [WORLD_PATH], "dependency_assumptions": [],
        "time_budget_guidance": {"world": 100}, "task_granularity_guidance": "one task",
        "artifact_naming_conventions": [], "open_questions": [],
    }  # fmt: skip
    proposed = {
        "version": 1, "proposal_id": "prop-dev", "source_brief_id": "brief-1",
        "proposing_role": "development", "scope_statement": focus,
        "tasks": [_develop_task(focus)], "brief_conflicts": [], "assumptions": [],
        "risks": [], "gaps_not_covered": [], "confidence": "high",
    }  # fmt: skip
    qa = {
        **proposed, "proposal_id": "prop-qa", "proposing_role": "qa",
        "scope_statement": "the framework plays the scenario on the worker", "tasks": [],
    }  # fmt: skip
    guidance = {
        "version": 1, "guidance_id": "guid-1", "source_brief_id": "brief-1",
        "proposing_role": "strategy", "priority_guidance": [], "ordering_guidance": [],
        "risk_guidance": [], "time_budget_guidance": [], "scope_cut_guidance": [],
        "must_not_skip": [], "defer_if_time_constrained": [], "confidence": "high",
    }  # fmt: skip
    plan = {
        "version": 1, "project_id": PROJECT, "cycle_id": "cyc_unknown", "prd_hash": "abc",
        "tasks": [{**_develop_task(focus), "task_index": 0, "depends_on": []}],
        "summary": {"total_dev_tasks": 1, "total_qa_tasks": 0, "total_tasks": 1,
                    "estimated_layers": []},
    }  # fmt: skip
    for task in plan["tasks"]:
        task.pop("depends_on_focus")
    return [
        answer("development.design_plan", 1, f"# Design\n\n{focus}, in `{WORLD_PATH}`.\n"),
        answer("qa.define_test_strategy", 1, "# Test strategy\n\nThe scenario is played.\n"),
        answer(
            "governance.prepare_plan_authoring_brief",
            1,
            emitted("plan_authoring_brief.yaml", _yaml(brief), "yaml"),
        ),
        answer(
            "development.propose_plan_tasks",
            1,
            emitted("proposed_plan_tasks.yaml", _yaml(proposed), "yaml"),
        ),
        answer("qa.propose_plan_tasks", 1, emitted("proposed_plan_tasks.yaml", _yaml(qa), "yaml")),
        answer(
            "strategy.propose_plan_guidance",
            1,
            emitted("plan_guidance.yaml", _yaml(guidance), "yaml"),
        ),
        answer(
            "governance.merge_plan", 1, emitted("implementation_plan.yaml", _yaml(plan), "yaml")
        ),
        answer(
            "governance.review_plan",
            1,
            "---\nreadiness: go\nsufficiency_score: 5\nblocker_unknowns: 0\n---\n\n"
            f"## Consolidated Plan\n\n{focus}.\n",
        ),
    ]


DONE = {
    "objective": "the increment's scenario",
    "acceptance_criteria": ["its scenario passes on the worker"],
    "non_goals": [],
    "time_budget_seconds": 300,
    "stop_conditions": [],
    "required_artifacts": [WORLD_PATH],
}


def _check(thing: str) -> str:
    """qa's test for the increment: the world holds ``thing``, a test file of its own."""
    return f"""import json
import unittest
from pathlib import Path

WORLD = Path(__file__).resolve().parents[1] / "{WORLD_PATH}"


class World(unittest.TestCase):
    def test_the_world_holds_{thing.split(".")[-1].lower()}(self):
        world = json.loads(WORLD.read_text())
        self.assertIn("{thing}", world["server"])"""


def _implementation(world: dict, thing: str) -> list[dict]:
    name = thing.split(".")[-1].lower()
    return [
        answer("governance.define_done", 1, emitted("definition_of_done.json", json.dumps(DONE))),
        answer("development.develop", 1, emitted(WORLD_PATH, json.dumps(world, indent=2))),
        answer("qa.test", 1, emitted(f"checks/check_{name}_test.py", _check(thing), "python")),
    ]


SCRIPTS = {
    "machinery-inc1": [
        answer(
            "strategy.propose_increment",
            1,
            _proposal(
                "C-2", "Clicking the panel's button opens the door", DOOR_OPENS, "Workspace.Door"
            ),
        ),
        *_framing("open the door from its panel"),
        *_implementation(OPEN, "Workspace.Door"),
    ],
    "machinery-inc2": [
        answer(
            "strategy.propose_increment",
            1,
            _proposal("C-3", "Clicking the switch lights the lamp", LAMP_LIGHTS, "Workspace.Lamp"),
        ),
        *_framing("light the lamp from its switch"),
        *_implementation(LIT_SHUT, "Workspace.Lamp"),
    ],
    "machinery-repair": _implementation(LIT_OPEN, "Workspace.Lamp"),
}


def _pinned(scripts_dir) -> list[str]:
    pinned = []
    for name, answers in SCRIPTS.items():
        raw = yaml.safe_dump(
            {"script": name, "description": "machinery Campaign", "answers": answers},
            sort_keys=False,
            width=1000,
        ).encode()
        (scripts_dir / f"{name}.yaml").write_bytes(raw)
        pinned.append(f"{name}@{script_version(raw)}")
    return pinned


async def _start(world) -> None:
    draft = campaign(
        CID,
        project_id=PROJECT,
        objective=dataclasses.replace(
            campaign().objective,
            statement="the door's world grows by scenario",
            allowed_scope=SCOPE,
            requirements="repo:file:README.md@current",
        ),
        policy=policy(
            proposal_profile="campaign-increment-source",
            squad_profile="machinery",
            max_repair_cycles_per_increment=1,
            llm_scripts=_pinned(world.scripts),
        ),
    )
    await world.campaigns.create_campaign(
        draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
    )
    projects = world.executor._project_registry
    record = await record_for(projects, projects.project, campaign_id=CID)
    await world.campaigns.transition(
        CID,
        start_transition(
            draft, actor="owner", actor_role="admin", reason="go", idempotency_key="start",
            record=record,
        ),
    )  # fmt: skip
    await world.progress.calibration_recorded(CID)


async def _rule(world, ruled: set) -> None:
    """Rule every gate waiting now, approving, as an operator's route does."""
    now = datetime.now(UTC)
    current = await world.campaigns.get_campaign(CID)
    if current.state is CampaignState.AWAITING_RULING and current.proposal is not None:
        run_id = current.proposal.run_id
        if run_id not in ruled:
            ruled.add(run_id)
            await world.campaigns.transition(
                CID,
                ruling_transition(
                    GateDecisionValue.APPROVED, current.proposal.binding, run_id=run_id,
                    actor="owner", actor_role="admin", reason="approved",
                    idempotency_key=f"rule-{run_id}",
                ),
            )  # fmt: skip
            run = await world.registry.get_run(run_id)
            await _decide(world, run, INCREMENT_RULING, now)
    for cycle in await world.registry.list_cycles(PROJECT):
        for run in await world.registry.list_runs(cycle.cycle_id):
            if (
                run.workload_type == "framing"
                and run.status == "completed"
                and run.run_id not in ruled
                and not any(d.gate_name == PLAN_REVIEW for d in run.gate_decisions)
            ):
                ruled.add(run.run_id)
                await _decide(world, run, PLAN_REVIEW, now)


async def _decide(world, run, gate: str, now) -> None:
    await record_gate_decision(
        world.registry, world.vault, world.executor._cycle_event_bus, project_id=PROJECT,
        cycle_id=run.cycle_id, run_id=run.run_id,
        decision=GateDecision(gate_name=gate, decision="approved", decided_by="owner",
                              decided_at=now, notes="approved"),
    )  # fmt: skip


async def _until_settled(world, *, seconds: float = 120) -> None:
    ruled: set = set()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while loop.time() < deadline:
        await _rule(world, ruled)
        current = await world.campaigns.get_campaign(CID)
        if current.state.value in ("completed", "escalated", "aborted", "failed"):
            return
        if not world.launch._running and current.state is not CampaignState.AWAITING_RULING:
            pending = await world.campaigns.pending_launch_intents()
            if not pending:
                return
        await asyncio.sleep(0.1)
    raise AssertionError("the Campaign didn't settle")


@pytest.fixture
async def machinery(tmp_path, monkeypatch):
    world = await compose(tmp_path, monkeypatch, campaign=True)
    yield world
    await world.broker.drained()


def _rows(log) -> list[str]:
    """The continuation table's row each decision took, in order (§10)."""
    return [e.reason.rsplit("§10 ", 1)[1] for e in log if "§10 row" in (e.reason or "")]


async def _evaluation(world, cycle_id: str) -> dict:
    [ref] = await world.vault.list_artifacts(
        cycle_id=cycle_id, artifact_type=INCREMENT_EVALUATION_ARTIFACT_TYPE
    )
    return json.loads((await world.vault.retrieve(ref.artifact_id))[1])


def _played(world, criterion: str, side: str) -> list:
    """Each operation that played ``criterion``'s scenario on ``side`` at delivery or baseline."""
    return [o for o in world.operations() if o.request.task_id.endswith(f":{criterion}:{side}")]


def _outcome(operation, assertion: str) -> str:
    [record] = [r for r in operation.result.records if r.assertion_id == assertion]
    return record.outcome.value


async def test_a_campaign_refuses_a_candidate_that_breaks_an_earlier_scenario_and_accepts_its_repair(
    machinery,
):
    """Bugs caught, each a seam a live Campaign crosses and its own test doesn't:
    - an increment's accepted scenario not pinned on the next launch, so the next candidate is
      never judged against it, or judged by a test instead of on the worker;
    - a candidate that passes its own scenario and breaks an earlier one accepted;
    - the refusal not routed to a repair, or the repair launched without the frozen scenario;
    - the repair's candidate judged on a tree other than the one it delivered, or the Campaign
      not completing when its second increment is accepted;
    - a gate decided by anything but the operator's ruling."""
    async with machinery.worker():
        await _start(machinery)
        await _until_settled(machinery)

    current = await machinery.campaigns.get_campaign(CID)
    assert current.state is CampaignState.COMPLETED
    log = await machinery.campaigns.control_log(CID)
    # The record proposes (5); increment one accepted proposes again (7); increment two rejected
    # is repaired (12); the repair accepted meets the objective (3).
    assert _rows(log) == ["row 5", "row 7", "row 12", "row 3"]

    cycles = sorted(await machinery.registry.list_cycles(PROJECT), key=lambda c: c.created_at)
    assert [c.kind for c in cycles] == ["increment", "increment", "repair"]
    one, two, repair = cycles
    runs = {
        c.cycle_id: [
            (r.workload_type, r.status) for r in await machinery.registry.list_runs(c.cycle_id)
        ]
        for c in cycles
    }
    for increment in (one, two):
        assert sorted(runs[increment.cycle_id]) == [
            ("framing", "completed"), ("implementation", "completed"), ("proposal", "completed"),
        ]  # fmt: skip
    assert runs[repair.cycle_id] == [("implementation", "completed")]

    first = await _evaluation(machinery, one.cycle_id)
    assert (first["verdict"], [d["criterion_id"] for d in first["discriminations"]]) == (
        "accepted", ["C-2"]
    )  # fmt: skip
    # Increment two: its own scenario discriminates, and increment one's, replayed on the same
    # candidate on the worker, is broken.
    second = await _evaluation(machinery, two.cycle_id)
    assert second["verdict"] == "rejected"
    assert [(d["criterion_id"], d["met"]) for d in second["discriminations"]] == [("C-3", True)]
    assert [(f["criterion_id"], f["held"], f["detail"]) for f in second["frozen"]] == [
        ("C-2", "broken", "door-open")
    ]
    # The repair: the frozen scenario is held and its own still discriminates.
    repaired = await _evaluation(machinery, repair.cycle_id)
    assert repaired["verdict"] == "accepted"
    assert [(f["criterion_id"], f["held"]) for f in repaired["frozen"]] == [("C-2", "held")]
    assert [(d["criterion_id"], d["met"]) for d in repaired["discriminations"]] == [("C-3", True)]

    # C-2 played on the worker on each candidate it judged: increment one's (as new), and
    # increment two's and the repair's (frozen), each on the tree that candidate delivered.
    played = _played(machinery, "C-2", "candidate")
    assert [json.loads(o.request.source_files[WORLD_PATH]) for o in played] == [
        OPEN, LIT_SHUT, LIT_OPEN
    ]  # fmt: skip
    assert [_outcome(o, "door-open") for o in played] == ["passed", "failed", "passed"]

    # The accepted tree the Campaign ends on is the repair's: the door open and the lamp lit.
    final = head(current, log)
    world = await machinery.clones.file_at(PROJECT, final.commit, WORLD_PATH)
    assert json.loads(world) == LIT_OPEN


async def test_a_campaign_whose_worker_is_offline_launches_no_development(machinery):
    """No worker serving when the Campaign starts. Bug caught: an increment whose work requires
    a worker tool created anyway, so its squad's work is spent with nothing to judge it."""
    await _start(machinery)

    current = await machinery.campaigns.get_campaign(CID)
    assert current.state is CampaignState.ESCALATED
    [refused] = [
        e
        for e in await machinery.campaigns.control_log(CID)
        if e.operation.value == "launch_refused"
    ]
    assert "fixture/declared_scenario" in refused.reason
    assert await machinery.registry.list_cycles(PROJECT) == []
    assert machinery.dispatched() == []


class _Comes:
    """A worker there at every launch and gone at every reading (#3045): it starts as each
    launch is drained, so creation finds it, and leaves the moment qa's operation reports, before
    the runtime reads the reply, so delivery's reading finds no one to take it."""

    def __init__(self, world) -> None:
        self.world = world
        self.serving = None
        self.arrivals = 0
        launch = world.launch.drain

        async def drain():
            await self.arrive()
            return await launch()

        world.launch.drain = drain
        world.broker.on_reply = self.reply

    async def arrive(self) -> None:
        if self.serving is None:
            self.arrivals += 1
            self.serving = self.world.worker(f"spark-worker-{self.arrivals}")
            await self.serving.__aenter__()

    async def leave(self) -> None:
        if self.serving is not None:
            serving, self.serving = self.serving, None
            await serving.__aexit__(None, None, None)

    async def reply(self, result: dict) -> None:
        sent = [
            m["payload"]["task_id"]
            for q, m in self.world.broker.published
            if q.endswith("_comms") and m["payload"]["task_type"] == "qa.run_remote_operation"
        ]
        if result["task_id"] in sent and result["status"] == "SUCCEEDED":
            await self.leave()


#: An increment's retry: framed and built again on its approved request, on the same answers.
RETRY_SCRIPTS = {
    "machinery-inc1": SCRIPTS["machinery-inc1"],
    "machinery-retry": [
        *_framing("open the door from its panel"),
        *_implementation(OPEN, "Workspace.Door"),
    ],
}


async def test_a_worker_there_at_every_launch_and_gone_at_every_reading_spends_the_retries(
    machinery, monkeypatch
):
    """#3045's done-when: the increment is retried for want of a worker, never repaired, within
    its retries, and the owner hears of it when they are spent. Bugs caught: the outage read as
    the work's failure (a repair cycle launched); the retries reset by each launch, so it
    relaunches for ever; or the retry launched without the scenario's reading flagged."""
    monkeypatch.setitem(globals(), "SCRIPTS", RETRY_SCRIPTS)
    comes = _Comes(machinery)
    try:
        await comes.arrive()
        await _start(machinery)
        await _until_settled(machinery)
    finally:
        await comes.leave()

    current = await machinery.campaigns.get_campaign(CID)
    assert current.state is CampaignState.ESCALATED
    log = await machinery.campaigns.control_log(CID)
    # The record proposes (5); the increment, blocked for want of a worker, is retried (10);
    # the retry, blocked the same way, escalates with its retries spent (11).
    assert _rows(log) == ["row 5", "row 10", "row 11"]
    cycles = sorted(await machinery.registry.list_cycles(PROJECT), key=lambda c: c.created_at)
    assert [c.kind for c in cycles] == ["increment", "retry"]
    for cycle in cycles:
        evaluation = await _evaluation(machinery, cycle.cycle_id)
        assert evaluation["verdict"] == "blocked_unverified"
        assert evaluation["blocked_only_by_availability"] is True
        [judged] = evaluation["discriminations"]
        assert (judged["criterion_id"], judged["reason"], judged["unavailable"]) == (
            "C-2", "not_run", True
        )  # fmt: skip
