"""A repository-backed Campaign's baseline reading: its calibration record's commit, evaluated when
the record is heard (SIP-0113 §10l; SIP-0109 §24bv point 1, §24cc; SIP-0112 contracts 4, 5, 7, 8).

Entered where the live campaign enters: ``CampaignProgress.calibration_recorded``, which the start
route calls once the start has written its record, and which the sweep and the startup call again
for a record that was never decided (``rehear_calibration_records``). The progress and the
evaluator are built as the runtime root builds them (``main.py``). The world is the shared
fixture's Tally, in a real managed clone, its baseline really captured and its derived profile
derived; the campaign starts by its record (``_World.started``). The runner records what it was
asked to start, and passes each scenario it runs unless the tree is one it is told to fail.

What bugs would these catch?
- a baseline read from anything but the record's commit whole, started by anything but the
  record's own configuration revision, or named by anything but its tree identity;
- the reading stored naming a cycle, or naming no unit, so no reader can find it;
- the reading taken after the promotion, beside the first increment's run;
- a declaration that can't run passing scenarios or reading them not applicable;
- a failed read, or a tree that isn't the record's, stopping the campaign's decision;
- a record heard again after a restart read twice;
- a product made from a scaffold blueprint never linted, or one that isn't linted by rules it never
  chose;
- the package reading a repository-backed campaign's deltas against nothing, or against zero.
"""

from __future__ import annotations

import dataclasses
import json
from functools import partial
from unittest.mock import AsyncMock

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.campaigns.calibration_record import recorded_calibration
from squadops.campaigns.campaign_branch import CampaignBranch
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.models import ControlOperation, CycleKind
from squadops.campaigns.progress import CampaignProgress, decision_key
from squadops.cycles.cycle_end import CycleStopReason
from squadops.outcomes.campaign_package import NO_BASELINE_READING, campaign_outcomes
from squadops.projects.development_configuration import EntryPoint
from squadops.scenarios.campaign_cycles import CampaignCycleEvaluator
from squadops.scenarios.evaluation import Applicability, BlockedReason, ScenarioResult
from squadops.scenarios.models import CampaignSuitePin
from squadops.scenarios.quality import LintReading, NotMeasured, QualityReading, QualityStatus
from squadops.scenarios.runner import TreeEvaluation
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import approve_suite, draft_suite
from tests.fixtures.shared_contract.repository import tracked_files
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.campaigns.test_campaign_branch import CID, _added, _World
from tests.unit.scenarios.test_campaign_cycles_declared_start import (
    SUITE,
    T0,
    _Delegate,
    _without_secret,
)

BLUEPRINT = "fullstack_fastapi_react"
EVALUATOR = "squadops-evaluator:test"


def _lint(total: int) -> LintReading:
    reading = {"tools": {"ruff": "ruff 0.16.6"}, "total": total, "by_rule": {"ruff:F401": total}}
    return LintReading(
        QualityStatus.MEASURED, reading={**reading, "unavailable": {}}, evaluator=EVALUATOR
    )


class _Runner:
    """Records each start it's asked for, and whether the campaign had promoted anything by then.
    Passes every scenario it runs, except on a tree in ``failing``; reports ``started=False`` when
    its start fails. Lints only a tree it is given a blueprint for, as the sandbox's runner does:
    ``lint_totals`` findings by tree, else ``lint_default``."""

    def __init__(
        self, world, *, failing=(), start_fails=False, lint_totals=None, lint_default=3
    ) -> None:
        self.world, self.failing, self.start_fails = world, set(failing), start_fails
        self.lint_totals, self.lint_default = lint_totals or {}, lint_default
        self.calls: list[dict] = []
        self.promoted_before: list[bool] = []

    async def evaluate_tree(self, **kw):
        self.calls.append(kw)
        log = await self.world.campaigns.control_log(CID)
        self.promoted_before.append(any(e.operation is ControlOperation.PROMOTE for e in log))
        identity = kw["tree_identity"]
        lint = (
            _lint(self.lint_totals.get(identity, self.lint_default))
            if kw.get("lint_stack")
            else None
        )
        if self.start_fails:
            return TreeEvaluation(identity, started=False, start_detail="setup step 1 exited 2")
        failed = identity in self.failing
        runs = tuple(
            ScenarioRun(
                s["scenario_id"],
                "failed" if failed else "passed",
                steps_taken=1,
                first_failing_step=1 if failed else None,
            )
            for s in kw["scenarios"]
        )
        return TreeEvaluation(
            identity,
            started=True,
            runs=runs,
            configuration_revision=kw["declared"].configuration_revision,
            lint=lint,
        )


