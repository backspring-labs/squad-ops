"""A repository-backed Project's campaign cycle, evaluated at its end from its own declared start
(SIP-0113 §4.1, §10l; SIP-0112 contract 7; #2414's remainder).

Entered where the live campaign enters: ``CampaignProgress.cycle_ended``, whose hearing evaluates
each ending before it decides it (``_outcome_evaluated``). The world is the shared fixture's Tally,
in a real managed clone, with an increment delivered for real (verified by Tally's checks and
captured in the clone, its mapping recorded), so the tree evaluated is the capture's. The runner
records what it was asked to start, and passes each scenario it runs.

What bugs would these catch?
- a repository-backed cycle evaluated on the vault's files, which are only the squad's changes, so
  the record names a tree that isn't the product's;
- the product started by anything but its own declaration, at another revision, or without its
  executable bits;
- the previous tree named by something other than the head the cycle was built on;
- a declaration that can't run (none, a secret nobody approved) passing scenarios, or reading
  them not applicable, rather than blocked with contract 7's reason;
- a cycle that captured nothing evaluated as an empty app.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.progress import decision_key
from squadops.cycles.cycle_end import CycleStopReason
from squadops.scenarios.campaign_cycles import CampaignCycleEvaluator
from squadops.scenarios.evaluation import BlockedReason, ScenarioResult
from squadops.scenarios.models import CampaignSuitePin, parse_suite
from squadops.scenarios.runner import TreeEvaluation
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import approve_suite, draft_suite
from tests.fixtures.shared_contract.repository import tracked_files
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.campaigns.test_campaign_branch import CID, _added, _World

T0 = datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
SUITE = parse_suite(
    {
        "name": "tally-heldout-invented",
        "scenarios": [
            {
                "scenario_id": "counter-total",
                "goal": "A counter's total is read back.",
                "surfaces": [{"kind": "http_endpoint", "method": "GET", "path": "/counters"}],
                "steps": [{"action": "http", "method": "GET", "path": "/counters"}],
                "checks": [{"check": "status", "step": 1, "equals": 200}],
            },
            {
                "scenario_id": "counter-page",
                "goal": "The counters page lists them.",
                "surfaces": [{"kind": "page", "path": "/"}],
                "steps": [{"action": "visit", "path": "/"}],
                "checks": [{"check": "text", "step": 1, "pattern": "apples"}],
            },
        ],
    }
)


class _Runner:
    """Records each start it's asked for, and passes every scenario it runs."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def evaluate_tree(self, **kw):
        self.calls.append(kw)
        runs = tuple(
            ScenarioRun(s["scenario_id"], "passed", steps_taken=1) for s in kw["scenarios"]
        )
        return TreeEvaluation(
            kw["tree_identity"],
            started=True,
            runs=runs,
            configuration_revision=kw["declared"].configuration_revision,
        )


def _without_secret(configuration):
    start = dataclasses.replace(configuration.commands.start, evaluation_environment=())
    return dataclasses.replace(
        configuration, commands=dataclasses.replace(configuration.commands, start=start)
    )


async def _heard(tmp_path, *, configure=None, deliver=True, projects=None, repository=None):
    """Tally's campaign started, one increment delivered (or not), and its ending heard by the
    completion path the runtime builds, with the evaluator the runtime builds."""
    world = _World(tmp_path)
    if configure is not None:
        world.projects.configuration = configure(world.projects.configuration)
    await world.started()
    store = MemoryScenarioStore()
    await draft_suite(store, SUITE, actor="supervisor", at=T0)
    await approve_suite(store, SUITE.digest, actor="owner", at=T0)
    await store.save_pin(CampaignSuitePin(CID, SUITE.digest, pinned_by="owner", pinned_at=T0))
    runner = _Runner()
    evaluator = CampaignCycleEvaluator(
        store=store,
        runner=runner,
        vault=world.vault,
        campaigns=world.campaigns,
        clock=lambda: T0,
        projects=projects(world.projects) if projects else world.projects,
        repository=repository(world.clones) if repository else world.clones,
    )
    progress = world.progress_on(world.clones)
    progress._evaluate_outcome = evaluator.cycle_ended
    if deliver:
        cycle, run, captured = await world.delivered("cyc_inc000000001", _added("total"))
    else:
        cycle, run, captured = await _undelivered(world)
    world.decision = await progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)
    records = await store.evaluations_for_cycle(cycle.cycle_id)
    return world, runner, records, captured


async def _undelivered(world):
    """An increment whose run captured nothing: its capture is another cycle's."""
    cycle, run, captured = await world.delivered("cyc_inc000000001", _added("total"))
    world.projects.mappings = [
        dataclasses.replace(m, cycle_id="cyc_other0000001") if m.cycle_id == cycle.cycle_id else m
        for m in world.projects.mappings
    ]
    return cycle, run, captured


