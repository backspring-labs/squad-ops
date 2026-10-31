"""§10p ruling 13's reading tool (SIP-0113; #2564 step 6): named cycles evaluated against a named
suite through ``evaluate_cycle``, written with no campaign, and a fault-injected diagnostic tree
read by the same path.

The script runs in the runtime image, piped to ``python -``, so these tests enter at its ``read()``
with the evaluation service's own code beneath it, and only the tree read, the runner and the
campaign's log faked.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.models import ControlOperation, ControlOutcome
from squadops.scenarios import evaluate
from squadops.scenarios.evaluation import ScenarioResult
from squadops.scenarios.models import parse_suite
from squadops.scenarios.runner import TreeEvaluation
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import approve_suite, draft_suite
from tests.unit.scenarios.suite_fixtures import SUITE

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "read_scenarios.py"
T0 = datetime(2026, 10, 22, 6, 0, tzinfo=UTC)
TREE = {"backend/main.py": b"app = 1\n", "frontend/index.html": b"<button>Go</button>\n"}
CAL_TREE = "c" * 64


def _load():
    spec = importlib.util.spec_from_file_location("read_scenarios", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["read_scenarios"] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class _Row:
    binding: dict
    operation: ControlOperation = ControlOperation.PROMOTE
    outcome: ControlOutcome = ControlOutcome.APPLIED


class _Campaigns:
    def __init__(self, log=()):
        self.log, self.read = list(log), []

    async def control_log(self, campaign_id):
        self.read.append(campaign_id)
        return self.log


class _Cycle:
    def __init__(self, cycle_id, *, campaign_id="cmp_read00000001", built_on=None):
        self.cycle_id, self.project_id, self.campaign_id = cycle_id, "group_run", campaign_id
        self._config = {"build_profile": "fullstack_fastapi_react"}
        if built_on:
            self._config["campaign_proposal"] = {"accepted_cycle_id": built_on}

    def resolved_config(self):
        return self._config


class _Vault:
    async def list_artifacts(self, *, cycle_id):
        return []  # no stored manifest

    async def retrieve(self, artifact_id):
        return None, TREE[artifact_id]


class _Runner:
    """Passes every scenario, or starts nothing; keeps the tree each evaluation was handed."""

    def __init__(self, *, started=True):
        self.trees, self._started = [], started

    async def evaluate_tree(self, **kw):
        self.trees.append(kw["tree"])
        runs = tuple(
            ScenarioRun(s["scenario_id"], "passed", steps_taken=1) for s in kw["scenarios"]
        )
        return TreeEvaluation(
            kw["tree_identity"], started=self._started, runs=runs if self._started else ()
        )


@pytest.fixture
async def world(monkeypatch):
    module = _load()

    async def tree_refs(vault, cycle):
        return {path: path for path in TREE}

    # The tree read the service and the fault share, faked once for both.
    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    monkeypatch.setattr(module, "evaluated_tree_refs", tree_refs)
    store = MemoryScenarioStore()
    suite = parse_suite(SUITE)
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="supervisor", at=T0)
    return module, store, suite


async def _read(module, store, suite, runner, **kw):
    kw.setdefault("campaigns", _Campaigns([_Row({"cycle_id": "cyc_cal", "identity": CAL_TREE})]))
    return await module.read(
        store=store,
        runner=runner,
        vault=_Vault(),
        suite_digest=suite.digest,
        clock=lambda: T0,
        **kw,
    )


async def test_each_reading_is_the_services_record_written_with_no_campaign_and_no_goal(world):
    """Bug caught: a reading written under the cycle's campaign (its package would then count a
    suite it never pinned), one that names no tree it built on, a round dropped, or a goal in the
    output, which goes to the window's records and the Release."""
    module, store, suite = world
    runner = _Runner()
    cycle = _Cycle("cyc_inc", built_on="cyc_cal")

    doc = await _read(module, store, suite, runner, cycles=[cycle], times=2)

    records = await store.evaluations_for_cycle("cyc_inc")
    assert [(r.campaign_id, r.suite_digest) for r in records] == [(None, suite.digest)] * 2
    assert {r.previous_accepted_tree_identity for r in records} == {CAL_TREE}
    assert [(r["round"], r["evaluation"], r["started"]) for r in doc["readings"]] == [
        (n, rec.evaluation_id, True) for n, rec in enumerate(records, start=1)
    ]
    assert [o["result"] for o in doc["readings"][0]["outcomes"]] == [
        ScenarioResult.PASSED.value
    ] * len(SUITE["scenarios"])
    text = json.dumps(doc)
    assert not [s["goal"] for s in SUITE["scenarios"] if s["goal"] in text]
    assert runner.trees == [TREE, TREE]