def _progress(world, evaluator, store, campaigns=None) -> CampaignProgress:
    """The completion path as ``main.py`` builds it: the evaluator's two hooks, and the package's
    outcome section read from the same store."""
    return CampaignProgress(
        campaigns=campaigns or world.campaigns,
        cycles=world.cycles,
        vault=world.vault,
        assess=world._assess,
        launch=AsyncMock(),
        evaluate_outcome=evaluator.cycle_ended,
        evaluate_baseline=evaluator.calibration_recorded,
        outcome_section=partial(campaign_outcomes, store),
        intervention_section=None,
        campaign_branch=CampaignBranch(projects=world.projects, repository=world.clones),
    )


async def _store(*, pin: bool = True) -> MemoryScenarioStore:
    store = MemoryScenarioStore()
    await draft_suite(store, SUITE, actor="supervisor", at=T0)
    await approve_suite(store, SUITE.digest, actor="owner", at=T0)
    if pin:
        await store.save_pin(CampaignSuitePin(CID, SUITE.digest, pinned_by="owner", pinned_at=T0))
    return store


def _evaluator(world, store, runner, *, projects=None, repository=None) -> CampaignCycleEvaluator:
    return CampaignCycleEvaluator(
        store=store,
        runner=runner,
        vault=world.vault,
        campaigns=world.campaigns,
        clock=lambda: T0,
        projects=projects(world.projects) if projects else world.projects,
        repository=repository(world.clones) if repository else world.clones,
    )


def _record_tree(world) -> str:
    """The tree identity of the commit Tally's record is written at, its baseline's."""
    return FileTree.of(tracked_files(world.repo.path, world.repo.second_commit)).identity


async def _heard(
    tmp_path, *, configure=_without_secret, pin=True, runner=None, projects=None, repository=None
):
    """Tally's campaign started by its record, heard by the progress the runtime builds: its
    baseline captured, the record written, promoted and decided (``_World.started``)."""
    world = _World(tmp_path)
    if configure is not None:
        world.projects.configuration = configure(world.projects.configuration)
    store = await _store(pin=pin)
    runner = runner(world) if runner else _Runner(world)
    world.progress = _progress(
        world, _evaluator(world, store, runner, projects=projects, repository=repository), store
    )
    await world.started()
    record = recorded_calibration(await world.campaigns.control_log(CID))
    return world, store, runner, record


async def _decided(world, record) -> bool:
    log = await world.campaigns.control_log(CID)
    return decision_key(record.record_id) in {e.idempotency_key for e in log}


class _Asked:
    """The registry, recording the revision each configuration is read at and the pin each
    derived profile is read at."""

    asked: list = []

    def __init__(self, inner) -> None:
        self._inner = inner
        _Asked.asked = []

    async def get_development_configuration(self, project_id, revision=None):
        _Asked.asked.append(("configuration", revision))
        return await self._inner.get_development_configuration(project_id, revision)

    async def get_derived_profile(self, project_id, *, at=None):
        _Asked.asked.append(("profile", at))
        return await self._inner.get_derived_profile(project_id, at=at)

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def test_the_records_commit_is_read_whole_started_from_its_revision_and_names_the_record(
    tmp_path,
):
    """§10l end to end. Bugs caught: a tree other than the record's commit read; the start not
    the declared one at the record's revision, or the profile read at another pin; the executable
    bits dropped; the reading naming a cycle, a previous tree, or no unit; the reading taken after
    the promotion, so it runs beside the first increment rather than on the idle box."""
    world, store, runner, record = await _heard(tmp_path, projects=_Asked)

    assert _Asked.asked == [
        ("configuration", record.development_configuration_revision),
        ("profile", (record.commit, record.development_configuration_revision)),
    ]
    [reading] = await store.evaluations_for_calibration_record(record.record_id)
    checkout = await world.clones.tree_at(PROJECT, record.commit)
    [call] = runner.calls
    assert (reading.calibration_record_id, reading.cycle_id, reading.campaign_id) == (
        record.record_id,
        None,
        CID,
    )
    assert (reading.project_id, reading.suite_digest) == (PROJECT, SUITE.digest)
    assert reading.previous_accepted_tree_identity is None
    assert reading.evaluated_tree_identity == call["tree_identity"] == record.tree_identity
    assert record.tree_identity == FileTree.of(checkout.files).identity == _record_tree(world)
    assert (dict(call["tree"]), set(call["executable"])) == (
        dict(checkout.files),
        set(checkout.executable),
    )
    declared = call["declared"]
    assert (declared.start, declared.setup, declared.configuration_revision) == (
        ("python3", "-m", "tally", "serve", "--host", "0.0.0.0", "--port", "18407"),
        (("python3", "tools/build.py"),),
        record.development_configuration_revision,
    )
    assert (call["stack"], call["environment"]) == (None, {})
    # Tally declares an http_base and no ui_base: its HTTP scenario ran, its page one doesn't apply.
    by_id = {o.scenario_id: o for o in reading.outcomes}
    assert by_id["counter-total"].result is ScenarioResult.PASSED
    assert by_id["counter-page"].applicability is Applicability.NOT_APPLICABLE
    assert reading.quality == QualityReading(QualityStatus.NOT_APPLICABLE)
    # Tally was made from no blueprint: no rule set is asked for, and none is read.
    assert "lint_stack" not in call
    assert (reading.lint.status, reading.lint.reason) == (
        QualityStatus.NOT_MEASURED,
        NotMeasured.NOT_A_SCAFFOLD_STACK,
    )
    assert runner.promoted_before == [False]
    assert await _decided(world, record)
    assert reading.reference().to_dict()["calibration_record_id"] == record.record_id


