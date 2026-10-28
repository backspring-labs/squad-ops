"""A repository-backed increment is judged at its delivery, on the product's runner, in place of
``qa.evaluate_increment`` (SIP-0109 §24cd point 6, §24cl).

Entered where the live cycle enters: the executor's end of plan (``_execute_sequential``, which
delivers once the plan's tasks are done), and plan generation (``generate_task_plan``, which
``RunProvisioning.prepare`` calls). The Project is the shared fixture's Tally, in a real managed
clone, delivered and judged through the real sandbox service, whose one stand-in runs X-3a's
disposable copy as local processes. Tally tests with unittest, which no findings reader names test
by test (its profile's ``no_test_id_reader``), so a new criterion is unread and a frozen one is
read by its file's exit status. Real readings by test id are ``test_runner_acceptance_sandbox``'s.

What bugs would these catch?
- a repository-backed increment's plan still ending in ``qa.evaluate_increment``, which runs in the
  qa role's container, where no product toolchain is, or a sample application's losing it;
- the delivery never judging the increment, so the campaign reads no evaluation and blocks every
  increment unjudged, or judging a standalone source-backed cycle that is no increment;
- the evaluation stored off the run the campaign reads it from, or with a document its readers
  can't read: the verdict, the frozen results, the bundles a promotion freezes;
- a frozen criterion run from the candidate's copy, or never run.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime

import pytest

from squadops.campaigns.acceptance import NO_READER_EXIT_ZERO
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import INCREMENT_EVALUATION_ARTIFACT_TYPE
from squadops.campaigns.runner_acceptance import ProductTestSurface, freeze_product_bundle
from squadops.capabilities.handlers.planning.proposal import CHANGE_REQUEST_ARTIFACT_TYPE
from squadops.cycles.models import ArtifactRef, Run
from squadops.execution.dispatched_flow_executor import _ExecutionError
from squadops.execution.source_delivery import SOURCE_VERIFICATION_TYPE
from squadops.projects.derived_profile import parse_profile
from tests.fixtures.shared_contract.repository import recorded, tracked_files
from tests.unit.campaigns.test_product_increment_seams import STORED, _cycle, _profile
from tests.unit.cycles import test_source_backed_run
from tests.unit.cycles.test_source_backed_run import _end_of_plan, _of_type

#: The shared fixture's Tally, its real clone and sandbox, and an executor over them (``world``).
world = test_source_backed_run.world

NOW = datetime(2026, 10, 28, 14, 0, tzinfo=UTC)
REPORT = "tally/report.py"
R1 = "checks/check_criterion_R1.py"
F1 = "checks/check_criterion_F1.py"

#: The increment's change: a summary line, which R1 asserts.
_LINE = b"""

def summary_line(ledger):
    s = summarize(ledger)
    return f"{s['total']} across {s['counters']} counters"
"""
_R1_TEST = b"""import unittest

from tally.ledger import Ledger
from tally.report import summary_line


class SummaryLine(unittest.TestCase):
    def test_reads_the_total_and_counters(self):
        ledger = Ledger()
        ledger.load(["apples:3", "pears:5"])
        self.assertEqual(summary_line(ledger), "8 across 2 counters")
"""
#: An earlier increment's criterion, frozen: one counter is the top one. No check of Tally's
#: asserts it, so only the frozen bundle finds a change that breaks it.
_F1_TEST = b"""import unittest

from tally.ledger import Ledger
from tally.report import summarize


class OneCounter(unittest.TestCase):
    def test_a_single_counter_is_the_top(self):
        ledger = Ledger()
        ledger.load(["apples:2"])
        self.assertEqual(summarize(ledger)["top"], "apples")
"""
#: A change that keeps every check of Tally's and breaks F1.
_NO_TOP_FOR_ONE = b"""

_summarize = summarize


def summarize(ledger):
    s = _summarize(ledger)
    return {**s, "top": None} if s["counters"] == 1 else s