async def test_a_product_cycle_is_evaluated_on_its_capture_started_from_its_declaration(tmp_path):
    """#2414's remainder end to end. Bugs caught: the vault's partial tree evaluated; the start
    not the declared one, or at another revision; the executable bits dropped; the previous tree
    not the head it was pinned at."""
    world, runner, [record], captured = await _heard(tmp_path, configure=_without_secret)

    checkout = await world.clones.tree_at(PROJECT, captured)
    capture = checkout.files
    head = tracked_files(world.repo.path, world.repo.second_commit)
    [call] = runner.calls
    assert record.evaluated_tree_identity == call["tree_identity"] == FileTree.of(capture).identity
    assert record.previous_accepted_tree_identity == FileTree.of(head).identity
    declared = call["declared"]
    assert (declared.start, declared.setup, declared.configuration_revision) == (
        ("python3", "-m", "tally", "serve", "--host", "0.0.0.0", "--port", "18407"),
        (("python3", "tools/build.py"),),
        1,
    )
    assert (declared.port, declared.ready_path, declared.api_port) == (18407, "/healthz", 18407)
    assert (call["stack"], call["environment"]) == (None, {})
    assert set(call["executable"]) == set(checkout.executable)
    # Tally declares an http_base and no ui_base: its HTTP scenario runs, its page one doesn't apply.
    by_id = {o.scenario_id: o for o in record.outcomes}
    assert by_id["counter-total"].result is ScenarioResult.PASSED
    assert str(by_id["counter-page"].applicability) == "not_applicable"


@pytest.mark.parametrize(
    ("configure", "reason"),
    [
        (None, BlockedReason.SECRET_NOT_AVAILABLE),
        (
            lambda c: dataclasses.replace(c, commands=dataclasses.replace(c.commands, start=None)),
            BlockedReason.NO_START_DECLARATION,
        ),
    ],
    ids=["tallys-own-secret-nobody-approved", "no-start-declaration"],
)
async def test_a_declaration_that_cant_run_blocks_every_applicable_scenario(
    tmp_path, configure, reason
):
    """Contract 7's reasons (SIP-0112 §8.2.1): nothing is started, and every applicable scenario
    is blocked with the reason, never passed and never not applicable. Tally's recorded start
    declares an evaluation secret, which no approval record releases before #2421."""
    _world, runner, [record], _captured = await _heard(tmp_path, configure=configure)

    assert runner.calls == []
    applicable = [o for o in record.outcomes if str(o.applicability) == "applicable"]
    assert applicable
    assert {(o.result, o.blocked_reason) for o in applicable} == {
        (ScenarioResult.BLOCKED_UNVERIFIED, reason)
    }


async def test_a_product_cycle_that_captured_nothing_writes_no_record(tmp_path):
    """Bugs caught: a cycle that delivered nothing evaluated on the vault's partial tree, or on
    another cycle's capture, or started as an empty app whose failure reads as the product's."""
    _world, runner, records, _captured = await _heard(
        tmp_path, configure=_without_secret, deliver=False
    )

    assert (records, runner.calls) == ([], [])


async def test_a_capture_whose_tree_isnt_the_recorded_one_writes_no_record(tmp_path):
    """Contract 4: the mapping names the commit's tree identity. Bug caught: a record naming a
    tree other than the one the capture verified."""
    world = _World(tmp_path)
    world.projects.configuration = _without_secret(world.projects.configuration)
    await world.started()
    cycle, run, _captured = await world.delivered("cyc_inc000000001", _added("total"))
    world.projects.mappings = [
        dataclasses.replace(m, tree_identity="0" * 64) if m.cycle_id == cycle.cycle_id else m
        for m in world.projects.mappings
    ]
    store = MemoryScenarioStore()
    await draft_suite(store, SUITE, actor="supervisor", at=T0)
    await approve_suite(store, SUITE.digest, actor="owner", at=T0)
    await store.save_pin(CampaignSuitePin(CID, SUITE.digest, pinned_by="owner", pinned_at=T0))
    runner = _Runner()
    evaluator = CampaignCycleEvaluator(
        store=store, runner=runner, vault=world.vault, campaigns=world.campaigns,
        clock=lambda: T0, projects=world.projects, repository=world.clones,
    )  # fmt: skip

    assert await evaluator.cycle_ended(cycle) is None
    assert runner.calls == []