async def test_a_campaign_with_no_suite_pinned_has_no_baseline_reading(tmp_path):
    """Bug caught: a reading against a suite the campaign never pinned, or a missing pin failing
    the hearing, so the record is never decided."""
    world, store, runner, record = await _heard(tmp_path, pin=False)

    assert await store.evaluations_for_calibration_record(record.record_id) == []
    assert runner.calls == []
    assert await _decided(world, record)


def _with_ui(configuration):
    """Tally's recorded start, its secret kept, with pages declared beside its API."""
    start = configuration.commands.start
    ui = EntryPoint("ui_base", "http://127.0.0.1:18407/ui")
    start = dataclasses.replace(start, entry_points=(*start.entry_points, ui))
    return dataclasses.replace(
        configuration, commands=dataclasses.replace(configuration.commands, start=start)
    )


def _no_start(configuration):
    return dataclasses.replace(
        configuration, commands=dataclasses.replace(configuration.commands, start=None)
    )


def _blueprint_no_start(configuration):
    """A product made from a scaffold blueprint whose configuration declares no start."""
    return dataclasses.replace(_no_start(configuration), stack=BLUEPRINT)


@pytest.mark.parametrize(
    ("configure", "reason", "quality", "lint"),
    [
        (
            None,
            BlockedReason.SECRET_NOT_AVAILABLE,
            QualityReading(QualityStatus.NOT_APPLICABLE),
            NotMeasured.NOT_A_SCAFFOLD_STACK,
        ),
        (
            _with_ui,
            BlockedReason.SECRET_NOT_AVAILABLE,
            QualityReading.not_measured(NotMeasured.SECRET_NOT_AVAILABLE),
            NotMeasured.NOT_A_SCAFFOLD_STACK,
        ),
        (
            _no_start,
            BlockedReason.NO_START_DECLARATION,
            QualityReading.not_measured(NotMeasured.NO_START_DECLARATION),
            NotMeasured.NOT_A_SCAFFOLD_STACK,
        ),
        (
            _blueprint_no_start,
            BlockedReason.NO_START_DECLARATION,
            QualityReading.not_measured(NotMeasured.NO_START_DECLARATION),
            NotMeasured.NO_START_DECLARATION,
        ),
    ],
    ids=["tallys-own-secret", "a-secret-with-pages", "no-start-declaration", "a-blueprints-too"],
)
async def test_a_declaration_that_cant_run_blocks_every_scenario_and_measure(
    tmp_path, configure, reason, quality, lint
):
    """§10l, contract 7's reasons: nothing is started, every applicable scenario reads
    ``blocked_unverified`` with the reason, and every measure the start would serve is not
    measured for it: a blueprint's lint too, for the start's reason, since nothing reached the
    runner that lints. With no declaration every scenario applies. Bugs caught: a blocked start
    read as passing or not applicable; a blueprint's lint read as the evaluator's failure; and
    (found building this) a product with pages whose secret nothing releases failing the reading
    outright, since the page measures had no reason for it."""
    world, store, runner, record = await _heard(tmp_path, configure=configure)

    [reading] = await store.evaluations_for_calibration_record(record.record_id)
    applicable = [o for o in reading.outcomes if o.applicability is Applicability.APPLICABLE]
    assert runner.calls == []
    assert applicable
    assert {(o.result, o.blocked_reason) for o in applicable} == {
        (ScenarioResult.BLOCKED_UNVERIFIED, reason)
    }
    assert reading.quality == quality
    assert (reading.lint.status, reading.lint.reason) == (QualityStatus.NOT_MEASURED, lint)
    assert await _decided(world, record)