"""


def _stored(vault, cycle, run_id, artifact_type, filename, content, **metadata) -> str:
    ref = ArtifactRef(
        artifact_id=f"art_{artifact_type[:6]}{len(vault.stored):06d}",
        project_id=cycle.project_id,
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        artifact_type=artifact_type,
        filename=filename,
        content_hash="h",
        size_bytes=len(content),
        media_type="application/json",
        created_at=NOW,
        metadata=metadata,
    )
    vault.stored[ref.artifact_id] = (ref, content)
    return ref.artifact_id


def _f1_bundle(repo) -> dict:
    """F1's bundle as an earlier increment's promotion stored it (``_store_bundle``)."""
    profile = parse_profile(recorded("derived_profile", "valid"))
    tree = FileTree.of({**tracked_files(repo.path, repo.second_commit), F1: _F1_TEST})
    bundle = freeze_product_bundle(
        "F1", tree, F1, ProductTestSurface.of(profile, [F1]), profile.runners[0]
    )
    return {
        "criterion_id": "F1",
        "address": bundle.address,
        "test_path": F1,
        "invocation": list(bundle.invocation),
        "files": {p: c.decode() for p, c in bundle.files.files},
    }


def _increment(world_, *, frozen: bool, request: str = STORED):
    """The world's cycle as a repository-backed increment's implementation sees it: its block names
    the campaign branch, its launch pinned F1 (when ``frozen``), and its approved change request
    (R1, a summary line in the report module) is forwarded in its plan refs."""
    repo, vault, executor, cycle, run = world_
    pins = []
    if frozen:
        bundle = _f1_bundle(repo)
        ref = _stored(
            vault, cycle, "run_prior", "verifier_bundle", "F1.json", json.dumps(bundle).encode()
        )
        pins = [
            {
                "criterion_id": "F1",
                "test_path": F1,
                "bundle_ref": ref,
                "bundle_address": bundle["address"],
            }
        ]
    request = _stored(
        vault,
        cycle,
        "run_prop",
        CHANGE_REQUEST_ARTIFACT_TYPE,
        "change_request.yaml",
        request.encode(),
    )
    block = {**_cycle().execution_overrides["campaign_proposal"], "frozen_criteria": pins}
    increment = dataclasses.replace(
        cycle,
        kind="increment",
        campaign_id="cmp_tally00001",
        execution_overrides={"campaign_proposal": block, "plan_artifact_refs": [request]},
    )
    return repo, vault, executor, increment, run


async def _judged(world_, changes: dict, *, frozen: bool = True, request: str = STORED) -> dict:
    repo, vault, executor, cycle, run = _increment(world_, frozen=frozen, request=request)
    await _end_of_plan(executor, cycle, run, vault, changes)
    [(ref, raw)] = _of_type(vault, INCREMENT_EVALUATION_ARTIFACT_TYPE)
    assert (ref.cycle_id, ref.run_id) == (cycle.cycle_id, run.run_id)
    executor._cycle_registry.append_artifact_refs.assert_any_await(run.run_id, (ref.artifact_id,))
    return json.loads(raw)


async def test_a_branch_increment_is_judged_at_its_delivery_on_its_runner(world):  # noqa: F811
    """The live path end to end: delivery verifies and captures the candidate, then judges it.
    Tally's runner names no test, so R1 is unread and blocks (§24ci (a)). F1's frozen bundle runs
    on the candidate and exits 0, which shows no test ran, so it blocks too (§24cl item 13). R1's
    bundle is frozen with its invocation, for the promotion that never comes while it blocks."""
    repo = world[0]
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(world, {REPORT: report + _LINE, R1: _R1_TEST})

    assert document["verdict"] == "blocked_unverified"
    assert (document["unmet"], document["blocked"]) == (
        [],
        ["criterion R1: its runner names no test", f"frozen F1: {NO_READER_EXIT_ZERO}"],
    )
    assert document["discriminations"] == [
        {"criterion_id": "R1", "met": False, "reason": "no_test_id_reader", "discriminating": []}
    ]
    [frozen] = document["frozen"]
    assert (frozen["criterion_id"], frozen["held"], frozen["detail"]) == (
        "F1", "blocked_unverified", NO_READER_EXIT_ZERO,
    )  # fmt: skip
    assert document["new_bundles"]["R1"]["invocation"] == [
        "python3", "-m", "unittest", "discover", "-s", "checks", "-p", "check_criterion_R1.py",
    ]  # fmt: skip
    assert list(document["new_bundles"]["R1"]["files"]) == [R1]
    assert document["evaluated_on"] == "product_runner"
    [run] = document["runs"]
    assert (run["criterion_id"], run["side"], run["exit_code"], run["reader"]) == (
        "F1", "candidate", 0, None,
    )  # fmt: skip
    # Judged on the candidate delivery verified: the candidate's tree, and the head's.
    [(_v, raw)] = _of_type(world[1], SOURCE_VERIFICATION_TYPE)
    verification = json.loads(raw)
    assert document["candidate_tree"] == verification["candidate_tree_identity"]
    assert (
        document["accepted_tree"]
        == FileTree.of(tracked_files(repo.path, repo.second_commit)).identity
    )


async def test_a_change_that_breaks_a_frozen_criterion_is_rejected_though_every_check_holds(world):  # noqa: F811
    """§8.1: the frozen bundle is what finds a break the product's checks don't. Bugs caught: the
    frozen criteria never run at delivery, so the increment is accepted on the checks alone; or
    run from the candidate's copy of the file."""
    repo = world[0]
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(world, {REPORT: report + _NO_TOP_FOR_ONE}, frozen=True)

    [(_v, raw)] = _of_type(world[1], SOURCE_VERIFICATION_TYPE)
    assert json.loads(raw)["verdict"] == "accepted"
    assert document["verdict"] == "rejected"
    assert document["unmet"] == [
        "frozen F1: its test file exited 1 (read whole: no test-id reader)"
    ]


