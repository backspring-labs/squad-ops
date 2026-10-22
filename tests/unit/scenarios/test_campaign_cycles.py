"""Each campaign cycle evaluated at its end against its campaign's pinned suite (SIP-0113 §4.1;
#2414). The wiring through the completion hook is ``tests/unit/campaigns/test_progress.py``'s
``test_each_built_ending_is_evaluated_before_its_decision_against_the_tree_it_built_on``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.campaigns.models import ControlOperation, ControlOutcome
from squadops.scenarios import campaign_cycles
from squadops.scenarios.campaign_cycles import CampaignCycleEvaluator, promoted_identity
from squadops.scenarios.evaluate import evaluate_cycle
from squadops.scenarios.evaluation import BlockedReason, ScenarioResult
from squadops.scenarios.models import CampaignSuitePin, parse_suite
from squadops.scenarios.runner import TreeEvaluation
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import approve_suite, draft_suite

T0 = datetime(2026, 10, 19, 2, 0, tzinfo=UTC)
CID = "cmp_eval00000001"
CAL_TREE = "a" * 64
OTHER_TREE = "b" * 64


def _suite(name: str):
    return parse_suite(
        {
            "name": name,
            "scenarios": [
                {
                    "scenario_id": "runs-list",
                    "goal": "The runs are listed.",
                    "surfaces": [{"kind": "http_endpoint", "method": "GET", "path": "/runs"}],
                    "steps": [{"action": "http", "method": "GET", "path": "/runs"}],
                    "checks": [{"check": "status", "step": 1, "equals": 200}],
                }
            ],
        }
    )


@dataclass
class _Row:
    target: str
    binding: dict
    operation: ControlOperation = ControlOperation.PROMOTE
    outcome: ControlOutcome = ControlOutcome.APPLIED


@dataclass
class _Campaigns:
    log: list = field(default_factory=list)

    async def control_log(self, campaign_id):
        return self.log


class _Cycle:
    def __init__(self, cycle_id="cyc_inc", *, campaign_id=CID, config=None):
        self.cycle_id, self.project_id, self.campaign_id = cycle_id, "group_run", campaign_id
        self._config = {"build_profile": "fullstack_fastapi_react"} if config is None else config

    def resolved_config(self):
        return self._config


class _Runner:
    def __init__(self):
        self.trees: list[str] = []

    async def evaluate_tree(self, **kw):
        self.trees.append(kw["tree_identity"])
        runs = tuple(
            ScenarioRun(s["scenario_id"], "passed", steps_taken=1) for s in kw["scenarios"]
        )
        return TreeEvaluation(kw["tree_identity"], started=True, runs=runs)


class _Vault:
    """A delivered tree with no interface manifest stored beside it."""

    async def list_artifacts(self, *, cycle_id):
        return []

    async def retrieve(self, artifact_id):
        return None, b"app = 1\n"


async def _world(monkeypatch, *, pinned=True, tree=True, log=()):
    async def tree_refs(vault, cycle):
        return {"backend/main.py": "art_main"} if tree else {}

    monkeypatch.setattr(campaign_cycles, "evaluated_tree_refs", tree_refs)
    monkeypatch.setattr("squadops.scenarios.evaluate.evaluated_tree_refs", tree_refs)
    store, suite = MemoryScenarioStore(), _suite("group_run")
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)
    if pinned:
        await store.save_pin(CampaignSuitePin(CID, suite.digest, pinned_by="owner", pinned_at=T0))
    runner = _Runner()
    evaluator = CampaignCycleEvaluator(
        store=store,
        runner=runner,
        vault=_Vault(),
        campaigns=_Campaigns(list(log)),
        clock=lambda: T0,
    )
    return evaluator, store, runner, suite


@pytest.mark.parametrize(
    ("cycle", "pinned", "tree"),
    [
        (_Cycle(campaign_id=None), True, True),
        (_Cycle(), False, True),
        (_Cycle(), True, False),
    ],
    ids=["no-campaign", "no-suite-pinned", "no-delivered-tree"],
)
async def test_nothing_to_evaluate_writes_no_record_and_runs_nothing(
    monkeypatch, cycle, pinned, tree
):
    """Bug caught: a standalone cycle, or a campaign created without a suite, evaluated against
    nothing (a crash in the hearing); or a cycle that delivered nothing started as an empty app,
    whose ``start_failed`` reads as the product's failure."""
    evaluator, store, runner, _ = await _world(monkeypatch, pinned=pinned, tree=tree)

    assert await evaluator.cycle_ended(cycle) is None
    assert await store.evaluations_for_cycle(cycle.cycle_id) == []
    assert runner.trees == []