async def test_a_start_that_fails_blocks_every_scenario_and_the_reading_is_still_written(tmp_path):
    """§10l: the product was asked to start and didn't. Bug caught: a failed start writing no
    reading, so the deltas can't say why there is no baseline, or a scenario read as failed."""
    world, store, runner, record = await _heard(
        tmp_path, runner=lambda w: _Runner(w, start_fails=True)
    )

    [reading] = await store.evaluations_for_calibration_record(record.record_id)
    [call] = runner.calls
    applicable = [o for o in reading.outcomes if o.applicability is Applicability.APPLICABLE]
    assert call["tree_identity"] == record.tree_identity
    assert {(o.result, o.blocked_reason) for o in applicable} == {
        (ScenarioResult.BLOCKED_UNVERIFIED, BlockedReason.START_FAILED)
    }
    assert await _decided(world, record)


class _OtherTree:
    """A clone whose tree at any commit carries one more file than was recorded."""

    def __init__(self, inner) -> None:
        self._inner = inner

    async def tree_at(self, project_id, commit):
        checkout = await self._inner.tree_at(project_id, commit)
        return dataclasses.replace(checkout, files={**checkout.files, "stray.txt": b"x\n"})

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def test_a_commit_whose_tree_isnt_the_records_writes_no_reading(tmp_path, caplog):
    """Contract 4: the record names its commit's tree identity. Bug caught: a reading naming a
    tree other than the one the record accepted, which every increment's contribution would then
    read against; or the mismatch stopping the decision."""
    with caplog.at_level("WARNING", logger="squadops.scenarios.campaign_cycles"):
        world, store, runner, record = await _heard(tmp_path, repository=_OtherTree)

    [warned] = [
        r for r in caplog.records if r.getMessage() == "outcome_evaluation_skipped_tree_mismatch"
    ]
    assert (warned.record_id, warned.commit) == (record.record_id, record.commit)
    assert await store.evaluations_for_calibration_record(record.record_id) == []
    assert runner.calls == []
    assert await _decided(world, record)


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
        (lambda p: _Delegate(p, "get_derived_profile", RuntimeError("the registry is down")), None),
    ],
    ids=["the-clone-fails", "the-configuration-read-fails", "the-profile-read-fails"],
)
async def test_a_failing_read_never_stops_the_records_promotion_or_decision(
    tmp_path, caplog, projects, repository
):
    """§10l, phase 1's reporting-only rule. Bug caught: a read the baseline adds (the clone, the
    configuration, the profile) raising out of the hearing, so the record is never promoted or
    decided and the campaign stalls on a report nothing reads. It is logged at the hearing's
    reporting boundary, and the reading is left absent."""
    with caplog.at_level("ERROR", logger="squadops.campaigns.progress"):
        world, store, runner, record = await _heard(
            tmp_path, projects=projects, repository=repository
        )

    [failed] = [r for r in caplog.records if r.getMessage() == "baseline_evaluation_failed"]
    assert (failed.record_id, failed.campaign_id) == (record.record_id, CID)
    assert failed.exc_info is not None
    assert await store.evaluations_for_calibration_record(record.record_id) == []
    assert runner.calls == []
    log = await world.campaigns.control_log(CID)
    promoted = [e for e in log if e.operation is ControlOperation.PROMOTE]
    assert [e.binding["calibration_record_id"] for e in promoted] == [record.record_id]
    assert await _decided(world, record)