async def test_a_branch_increment_with_no_profile_at_its_pin_fails_its_run(world):  # noqa: F811
    """Nothing is accepted unjudged. Bug caught: an increment the evaluator couldn't judge
    completing with no evaluation, so the campaign reads it ``blocked_unverified`` with no reason
    anyone can act on, or with a verdict from nothing."""
    repo, vault, executor, cycle, run = _increment(world, frozen=False)
    from squadops.cycles.models import DerivedProfileNotFoundError

    executor._project_registry.get_derived_profile.side_effect = DerivedProfileNotFoundError("x")
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    with pytest.raises(
        _ExecutionError, match="increment acceptance: Project prj-tally has no derived"
    ):
        await _end_of_plan(executor, cycle, run, vault, {REPORT: report + _LINE})

    assert _of_type(vault, INCREMENT_EVALUATION_ARTIFACT_TYPE) == []


async def test_a_standalone_source_backed_cycle_is_never_judged_as_an_increment(world):  # noqa: F811
    """Bug caught: the evaluation keyed on the cycle's source context alone, so every standalone
    cycle on a Project is judged against criteria it never had."""
    repo, vault, executor, cycle, run = world
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    await _end_of_plan(executor, cycle, run, vault, {REPORT: report + _LINE})

    assert _of_type(vault, INCREMENT_EVALUATION_ARTIFACT_TYPE) == []
    assert len(_of_type(vault, SOURCE_VERIFICATION_TYPE)) == 1


def _branch_plan():
    from squadops.cycles.task_plan import generate_task_plan

    run = Run("run_i", "cyc_inc", 3, "running", "system", "cfg", workload_type="implementation")
    from tests.unit.cycles.test_increment_evaluation_wiring import _PLAN

    return generate_task_plan(_cycle(), run, _profile(), plan=_PLAN, change_request=STORED)


def _sample_plan():
    from tests.unit.cycles.test_increment_evaluation_wiring import STORED as SAMPLE
    from tests.unit.cycles.test_increment_evaluation_wiring import _implementation

    return _implementation(True, SAMPLE)


_BUILD = ["governance.define_done", "development.develop", "qa.test"]


@pytest.mark.parametrize(
    ("plan", "planned"),
    [(_branch_plan, _BUILD), (_sample_plan, [*_BUILD, "qa.evaluate_increment"])],
    ids=["a-campaign-branch-increment", "a-sample-applications-increment"],
)
def test_only_a_sample_applications_increment_plans_qa_evaluate_increment(plan, planned):
    """Rule 3: the plan asks the basis's property, never the task type. Entered at
    ``generate_task_plan``, over one authored plan. Bugs caught: the drop applied to a sample
    application's increment, so nothing judges it; not applied to a product's, so its acceptance
    runs in a role's container with no product toolchain; or taking a build task with it."""
    assert [str(e.task_type) for e in plan()] == planned