async def test_a_fault_is_read_by_the_same_path_on_its_own_tree_and_named_a_diagnostic(world):
    """Ruling 13, #1251's rule. Bug caught: the runner handed the original tree (the diagnostic
    then reads the outcome the fault was meant to remove), the record named by the tree it was
    made from, or the edit leaking into another cycle's reading."""
    module, store, suite = world
    runner = _Runner()
    edits = [{"path": "frontend/index.html", "old": "<button>Go</button>", "new": ""}]
    spec = {"diagnostic": "its only control removed", "cycle_id": "cyc_cal", "edits": edits}
    edited = {**TREE, "frontend/index.html": b"\n"}

    doc = await _read(
        module,
        store,
        suite,
        runner,
        cycles=[_Cycle("cyc_other")],
        times=1,
        fault=(_Cycle("cyc_cal"), spec),
    )

    plain, diagnostic = doc["readings"]
    assert runner.trees == [TREE, edited]
    assert "diagnostic" not in plain
    assert diagnostic["tree"] == FileTree.of(edited).identity != plain["tree"]
    assert diagnostic["diagnostic"] == {
        "what": "its only control removed",
        "made_from": FileTree.of(TREE).identity,
        "edited": ["frontend/index.html"],
    }
    [record] = await store.evaluations_for_cycle("cyc_cal")
    assert record.evaluated_tree_identity == diagnostic["tree"]


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        ({"path": "frontend/missing.html", "old": "x"}, "isn't in cyc_cal's tree"),
        ({"path": "frontend/index.html", "old": "<a>"}, "occurs 0 times"),
        ({"path": "frontend/index.html", "old": "button"}, "occurs 2 times"),
    ],
)
async def test_a_fault_that_doesnt_apply_is_refused_before_anything_runs(world, edit, why):
    """Bug caught: a fault whose text isn't there read as a diagnostic of an unchanged tree (its
    outcome then reads as the fault's), or one that matches twice changing more than it names."""
    module, store, suite = world
    runner = _Runner()
    spec = {"diagnostic": "d", "cycle_id": "cyc_cal", "edits": [edit]}

    with pytest.raises(ValueError, match=why):
        await _read(
            module, store, suite, runner, cycles=[_Cycle("cyc_x")], times=1,
            fault=(_Cycle("cyc_cal"), spec),
        )  # fmt: skip

    assert runner.trees == []
    assert await store.evaluations_for_cycle("cyc_x") == []


async def test_a_tree_that_never_started_reads_not_started_and_a_standalone_reads_no_log(world):
    """Bug caught: a reading whose tree never started exits 0, so a series reads its blocked rows
    as results; or a cycle with no campaign asking for a campaign's log."""
    module, store, suite = world
    campaigns = _Campaigns()

    doc = await _read(
        module,
        store,
        suite,
        _Runner(started=False),
        campaigns=campaigns,
        cycles=[_Cycle("cyc_solo", campaign_id=None)],
        times=1,
    )

    [reading] = doc["readings"]
    assert (reading["started"], reading["built_on"], campaigns.read) == (False, None, [])


@pytest.mark.parametrize(
    "argv",
    [
        ["sha256:abc"],
        ["sha256:abc", "cyc_a", "--times", "0"],
        ["sha256:abc", "--fault", '{"diagnostic": "d", "cycle_id": "cyc_a", "edits": []}'],
        ["sha256:abc", "--fault", '{"cycle_id": "cyc_a", "edits": [{"path": "p", "old": "o"}]}'],
        ["sha256:abc", "--fault", "[1]"],
    ],
)
def test_a_reading_with_nothing_to_read_or_a_malformed_fault_is_a_usage_error(argv):
    """Bug caught: a run that opens the deploy's database and reads nothing, or a fault spec
    missing its name or its edits reaching the vault."""
    with pytest.raises(SystemExit) as raised:
        _load().parse(argv)
    assert raised.value.code == 2
