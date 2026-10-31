"""Evaluating a cycle against a pinned suite (SIP-0113 §4.1, §4.8; #2414)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
from squadops.campaigns.evaluator_trees import FileTree
from squadops.scenarios import evaluate
from squadops.scenarios.evaluation import Applicability, BlockedReason, ScenarioResult
from squadops.scenarios.models import parse_suite
from squadops.scenarios.runner import (
    DeclaredStart,
    ReadinessUnsupported,
    RunnerUnavailable,
    StartUndeclared,
    TreeEvaluation,
)
from squadops.scenarios.steps import ScenarioRun
from squadops.scenarios.suites import SuiteRefused, approve_suite, draft_suite
from tests.unit.scenarios.suite_fixtures import SUITE

T0 = datetime(2026, 10, 18, 23, 0, tzinfo=UTC)
TREE = {"backend/main.py": b"app = 1\n", "frontend/index.html": b"<html></html>\n"}
#: SUITE's first scenario needs an endpoint and a page, its second an endpoint only.
PAGE_SCENARIO, API_SCENARIO = (s["scenario_id"] for s in SUITE["scenarios"])


class _Cycle:
    cycle_id, project_id = "cyc_eval00000001", "group_run"

    def resolved_config(self):
        return {"build_profile": "fullstack_fastapi_react"}


class _Vault:
    async def list_artifacts(self, *, cycle_id):
        return []  # no stored manifest: no concept or endpoint to resolve against

    async def retrieve(self, artifact_id):
        return None, TREE[artifact_id]


class _Runner:
    def __init__(self, *, started=True, raises=None):
        self.calls, self._started, self._raises = [], started, raises

    async def evaluate_tree(self, **kw):
        self.calls.append(kw)
        if self._raises:
            raise self._raises
        runs = tuple(
            ScenarioRun(s["scenario_id"], "failed", steps_taken=1, first_failing_step=1)
            if s["scenario_id"] == API_SCENARIO
            else ScenarioRun(
                s["scenario_id"], "blocked_unverified", blocked_reason="browser_unavailable"
            )
            for s in kw["scenarios"]
        )
        return TreeEvaluation(
            kw["tree_identity"], started=self._started, runs=runs if self._started else ()
        )


@pytest.fixture
async def store(monkeypatch):
    async def tree_refs(vault, cycle):
        return {path: path for path in TREE}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    store = MemoryScenarioStore()
    suite = parse_suite(SUITE)
    await draft_suite(store, suite, actor="supervisor", at=T0)
    await approve_suite(store, suite.digest, actor="owner", at=T0)
    return store, suite


async def _evaluate(store, suite, runner, **kw):
    return await evaluate.evaluate_cycle(
        store=store,
        runner=runner,
        vault=_Vault(),
        cycle=_Cycle(),
        suite_digest=suite.digest,
        campaign_id="cmp_eval00000001",
        previous_accepted_tree_identity="b" * 64,
        evaluated_at=T0,
        **kw,
    )


def _by_id(record):
    return {o.scenario_id: o for o in record.outcomes}


async def test_a_blueprint_cycle_is_evaluated_on_its_tree_and_its_record_written(store):
    """Bug caught: the runner handed a tree other than the cycle's (its identity then names
    nothing the campaign accepted), a failed scenario recorded without its step, or the record
    never written."""
    store, suite = store
    runner = _Runner()

    record = await _evaluate(store, suite, runner)

    [call] = runner.calls
    assert call["tree_identity"] == FileTree.of(TREE).identity == record.evaluated_tree_identity
    assert (call["stack"], call["declared"]) == ("fullstack_fastapi_react", None)
    outcomes = _by_id(record)
    assert (outcomes[API_SCENARIO].result, outcomes[API_SCENARIO].first_failing_step) == (
        ScenarioResult.FAILED,
        1,
    )
    assert outcomes[PAGE_SCENARIO].blocked_reason is BlockedReason.BROWSER_UNAVAILABLE
    assert await store.get_evaluation(record.evaluation_id) == record


async def test_a_scenario_whose_surface_the_project_lacks_is_not_applicable_and_never_runs(store):
    """§4.1. Bug caught: a page scenario run on a product with no pages and counted as a
    failure, or sent to the runner at all."""
    store, suite = store
    runner = _Runner()
    start = DeclaredStart(
        start=("python3", "-m", "tally"),
        port=18407,
        ready_kind="http",
        ready_path="/healthz",
        ready_timeout_seconds=20.0,
        configuration_revision=1,
    )

    record = await _evaluate(
        store,
        suite,
        runner,
        declared=start,
        served=evaluate.declared_surfaces(
            [{"kind": "http_base", "url": "http://127.0.0.1:18407/"}]
        ),
    )

    assert [s["scenario_id"] for s in runner.calls[0]["scenarios"]] == [API_SCENARIO]
    assert _by_id(record)[PAGE_SCENARIO].applicability is Applicability.NOT_APPLICABLE
    assert runner.calls[0]["declared"] == start


@pytest.mark.parametrize(
    ("runner", "kw", "reason"),
    [
        (None, {}, BlockedReason.NO_RUNNER),
        (_Runner(raises=RunnerUnavailable("503")), {}, BlockedReason.NO_RUNNER),
        (_Runner(started=False), {}, BlockedReason.START_FAILED),
        (
            _Runner(),
            {"unstartable": StartUndeclared("the Project declares no start")},
            BlockedReason.NO_START_DECLARATION,
        ),
        (
            _Runner(),
            {"unstartable": ReadinessUnsupported("no runner for readiness 'command'")},
            BlockedReason.NO_RUNNER,
        ),
    ],
    ids=[
        "no-runner",
        "runner-unreachable",
        "start-failed",
        "no-start-declaration",
        "a-readiness-no-runner-checks",
    ],
)
async def test_an_evaluation_that_cannot_run_blocks_every_applicable_scenario(
    store, runner, kw, reason
):
    """§4.1: never passed, never failed. Bug caught: a deploy with no runner, or a product that
    wouldn't start, reading as scenarios that failed (or, worse, that passed); or a ``command``
    readiness recorded as no start declaration (#2450's review)."""
    store, suite = store

    record = await _evaluate(store, suite, runner, **kw)

    assert {(o.result, o.blocked_reason) for o in record.outcomes} == {
        (ScenarioResult.BLOCKED_UNVERIFIED, reason)
    }


async def test_a_suite_the_owner_has_not_approved_evaluates_nothing(store):
    """D2. Bug caught: an evaluation by a draft suite, its results reported as the yardstick's."""
    store, _ = store
    draft = parse_suite({**SUITE, "scenarios": SUITE["scenarios"][:1]})
    await draft_suite(store, draft, actor="supervisor", at=T0)

    with pytest.raises(SuiteRefused):
        await _evaluate(store, draft, _Runner())
