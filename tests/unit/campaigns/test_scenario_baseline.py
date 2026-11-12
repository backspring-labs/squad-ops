"""The baseline step: each scenario played on the accepted baseline before development (#3044 2b).

Entered at ``judge_scenario_baselines``, which the executor's ``_judge_scenario_baselines`` calls
before a run's first dispatch, and at that method for the run's ending. The pin's checkout is the
fixture world the remote-execution fixture reads; the port runs ``fixture/declared_scenario`` in
process. How a run's ``ScenarioRuns`` is built (its operation, vocabulary and ids) is delivery's
own function, tested with it, so here it is the delivery tests' one.
"""

from __future__ import annotations

import dataclasses
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.remote_execution.fixture_operation_runner import WORLD_PATH
from squadops.campaigns.change_request import stored_change_request, validate_proposal
from squadops.campaigns.evaluator_trees import FileTree
from squadops.cycles.failure_attribution import TerminalKind
from squadops.execution import scenario_baseline
from squadops.execution.execution_errors import _ExecutionError
from squadops.execution.product_acceptance import baseline_scenario_overlay
from squadops.projects.models import CheckoutTree
from squadops.projects.source_context import parse_source_context
from squadops.remote_execution.models import ASSERTION_RECORDS_ARTIFACT_TYPE
from squadops.remote_execution.scenario import BaselineVerdict, staged_revision
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.campaigns.test_product_increment_seams import _cycle
from tests.unit.campaigns.test_runner_acceptance_sandbox import _profile
from tests.unit.campaigns.test_scenario_criterion import _ctx
from tests.unit.campaigns.test_scenario_criterion import _request as scenario_request
from tests.unit.campaigns.test_scenario_delivery import SOURCE, _Port, _scenarios
from tests.unit.remote_execution.scenario_fixture import OPEN, SHUT

pytestmark = [pytest.mark.domain_orchestration]

REQUEST = stored_change_request(validate_proposal(scenario_request(), _ctx()).change_request)


class _Vault:
    def __init__(self) -> None:
        self.stored: list[tuple[object, bytes]] = []

    async def store(self, ref, content):
        self.stored.append((ref, content))
        return ref


def _cycle_at_pin():
    return dataclasses.replace(
        _cycle(), source_context=parse_source_context(recorded("project_source_context", "valid"))
    )


async def _judge(monkeypatch, head: dict[str, bytes]):
    """The baseline step on a pin whose checkout is ``head``, through the in-process port."""
    port, vault = _Port(), _Vault()

    async def runs(*_args):
        return _scenarios(port)

    monkeypatch.setattr(scenario_baseline, "scenario_runs_for", runs)
    monkeypatch.setattr(
        scenario_baseline, "approved_change_request", AsyncMock(return_value=REQUEST)
    )
    repository = AsyncMock()
    repository.tree_at.return_value = CheckoutTree(
        "c" * 40, head, frozenset(), frozenset(), frozenset()
    )
    registry = AsyncMock()
    registry.get_project.return_value = SimpleNamespace(source=SimpleNamespace(base_ref="main"))

    judged = await scenario_baseline.judge_scenario_baselines(
        _cycle_at_pin(),
        "run_impl",
        ("C-2",),
        vault=vault,
        remote_execution=port,
        repository=repository,
        registry=registry,
        read_profile=AsyncMock(return_value=_profile()),
    )
    return judged, port, vault


def _head(world: dict | None) -> dict[str, bytes]:
    return {**SOURCE, **({WORLD_PATH: json.dumps(world).encode()} if world is not None else {})}


async def test_a_scenario_that_fails_on_the_baseline_may_start_and_its_reading_is_kept(monkeypatch):
    """Bugs caught: the scenario played on a tree other than the overlay delivery judges, so the
    reading is never credited there; the reading not kept, or kept as the candidate's; or
    development held back by a scenario that does fail on the baseline."""
    head = _head(SHUT)

    [judgement], port, vault = await _judge(monkeypatch, head)

    assert judgement.verdict is BaselineVerdict.MAY_START
    assert scenario_baseline.baseline_ending([judgement]) is None
    [asked] = port.asked
    overlay = baseline_scenario_overlay(
        _cycle_at_pin(), REQUEST, "C-2", accepted=FileTree.of(head), profile=_profile()
    )
    staged = {p: c.decode() for p, c in overlay.as_dict().items()}
    assert asked.source_files == staged
    assert asked.task_id.endswith(":C-2:baseline")
    [(ref, content)] = vault.stored
    document = json.loads(content)
    assert (ref.artifact_type, ref.cycle_id, ref.run_id) == (
        ASSERTION_RECORDS_ARTIFACT_TYPE,
        "cyc_inc",
        "run_impl",
    )
    assert (document["side"], document["source_revision"]) == ("baseline", staged_revision(staged))