async def test_a_cycle_heard_again_is_evaluated_once_per_suite(monkeypatch):
    """§12a: a process that stops between the evaluation and the decision hears the cycle again
    at startup. Bug caught: a second record of the same cycle and suite, so a reading counts its
    outcomes twice."""
    evaluator, store, runner, _ = await _world(monkeypatch)

    first = await evaluator.cycle_ended(_Cycle())
    again = await evaluator.cycle_ended(_Cycle())

    assert again is None
    assert [r.evaluation_id for r in await store.evaluations_for_cycle("cyc_inc")] == [
        first.evaluation_id
    ]
    assert len(runner.trees) == 1


async def test_a_reading_written_with_no_campaign_isnt_the_cycles_evaluation(monkeypatch):
    """§10p ruling 13's reading tool writes records with no campaign. Bug caught: its record of
    the campaign's own suite, written before the cycle's end is heard, taken for the cycle's
    evaluation, so its campaign never evaluates it."""
    evaluator, store, runner, suite = await _world(monkeypatch)
    await evaluate_cycle(
        store=store,
        runner=runner,
        vault=_Vault(),
        cycle=_Cycle(),
        suite_digest=suite.digest,
        campaign_id=None,
        previous_accepted_tree_identity=None,
        evaluated_at=T0,
    )

    record = await evaluator.cycle_ended(_Cycle())

    assert (record.campaign_id, len(runner.trees)) == (CID, 2)


async def test_an_increment_names_the_tree_its_campaign_promoted_for_what_it_built_on(monkeypatch):
    """Bug caught: the previous tree read from the campaign's latest promotion (the increment's
    own, once it is accepted), or from a refused row, so contribution compares a tree with
    itself."""
    log = [
        _Row(
            "cyc_cal",
            {"cycle_id": "cyc_cal", "identity": OTHER_TREE},
            outcome=ControlOutcome.REFUSED,
        ),
        _Row("cyc_cal", {"cycle_id": "cyc_cal", "identity": CAL_TREE}),
        _Row("cyc_inc", {"cycle_id": "cyc_inc", "identity": OTHER_TREE}),
    ]
    evaluator, *_ = await _world(monkeypatch, log=log)
    increment = _Cycle(
        config={
            "build_profile": "fullstack_fastapi_react",
            "campaign_proposal": {"accepted_cycle_id": "cyc_cal"},
        }
    )

    record = await evaluator.cycle_ended(increment)

    assert record.previous_accepted_tree_identity == CAL_TREE
    assert record.campaign_id == CID
    assert promoted_identity(log, None) is None
    assert promoted_identity(log, "cyc_missing") is None


async def test_a_project_with_no_stack_is_blocked_on_its_start_declaration(monkeypatch):
    """SIP-0112 §8.3: a Project that isn't a blueprint starts only by its Development
    Configuration's declaration, which the hook doesn't read yet. Bug caught: such a cycle
    started by a sample stack's commands, or recorded as having no runner."""
    evaluator, _, runner, _ = await _world(monkeypatch)

    record = await evaluator.cycle_ended(_Cycle(config={}))

    [outcome] = record.outcomes
    assert (outcome.result, outcome.blocked_reason) == (
        ScenarioResult.BLOCKED_UNVERIFIED,
        BlockedReason.NO_START_DECLARATION,
    )
    assert runner.trees == []