class _StopsBeforeDeciding:
    """The campaign registry of a process that stops between the record's promotion and its
    decision: the first decision it is asked to write never commits."""

    def __init__(self, inner) -> None:
        self._inner, self.stopped = inner, False

    async def transition(self, campaign_id, transition):
        if transition.operation is ControlOperation.DECIDE and not self.stopped:
            self.stopped = True
            raise RuntimeError("the process stopped")
        return await self._inner.transition(campaign_id, transition)

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def test_a_record_heard_again_after_a_restart_is_read_once(tmp_path):
    """§10l: idempotent across a re-hearing. The first hearing reads the baseline and stops
    before its decision; the restarted process (a new progress and evaluator over the same
    stores) hears the record again, as its startup does. Bug caught: a second reading of the same
    commit, which the package would then pick between by time; or no decision at all."""
    world = _World(tmp_path)
    world.projects.configuration = _without_secret(world.projects.configuration)
    store, runner = await _store(), _Runner(world)
    stopping = _StopsBeforeDeciding(world.campaigns)
    world.progress = _progress(world, _evaluator(world, store, runner), store, campaigns=stopping)
    with pytest.raises(RuntimeError, match="the process stopped"):
        await world.started()
    record = recorded_calibration(await world.campaigns.control_log(CID))
    [first] = await store.evaluations_for_calibration_record(record.record_id)
    assert not await _decided(world, record)

    restarted = _progress(world, _evaluator(world, store, _Runner(world)), store)
    assert await restarted.rehear_calibration_records() == [CID]

    assert await store.evaluations_for_calibration_record(record.record_id) == [first]
    assert len(runner.calls) == 1
    assert await _decided(world, record)


def _blueprint(stack):
    """Tally's configuration as a greenfield product made from ``stack`` would record it: the
    derived profile captured at its pin names the blueprint (contract 8's ``blueprint``)."""

    def configure(configuration):
        return dataclasses.replace(_without_secret(configuration), stack=stack)

    return configure


@pytest.mark.parametrize(
    ("stack", "linted"),
    [(BLUEPRINT, True), ("django", False), (None, False)],
    ids=["a-scaffold-blueprint", "a-stack-with-no-scaffold", "no-blueprint"],
)
async def test_a_product_made_from_a_blueprint_is_linted_by_its_rule_set_at_baseline_and_increment(
    tmp_path, stack, linted
):
    """§10l, §4.2: lint by a blueprint's rule set, read from the derived profile at the pin, in
    the baseline reading and in each increment's evaluation (``CampaignProgress.cycle_ended``).
    Bugs caught: the blueprint never passed to the runner, so a product made from one is never
    linted; a stack with no scaffold (or none) linted by rules it never chose; the increment's
    evaluation reading it differently from its baseline, so the two can't be compared."""
    world, store, runner, record = await _heard(tmp_path, configure=_blueprint(stack))
    cycle, run, _captured = await world.delivered("cyc_inc000000001", _added("total"))
    await world.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)

    [baseline] = await store.evaluations_for_calibration_record(record.record_id)
    [increment] = await store.evaluations_for_cycle(cycle.cycle_id)
    assert [c.get("lint_stack") for c in runner.calls] == [BLUEPRINT if linted else None] * 2
    for reading in (baseline, increment):
        if linted:
            assert reading.lint == _lint(3)
        else:
            assert (reading.lint.status, reading.lint.reason) == (
                QualityStatus.NOT_MEASURED,
                NotMeasured.NOT_A_SCAFFOLD_STACK,
            )


async def _package(world) -> tuple[dict, str]:
    _identity, package_id, digest_id = await world.progress.materialize_package(CID)
    _ref, package = await world.vault.retrieve(package_id)
    _ref, digest = await world.vault.retrieve(digest_id)
    return json.loads(package), digest.decode("utf-8")


async def _first_increment_heard(world):
    cycle, run, _captured = await world.delivered("cyc_inc000000001", _added("total"))
    await world.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)


async def test_the_package_reads_the_first_increment_against_the_records_reading(tmp_path):
    """§10l: contribution and the deltas read the record's reading where a calibration cycle's
    stood. The baseline fails the scenario the increment makes pass, and the increment adds two
    lint findings to its blueprint's three. Bugs caught: the record's reading never named in the
    package, so the first increment's contribution is unread and no delta is taken; or the record
    id never passed from the control log to the section (``CampaignProgress._outcomes``)."""
    world, store, _runner, record = await _heard(
        tmp_path,
        configure=_blueprint(BLUEPRINT),
        runner=lambda w: _Runner(
            w, failing={_record_tree(w)}, lint_totals={_record_tree(w): 3}, lint_default=5
        ),
    )
    await _first_increment_heard(world)

    doc, digest = await _package(world)

    [reading] = await store.evaluations_for_calibration_record(record.record_id)
    baseline, [section] = doc["outcomes"]["baseline"], doc["outcomes"]["cycles"]
    assert (baseline["calibration_record_id"], baseline["evaluation"], baseline["tree"]) == (
        record.record_id,
        reading.evaluation_id,
        record.tree_identity,
    )
    assert section["built_on"] == record.tree_identity
    assert section["contribution"] == {
        "reading": "contributed",
        "newly_passing": ["counter-total"],
        "regressed": [],
        "unverified": [],
    }
    assert section["vs_baseline"]["against_tree"] == record.tree_identity
    assert section["vs_baseline"]["moved"] == [
        ["lint:total", None, 3, 5, 2],
        ["lint:ruff:F401", None, 3, 5, 2],
    ]
    assert (
        f"calibration record `{record.record_id}`: baseline reading `{reading.evaluation_id}`"
        in digest
    )