@pytest.mark.parametrize(
    ("world", "verdict", "kind", "says"),
    [
        (
            OPEN,
            BaselineVerdict.PASSES_ON_BASELINE,
            TerminalKind.CRITERIA_NOT_CHECKABLE,
            "door-open already passes on the baseline",
        ),
        (
            {**SHUT, "client": {}},
            BaselineVerdict.BLOCKED,
            TerminalKind.INFRASTRUCTURE_FAILED,
            "spawned (setup_failed)",
        ),
        (
            None,
            BaselineVerdict.BLOCKED,
            TerminalKind.INFRASTRUCTURE_FAILED,
            f"no world is staged at {WORLD_PATH}",
        ),
    ],
    ids=["already passes", "setup not established", "not executed"],
)
async def test_a_scenario_that_cant_check_the_work_ends_the_run_before_any_dispatch(
    monkeypatch, world, verdict, kind, says
):
    """Bugs caught: development started on a scenario that already passes, so the increment is
    accepted for work it didn't do; or on one that was never read, so its later pass means
    nothing; or a scenario that wasn't read sent back to its author as if it had passed."""
    [judgement], _port, _vault = await _judge(monkeypatch, _head(world))

    ending = scenario_baseline.baseline_ending([judgement])

    assert judgement.verdict is verdict
    assert isinstance(ending, _ExecutionError)
    assert ending.terminal.kind is kind
    assert says in str(ending)


def test_a_scenario_refused_to_its_author_outranks_one_not_read():
    """Bug caught: an increment with one scenario already met and one not read retried, when it
    is re-proposed either way."""
    ending = scenario_baseline.baseline_ending(
        [
            scenario_baseline.BaselineJudgement("C-1", BaselineVerdict.BLOCKED, "no worker"),
            scenario_baseline.BaselineJudgement("C-2", BaselineVerdict.PASSES_ON_BASELINE, "met"),
        ]
    )

    assert ending.terminal.kind is TerminalKind.CRITERIA_NOT_CHECKABLE
    assert "C-2: met" in str(ending) and "C-1" not in str(ending)


async def test_the_executor_reads_scenarios_its_plan_plays_and_ends_the_run_on_the_verdict(
    monkeypatch,
):
    """The executor's side, entered at ``_judge_scenario_baselines``. Bugs caught: a plan whose
    appended operation steps play scenarios started without its baseline read; a plan with none
    asked for one; or a baseline that can't be read at all left to start work."""
    from squadops.execution import dispatched_flow_executor
    from squadops.tasks.models import TaskEnvelope

    def envelope(task_type, inputs):
        return TaskEnvelope(
            task_id=task_type, agent_id="eve", cycle_id="cyc_inc", pulse_id="p",
            project_id="prj-tally", task_type=task_type, correlation_id="c", causation_id="c",
            trace_id="t", span_id="s", inputs=inputs,
        )  # fmt: skip

    plan = [
        envelope("development.develop", {}),
        envelope("qa.run_remote_operation", {"operation_scenario": {"scenario_id": "C-2"}}),
    ]
    asked = []

    async def judge(cycle, run_id, criteria, **_ports):
        asked.append(criteria)
        raise ValueError("no managed clone")

    monkeypatch.setattr(dispatched_flow_executor, "judge_scenario_baselines", judge)
    executor = SimpleNamespace(
        _artifact_vault=None, _remote_execution=None, _source_repository=None,
        _project_registry=None, _derived_profile_for=None,
    )  # fmt: skip
    method = dispatched_flow_executor.DispatchedFlowExecutor._judge_scenario_baselines

    await method(executor, _cycle_at_pin(), "run_impl", plan[:1])
    with pytest.raises(_ExecutionError, match="C-2 can't be read on the accepted baseline") as e:
        await method(executor, _cycle_at_pin(), "run_impl", plan)

    assert asked == [("C-2",)]
    assert e.value.terminal.kind is TerminalKind.INFRASTRUCTURE_FAILED