async def test_a_product_evaluations_bundle_is_frozen_at_promotion_and_pinned_whole(tmp_path):
    """The reader the evaluation feeds: ``CampaignProgress.cycle_ended``, on Tally's real campaign
    branch, reads a product evaluation's document as a sample application's, and its promotion
    freezes the new criterion's bundle at its placed file, with its runner's argv. Bugs caught:
    the document's added keys (``evaluated_on``, ``runs``) breaking a reader; the bundle frozen
    from the document with another address than the one the next launch's pin is checked
    against, so every later increment reads the criterion ``blocked_unverified``."""
    from squadops.campaigns.acceptance import (
        Discrimination,
        DiscriminationReason,
        IncrementAcceptance,
        IncrementVerdict,
    )
    from squadops.campaigns.acceptance_run import (
        IncrementEvaluation,
        NewCriterion,
        evaluation_document,
        frozen_criteria_from,
    )
    from squadops.cycles.cycle_end import CycleStopReason
    from tests.unit.campaigns.test_campaign_branch import _added, _World

    world_ = _World(tmp_path)
    await world_.started()
    cycle, run, captured = await world_.delivered("cyc_inc000000001", _added("total"))
    profile = parse_profile(recorded("derived_profile", "valid"))
    head = tracked_files(world_.repo.path, world_.repo.second_commit)
    tree = FileTree.of({**head, R1: _R1_TEST})
    bundle = freeze_product_bundle(
        "R1", tree, R1, ProductTestSurface.of(profile, [R1]), profile.runners[0]
    )
    evaluation = IncrementEvaluation(
        acceptance=IncrementAcceptance(IncrementVerdict.ACCEPTED),
        discriminations=(
            Discrimination("R1", True, DiscriminationReason.DISCRIMINATES, (f"{R1}::t",)),
        ),
        frozen=(),
        routes=(),
        new_bundles={"R1": bundle},
    )
    document = {
        **evaluation_document(
            evaluation,
            increment_id="prop_tally0001",
            accepted=FileTree.of(head),
            candidate=tree,
            new=[NewCriterion("R1", R1)],
            retired=(),
        ),
        "evaluated_on": "product_runner",
        "runs": [{"criterion_id": "R1", "side": "baseline", "exit_code": 1}],
    }
    await world_._stored(
        cycle, run, "increment_evaluation.json", INCREMENT_EVALUATION_ARTIFACT_TYPE,
        json.dumps(document).encode(),
    )  # fmt: skip

    await world_.progress.cycle_ended(cycle, run, CycleStopReason.SEQUENCE_COMPLETED)

    [promote] = await world_.promotions(cycle.cycle_id)
    assert promote.binding["commit"] == captured
    [pin] = promote.binding["frozen_criteria"]
    assert (pin["criterion_id"], pin["test_path"], pin["bundle_address"]) == (
        "R1", R1, bundle.address,
    )  # fmt: skip
    _ref, stored = await world_.vault.retrieve(pin["bundle_ref"])
    [frozen] = frozen_criteria_from([pin], {"R1": json.loads(stored)})
    assert frozen.bundle == bundle
    assert frozen.bundle.invocation[-2:] == ("-p", "check_criterion_R1.py")


# --- SIP-0109 §24co: the profile's client routes, rendered on the candidate at its delivery ---

#: Tally given a blueprint's routes, as a product made from one names them (H.7), and a start that
#: serves its pages at a ui_base. Tally serves none, so the browser's answers are the fake's.
_ROUTED = "/"
_TALLY_PAGES = {
    "http://10.89.0.7:8080/": '<html><body><main data-testid="counter-list"></main></body></html>',
    "http://10.89.0.7:8080/__squadops_unmatched__": (
        '<html><body><p data-testid="not-found-view"></p></body></html>'
    ),
}
_TALLY_MANIFEST = """
version: 1
kind: interface_manifest
project_id: tally
stack: fullstack_fastapi_react
entities: []
api: {base_path: "", endpoints: []}
frontend:
  routes:
    - {path: "/", view: CounterListView, testids: [counter-list]}
    - {path: "*", view: NotFoundView, testids: [not-found-view]}
"""


