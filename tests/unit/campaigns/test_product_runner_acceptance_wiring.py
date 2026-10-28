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


def _increment(world_, *, frozen: bool):
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
        STORED.encode(),
    )
    block = {**_cycle().execution_overrides["campaign_proposal"], "frozen_criteria": pins}
    increment = dataclasses.replace(
        cycle,
        kind="increment",
        campaign_id="cmp_tally00001",
        execution_overrides={"campaign_proposal": block, "plan_artifact_refs": [request]},
    )
    return repo, vault, executor, increment, run


async def _judged(world_, changes: dict, *, frozen: bool = True) -> dict:
    repo, vault, executor, cycle, run = _increment(world_, frozen=frozen)
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