async def test_a_tree_handed_in_is_evaluated_whole_with_its_executable_bits(tmp_path):
    """``evaluate_cycle``'s tree, as the hook hands a capture in. Tally tracks no executable file,
    so this holds the bits on an invented tree. Bugs caught: a handed-in tree replaced by the
    vault's; its executable bits dropped, so a product whose start is a script can't start."""
    from squadops.scenarios.evaluate import evaluate_cycle
    from squadops.scenarios.models import SurfaceKind
    from squadops.scenarios.runner import DeclaredStart

    class _Cycle:
        cycle_id, project_id, campaign_id = "cyc_x", "prj-x", CID

        def resolved_config(self):
            return {}

    class _NoVault:
        async def list_artifacts(self, **kw):
            raise AssertionError("a handed-in tree is never read from the vault")

    store = MemoryScenarioStore()
    await draft_suite(store, SUITE, actor="supervisor", at=T0)
    await approve_suite(store, SUITE.digest, actor="owner", at=T0)
    runner = _Runner()
    tree = {"run.sh": b"#!/bin/sh\nexec python3 -m shelf\n", "shelf/__init__.py": b""}
    start = DeclaredStart(("./run.sh",), 8000, "http", "/healthz", 5.0, api_port=8000)

    record = await evaluate_cycle(
        store=store, runner=runner, vault=_NoVault(), cycle=_Cycle(), suite_digest=SUITE.digest,
        campaign_id=CID, previous_accepted_tree_identity=None, evaluated_at=T0, declared=start,
        served=frozenset(), tree=tree, executable={"run.sh"},
    )  # fmt: skip

    assert record.evaluated_tree_identity == FileTree.of(tree).identity
    # No surface is served, so nothing applies and nothing is started.
    assert runner.calls == []
    served = await evaluate_cycle(
        store=store, runner=runner, vault=_NoVault(), cycle=_Cycle(), suite_digest=SUITE.digest,
        campaign_id=CID, previous_accepted_tree_identity=None, evaluated_at=T0, declared=start,
        served=frozenset({SurfaceKind.HTTP_ENDPOINT}),
        tree=tree, executable={"run.sh"},
    )  # fmt: skip
    assert served.evaluated_tree_identity == FileTree.of(tree).identity
    [call] = runner.calls
    assert (call["tree"], call["executable"]) == (tree, ["run.sh"])


def test_the_runtime_root_hands_the_evaluator_the_registry_and_the_clone():
    """Bug caught: the root building the evaluator with no registry or clone, so every product
    cycle is skipped at its end while each test, built on its own world, stays green."""
    import ast
    from pathlib import Path

    main = Path(__file__).resolve().parents[3] / "src/squadops/api/runtime/main.py"
    [call] = [
        node
        for node in ast.walk(ast.parse(main.read_text()))
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "CampaignCycleEvaluator"
    ]
    passed = {k.arg: ast.unparse(k.value) for k in call.keywords}
    assert (passed["projects"], passed["repository"]) == (
        "project_registry",
        "state.source_repository",
    )


class _Delegate:
    """A registry or a clone whose one named read fails, every other read passing through."""

    def __init__(self, inner, failing: str, error: Exception) -> None:
        self._inner, self._failing, self._error = inner, failing, error

    def __getattr__(self, name):
        if name == self._failing:

            async def fails(*args, **kwargs):
                raise self._error

            return fails
        return getattr(self._inner, name)


@pytest.mark.parametrize(
    ("projects", "repository"),
    [
        (None, lambda c: _Delegate(c, "tree_at", OSError("the managed clone is unreadable"))),
        (
            lambda p: _Delegate(
                p, "get_development_configuration", RuntimeError("the registry is down")
            ),
            None,
        ),
        (lambda p: _Delegate(p, "source_mappings", RuntimeError("the registry is down")), None),
    ],
    ids=["the-clone-fails", "the-configuration-read-fails", "the-mapping-read-fails"],
)
async def test_a_failing_product_read_never_stops_the_campaigns_decision(
    tmp_path, caplog, projects, repository
):
    """The outside review of #2778 (P2): the evaluation is reporting-only, heard before the
    decision, and the product path adds reads of the registry, the configuration and the clone.
    Bug caught: one of them failing propagates out of the hearing, so the campaign's continuation
    is never recorded and the campaign stalls on a report nothing reads. The failure is logged at
    the hearing's reporting boundary (``CampaignProgress._outcome_evaluated``), the one a sample
    application's evaluation already has, and the evaluation is left absent."""
    with caplog.at_level("ERROR", logger="squadops.campaigns.progress"):
        world, runner, records, _captured = await _heard(
            tmp_path, configure=_without_secret, projects=projects, repository=repository
        )

    # The read failed inside the evaluation, and the reporting boundary logged it.
    [failed] = [r for r in caplog.records if r.getMessage() == "outcome_evaluation_failed"]
    assert failed.exc_info is not None
    assert (records, runner.calls) == ([], [])
    assert world.decision is not None
    log = await world.campaigns.control_log(CID)
    assert decision_key("cyc_inc000000001") in {e.idempotency_key for e in log}