def _routed(world_, *, pages, start_argv=None):
    """The world's executor with the product's routes to render: its profile names them, its
    initialization's manifest anchors them, its start serves a ui_base, and the sandbox's
    scenario runner stands it up."""
    from adapters.sandbox.scenario_runner import ContainerScenarioRunner
    from squadops.projects.development_configuration import EntryPoint
    from squadops.projects.initialization import ProjectInitialization
    from squadops.scenarios.declared_routes import DeclaredStartRoutes
    from tests.unit.sandbox.test_scenario_runner import EVALUATOR
    from tests.unit.sandbox.test_scenario_runner_routes import _app, _Browser, _ip

    repo, vault, executor, cycle, run = world_
    registry = executor._project_registry
    profile = registry.get_derived_profile.return_value
    registry.get_derived_profile.return_value = dataclasses.replace(
        profile, blueprint_stack="fullstack_fastapi_react", client_routes=(_ROUTED, "*")
    )
    configuration = registry.get_development_configuration.return_value
    start = dataclasses.replace(
        configuration.commands.start,
        start=tuple(start_argv or configuration.commands.start.start),
        entry_points=(
            *configuration.commands.start.entry_points,
            EntryPoint("ui_base", "http://127.0.0.1:8080/"),
        ),
        # No secret is resolved before #2421's approval record: Tally's would block every route.
        evaluation_environment=(),
    )
    registry.get_development_configuration.return_value = dataclasses.replace(
        configuration, commands=dataclasses.replace(configuration.commands, start=start)
    )
    registry.get_initialization.return_value = ProjectInitialization(
        "prj-tally", repo.second_commit, "main", "fullstack_fastapi_react", "sha256:t",
        _TALLY_MANIFEST, (), "owner", NOW,
    )  # fmt: skip
    container = _Browser(pages)
    executor._route_renderer = DeclaredStartRoutes(
        ContainerScenarioRunner(
            container=container,
            root=repo.path.parent / "scenario-sandbox",
            image="sandbox:pinned",
            http_client_factory=_app([]),
            poll_interval_seconds=0.01,
            app_network="squadops-sandbox-apps",
            evaluator_image=EVALUATOR,
            resolve_host=_ip,
        )
    )
    return container


async def test_a_branch_increments_routes_are_rendered_on_its_candidate_at_delivery(world):  # noqa: F811
    """The live path, entered at the executor's end of plan: delivery verifies and captures the
    candidate, and its acceptance starts it from the configuration's declared start in the
    sandbox and reads each of the profile's routes. Bugs caught: the routes never rendered at the
    live caller (the runner not wired into the executor), rendered on a tree other than the
    candidate delivery verified, started by anything but the declared start, or their evidence
    left off the document the campaign reads."""
    repo = world[0]
    container = _routed(world, pages=_TALLY_PAGES)
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(world, {REPORT: report + _LINE, R1: _R1_TEST})

    assert document["routes"] == [
        {"path": "*", "held": "held", "missing": [], "not_shown": []},
        {"path": "/", "held": "held", "missing": [], "not_shown": []},
    ]
    assert not [b for b in document["blocked"] if b.startswith("route")]
    [(_v, raw)] = _of_type(world[1], SOURCE_VERIFICATION_TYPE)
    verification = json.loads(raw)
    rendered = document["renderings"]
    assert rendered["start"] == {
        "tree_identity": verification["candidate_tree_identity"],
        "configuration_revision": 1,
        "started": True,
        "detail": None,
    }
    assert [(r["route"], r["anchor"], r["read_at"], r["seen"]) for r in rendered["routes"]] == [
        ("*", "not-found-view", "/__squadops_unmatched__", ["not-found-view"]),
        ("/", "counter-list", "/", ["counter-list"]),
    ]
    # Started by the declared start: its build step, then its start argv, in a copy of the
    # candidate, which carries the squad's change.
    build, app = [s for s in container.specs if s.image == "sandbox:pinned"]
    assert (build.command, app.command[:3]) == (
        ["python3", "tools/build.py"],
        ["python3", "-m", "tally"],
    )
    assert container.held[0][REPORT] == report + _LINE