class _FirstReadFails:
    """A clone whose first read fails: the record's, heard before any increment's capture."""

    def __init__(self, inner) -> None:
        self._inner, self._failed = inner, False

    async def tree_at(self, project_id, commit):
        if not self._failed:
            self._failed = True
            raise OSError("the managed clone is unreadable")
        return await self._inner.tree_at(project_id, commit)

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def test_with_no_baseline_reading_the_package_says_so_and_never_a_delta(tmp_path):
    """§10l: the record's read failed, so there is no baseline reading. Bugs caught: the deltas
    read as zero, or left out so the absence reads as nothing having moved; the first increment's
    contribution read against some other record."""
    world, store, _runner, record = await _heard(
        tmp_path, configure=_blueprint(BLUEPRINT), repository=_FirstReadFails
    )
    await _first_increment_heard(world)

    doc, digest = await _package(world)

    assert await store.evaluations_for_calibration_record(record.record_id) == []
    assert doc["outcomes"]["baseline"] == {
        "calibration_record_id": record.record_id,
        "evaluation": None,
        "unread_because": NO_BASELINE_READING,
    }
    [section] = doc["outcomes"]["cycles"]
    assert section["evaluation"] is not None
    assert section["vs_baseline"] == {"unread_because": NO_BASELINE_READING}
    assert section["contribution"] == {
        "reading": None,
        "unread_because": "no record of the tree it built on",
    }
    assert f"calibration record `{record.record_id}`: **{NO_BASELINE_READING}**" in digest


async def test_a_sample_applications_start_reads_no_baseline(tmp_path):
    """§10l leaves a sample application's calibration as it was: a cycle, evaluated at its end.
    Bug caught: the baseline hook called for a start that wrote no record, evaluating nothing or
    failing the start."""
    from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
    from squadops.campaigns.launch_requests import start_transition
    from tests.unit.campaigns.builders import campaign

    campaigns = MemoryCampaignRegistry()
    draft = campaign(CID)
    await campaigns.create_campaign(
        draft, actor="owner", actor_role="admin", reason="r", idempotency_key="create"
    )
    await campaigns.transition(
        CID,
        start_transition(
            draft, actor="owner", actor_role="admin", reason="go", idempotency_key="start"
        ),
    )
    evaluate_baseline = AsyncMock()
    progress = CampaignProgress(
        campaigns=campaigns, cycles=AsyncMock(), vault=AsyncMock(), assess=AsyncMock(),
        launch=AsyncMock(), evaluate_outcome=None, evaluate_baseline=evaluate_baseline,
        outcome_section=None, intervention_section=None, campaign_branch=None,
    )  # fmt: skip

    assert await progress.calibration_recorded(CID) is None
    evaluate_baseline.assert_not_awaited()
    [intent] = await campaigns.launch_intents(CID)
    assert intent.cycle_kind is CycleKind.CALIBRATION


def test_the_runtime_root_hands_the_progress_the_evaluators_baseline_reading():
    """Bug caught: the root building the campaign's progress with no baseline hook, so no
    repository-backed campaign is ever read at its start while each test, built on its own
    progress, stays green."""
    import ast
    from pathlib import Path

    main = Path(__file__).resolve().parents[3] / "src/squadops/api/runtime/main.py"
    [call] = [
        node
        for node in ast.walk(ast.parse(main.read_text()))
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "CampaignProgress"
    ]
    passed = {k.arg: ast.unparse(k.value) for k in call.keywords}
    assert (passed["evaluate_outcome"], passed["evaluate_baseline"]) == (
        "cycle_evaluator.cycle_ended",
        "cycle_evaluator.calibration_recorded",
    )