async def test_a_route_the_candidate_no_longer_serves_rejects_the_increment(world):  # noqa: F811
    """§8.3, as a sample application's increment reads it: a page without its view's root anchor
    is broken, and the increment is rejected whatever its criteria read. Bug caught: a product's
    broken page read only as blocked, so a change that drops a page is retried, never refused."""
    repo = world[0]
    _routed(
        world,
        pages={**_TALLY_PAGES, "http://10.89.0.7:8080/": "<html><body><h1>404</h1></body></html>"},
    )
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(world, {REPORT: report + _LINE})

    assert document["verdict"] == "rejected"
    assert "route /: missing counter-list" in document["unmet"]


async def test_a_branch_increment_whose_start_fails_has_every_route_blocked(world):  # noqa: F811
    """Contract 7's "start failed", at the live caller. Bug caught: a start that failed read as
    every page broken, so the squad is told its pages are wrong when nothing stood up."""

    repo = world[0]
    container = _routed(world, pages=_TALLY_PAGES)

    async def refused(spec):
        from squadops.tools.exceptions import ToolContainerError

        raise ToolContainerError("docker: the start image is gone")

    container.run_detached = refused
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(world, {REPORT: report + _LINE})

    routes = [b for b in document["blocked"] if b.startswith("route")]
    assert routes == [
        "route *: not rendered: start failed: the start could not run: docker: the start image "
        "is gone",
        "route /: not rendered: start failed: the start could not run: docker: the start image "
        "is gone",
    ]
    assert document["renderings"]["start"]["started"] is False


async def test_a_route_the_change_request_adds_keeps_the_increment_from_acceptance(world):  # noqa: F811
    """The outside review of #2777 (P2), at the live caller: the approved change request asserts
    its criterion on a client route the profile doesn't pin, the page the candidate serves there
    is broken, and the pinned routes still render. Bugs caught: the added route never rendered,
    so a broken new page is accepted; or the pinned routes dropped when one is added."""
    from squadops.campaigns.change_request import (
        SurfaceKind,
        content_hash,
        load_stored_change_request,
        stored_change_request,
    )
    from squadops.campaigns.product_routes import NO_ANCHOR_REQUESTED

    request = load_stored_change_request(STORED)
    [r1, *rest] = request.criteria
    on_a_page = dataclasses.replace(r1, surface_kind=SurfaceKind.CLIENT_ROUTE, surface="/totals")
    changed = dataclasses.replace(request, criteria=(on_a_page, *rest))
    adds_a_page = stored_change_request(
        dataclasses.replace(changed, content_hash=content_hash(changed))
    )
    repo = world[0]
    _routed(
        world,
        pages={
            **_TALLY_PAGES,
            "http://10.89.0.7:8080/totals": "<html><body><h1>500</h1></body></html>",
        },
    )
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(world, {REPORT: report + _LINE, R1: _R1_TEST}, request=adds_a_page)

    assert document["verdict"] != "accepted"
    assert f"route /totals: not rendered: {NO_ANCHOR_REQUESTED}" in document["blocked"]
    held = {r["path"]: r["held"] for r in document["routes"]}
    assert held == {"*": "held", "/": "held", "/totals": "blocked_unverified"}
    sources = {r["route"]: r["source"] for r in document["renderings"]["routes"]}
    assert sources == {
        "*": "approved_manifest",
        "/": "approved_manifest",
        "/totals": "change_request",
    }


async def test_a_fallback_page_with_the_anchor_only_in_a_template_rejects_the_increment(world):  # noqa: F811
    """The outside review of #2777 at 8c09cd4f (P2), at the live caller: the candidate no longer
    serves ``/``, and its fallback page carries ``/``'s root anchor only inside an unused
    ``<template>``. Bug caught: inert markup Chromium's dump keeps read as the rendered view, so a
    dropped page holds and the increment is accepted."""
    repo = world[0]
    _routed(
        world,
        pages={
            **_TALLY_PAGES,
            "http://10.89.0.7:8080/": (
                '<html><body><p data-testid="not-found-view"></p><template><main '
                'data-testid="counter-list"></main></template></body></html>'
            ),
        },
    )
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(world, {REPORT: report + _LINE})

    assert document["verdict"] == "rejected"
    assert "route /: missing counter-list" in document["unmet"]
    [root] = [r for r in document["renderings"]["routes"] if r["route"] == "/"]
    assert (root["held"], root["seen"]) == ("broken", ["not-found-view"])


async def test_a_page_whose_anchor_its_markup_hides_rejects_the_increment(world):  # noqa: F811
    """§24co item 13 at the live caller: the candidate's ``/`` carries its root anchor only on an
    element an ancestor's inline style hides, beside a visible fallback. Bug caught: a successful
    browser exit plus an anchor's incidental presence read as the view rendered."""
    repo = world[0]
    _routed(
        world,
        pages={
            **_TALLY_PAGES,
            "http://10.89.0.7:8080/": (
                '<html><body><p data-testid="not-found-view"></p><div style="display:none">'
                '<main data-testid="counter-list"></main></div></body></html>'
            ),
        },
    )
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(world, {REPORT: report + _LINE})

    assert document["verdict"] == "rejected"
    assert "route /: missing counter-list" in document["unmet"]


def _adds_totals(anchor: str) -> str:
    """The stored request with R1 asserted on ``/totals``, a page the profile doesn't pin, naming
    its view's anchor (§24cp), re-hashed as the rails would have stored it."""
    from squadops.campaigns.change_request import (
        SurfaceKind,
        content_hash,
        load_stored_change_request,
        stored_change_request,
    )

    request = load_stored_change_request(STORED)
    [r1, *rest] = request.criteria
    on_a_page = dataclasses.replace(
        r1, surface_kind=SurfaceKind.CLIENT_ROUTE, surface="/totals", anchor=anchor
    )
    changed = dataclasses.replace(request, criteria=(on_a_page, *rest))
    return stored_change_request(dataclasses.replace(changed, content_hash=content_hash(changed)))


@pytest.mark.parametrize(
    ("page", "held", "verdict"),
    [
        # R1 is unread on Tally's runner (§24ci (a)), so the increment still blocks, on R1 alone.
        (
            '<html><body><section data-testid="totals-view"></section></body></html>',
            "held",
            "blocked_unverified",
        ),
        (
            '<html><body><main data-testid="counter-list"></main></body></html>',
            "broken",
            "rejected",
        ),
    ],
    ids=["the-candidate-renders-it", "the-candidate-renders-another-view"],
)
async def test_an_added_route_is_judged_at_delivery_by_the_anchor_its_request_names(  # noqa: F811
    world, page, held, verdict
):
    """#2779, at the live caller: the executor's end of plan delivers the candidate, and the
    approved change request's anchor reaches the renderer through ``requested_routes``. Bugs
    caught: the anchor lost between the stored request and the judgement, so an added page still
    blocks however it renders; or a candidate whose new page shows another view accepted."""
    repo = world[0]
    _routed(world, pages={**_TALLY_PAGES, "http://10.89.0.7:8080/totals": page})
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    document = await _judged(
        world, {REPORT: report + _LINE, R1: _R1_TEST}, request=_adds_totals("totals-view")
    )

    routes = {r["path"]: (r["held"], r["missing"]) for r in document["routes"]}
    assert routes == {
        "*": ("held", []),
        "/": ("held", []),
        "/totals": (held, [] if held == "held" else ["totals-view"]),
    }
    assert not [b for b in document["blocked"] if b.startswith("route")]
    [totals] = [r for r in document["renderings"]["routes"] if r["route"] == "/totals"]
    assert (totals["source"], totals["anchor"]) == ("change_request", "totals-view")
    assert document["verdict"] == verdict
    assert [u for u in document["unmet"] if u.startswith("route")] == (
        [] if held == "held" else ["route /totals: missing totals-view"]
    )
