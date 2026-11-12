"""A scenario criterion judged at an increment's delivery (#3053).

Entered at ``evaluate_on_runner``, which ``product_acceptance.evaluate_product_increment`` calls
at delivery. Its scenario criteria are played through a remote-execution port that runs #3044's
``fixture/declared_scenario`` operation in process, on the ``SHUT`` and ``OPEN`` worlds: the
reading each decision reads is one the real operation returned. No runner criterion is in these
increments, so the sandbox is never reached.

What bugs would these catch?
- A scenario's declaration run as a test, or never frozen: no one-file bundle for promotion.
- A new scenario judged on one side only, or on overlays that aren't acceptance's.
- An earlier increment's scenario not replayed on the candidate, so a change that breaks it is
  accepted.
- A declaration delivered with different content from the one approved, run as if approved.
- No port, no supplied operation or no kept vocabulary read as a pass or a failure instead of
  ``not_run``/blocked, with the reason lost.
- The readings dropped, so the verdict can't be re-read.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from adapters.remote_execution.fixture_operation_runner import (
    OPERATION,
    PROVIDER,
    VOCABULARY,
    WORLD_PATH,
    FixtureOperationRunner,
)
from squadops.campaigns.acceptance import DiscriminationReason, Held, IncrementVerdict
from squadops.campaigns.acceptance_run import FrozenCriterion, NewCriterion
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.runner_acceptance import (
    RunnerAcceptance,
    RunnerSetup,
    SandboxTree,
    evaluate_on_runner,
)
from squadops.campaigns.scenario_runs import ScenarioRuns, scenario_bundle
from squadops.capabilities.operation_supply import SuppliedOperation
from squadops.capabilities.skillsets import ToolRequest
from squadops.remote_execution.models import ReadingSide, RemoteOperationRequest
from tests.unit.campaigns.test_runner_acceptance_sandbox import _profile
from tests.unit.remote_execution.scenario_fixture import (
    OPEN,
    SCENARIO_PATH,
    SHUT,
    door_opens,
)

pytestmark = [pytest.mark.domain_orchestration]

SOURCE = {"src/server/door.luau": b"return { open = false }\n"}
DECLARATION = door_opens().document.encode()
OPERATION_SUPPLIED = SuppliedOperation(
    contract="game.scenario_verification",
    mode="play",
    role="qa",
    skillset="fixture-scenarios",
    skillset_digest="sha256:" + "11" * 32,
    tool=ToolRequest(OPERATION, PROVIDER, "worker"),
)


class _Port:
    """The runtime's port, running the fixture operation in process. It keeps every request."""

    def __init__(self) -> None:
        self.asked: list[RemoteOperationRequest] = []

    async def run_operation(self, request):
        self.asked.append(request)
        return await FixtureOperationRunner().run(request)


def _tree(world: dict, *, scenario: bool) -> dict[str, bytes]:
    return {
        **SOURCE,
        WORLD_PATH: json.dumps(world).encode(),
        **({SCENARIO_PATH: DECLARATION} if scenario else {}),
    }


def _scenarios(port=None, **overrides) -> ScenarioRuns:
    settings = {
        "operation": OPERATION_SUPPLIED,
        "vocabulary": VOCABULARY,
        "campaign_id": "cmp_1",
        "increment_id": "inc_2",
        "dispatch_id": "run_2:eval",
        **overrides,
    }
    return ScenarioRuns(port, **settings)


def _runs() -> RunnerAcceptance:
    return RunnerAcceptance(
        sandbox=None,
        profile=_profile(),
        setup=RunnerSetup(),
        workspace_prefix="acc-run_s-",
    )


async def _judge(port, *, candidate_world, frozen=(), new=True, scenarios=None, digests=None):
    accepted = SandboxTree(_tree(SHUT, scenario=False))
    candidate = SandboxTree(
        accepted.files,
        changes={
            WORLD_PATH: json.dumps(candidate_world).encode(),
            **({SCENARIO_PATH: DECLARATION} if new else {}),
        },
    )
    evaluation, done = await evaluate_on_runner(
        _runs(),
        increment_id="inc_2",
        accepted=accepted,
        candidate=candidate,
        new=[NewCriterion("C-2", SCENARIO_PATH)] if new else [],
        frozen=frozen,
        retired=(),
        routes=(),
        scenarios=scenarios if scenarios is not None else _scenarios(port),
        approved_digests=digests if digests is not None else {"C-2": door_opens().digest},
    )
    return evaluation, done


async def test_a_new_scenario_that_the_candidate_makes_pass_is_met_and_frozen_as_one_file():
    port = _Port()

    evaluation, done = await _judge(port, candidate_world=OPEN)

    [d] = evaluation.discriminations
    assert (d.met, d.reason, d.discriminating) == (
        True,
        DiscriminationReason.DISCRIMINATES,
        ("door-open",),
    )
    assert evaluation.acceptance.verdict is IncrementVerdict.ACCEPTED
    assert done == ()  # nothing reached the sandbox
    bundle = evaluation.new_bundles["C-2"]
    assert (bundle.files.as_dict(), bundle.invocation) == ({SCENARIO_PATH: DECLARATION}, ())
    # One ask per side, each under its own task, each on the tree acceptance judges.
    assert [r.task_id for r in port.asked] == [
        "campaign:cmp_1:inc_2:C-2:baseline",
        "campaign:cmp_1:inc_2:C-2:candidate",
    ]
    assert [json.loads(r.source_files[WORLD_PATH]) for r in port.asked] == [SHUT, OPEN]
    assert all(r.source_files[SCENARIO_PATH] == DECLARATION.decode() for r in port.asked)
    readings = evaluation.scenario_readings["C-2"]
    assert sorted(readings) == ["baseline", "candidate"]
    assert readings["candidate"]["source_revision"] == port.asked[1].source_revision


async def test_an_earlier_increments_scenario_that_the_candidate_breaks_rejects_it():
    port = _Port()
    earlier = FrozenCriterion("C-2", SCENARIO_PATH, scenario_bundle("C-2", _frozen_tree()))

    evaluation, _ = await _judge(port, candidate_world=SHUT, frozen=[earlier], new=False)

    [result] = evaluation.frozen
    assert (result.held, result.detail) == (Held.BROKEN, "door-open")
    assert evaluation.acceptance.verdict is IncrementVerdict.REJECTED
    assert [r.task_id for r in port.asked] == ["campaign:cmp_1:inc_2:C-2:candidate"]


async def test_an_earlier_scenario_the_candidate_keeps_holds():
    port = _Port()
    earlier = FrozenCriterion("C-2", SCENARIO_PATH, scenario_bundle("C-2", _frozen_tree()))

    evaluation, _ = await _judge(port, candidate_world=OPEN, frozen=[earlier], new=False)

    assert [(r.held, r.detail) for r in evaluation.frozen] == [(Held.HELD, "")]


async def test_a_declaration_delivered_unlike_the_one_approved_is_never_played():
    port = _Port()

    evaluation, _ = await _judge(port, candidate_world=OPEN, digests={"C-2": "sha256:" + "ab" * 32})

    [d] = evaluation.discriminations
    assert d.reason is DiscriminationReason.NOT_RUN
    assert d.detail == (
        f"the scenario at {SCENARIO_PATH} is {door_opens().digest}, and its approved change "
        f"request froze sha256:{'ab' * 32}"
    )
    assert port.asked == []
    assert evaluation.acceptance.verdict is IncrementVerdict.BLOCKED_UNVERIFIED


@pytest.mark.parametrize(
    ("scenarios", "why"),
    [
        (_scenarios(None, unavailable="this runtime binds no remote execution"),
         "this runtime binds no remote execution"),
        (_scenarios(_Port(), operation=None, unavailable="the record offers no operation"),
         "the record offers no operation"),
        (_scenarios(_Port(), vocabulary=None, unavailable="no reader kept"), "no reader kept"),
    ],
    ids=["no port", "no supplied operation", "no kept vocabulary"],
)  # fmt: skip
async def test_a_scenario_that_cant_be_asked_for_is_not_run_with_why(scenarios, why):
    evaluation, _ = await _judge(None, candidate_world=OPEN, scenarios=scenarios)

    [d] = evaluation.discriminations
    assert (d.met, d.reason, d.detail) == (False, DiscriminationReason.NOT_RUN, why)
    assert evaluation.acceptance.blocked == (f"criterion C-2: not run: {why}",)


def _frozen_tree() -> FileTree:
    return FileTree.of({SCENARIO_PATH: DECLARATION})


async def test_the_delivery_builds_scenario_runs_only_for_an_increment_that_has_one_and_says_why():
    """``product_acceptance.scenario_runs_for``, as ``evaluate_product_increment`` calls it. Bug
    caught: every increment made to resolve an operation it never plays (and fail for a cycle that
    supplies none), or a scenario increment's missing pieces read as one vague reason."""
    from squadops.execution import product_acceptance

    cycle = SimpleNamespace(skillset_record=None, campaign_id="cmp_1", cycle_id="cyc_1")
    runner_only = (NewCriterion("R-1", "tests/test_criterion_R_1.py"),)
    scenario = (NewCriterion("C-2", SCENARIO_PATH),)

    none = await product_acceptance.scenario_runs_for(
        cycle, "run_2", "inc_2", runner_only, None, None
    )
    runs = await product_acceptance.scenario_runs_for(cycle, "run_2", "inc_2", scenario, None, None)
    reading = await runs.read("C-2", ReadingSide.CANDIDATE, _frozen_tree(), door_opens())

    assert none is None
    assert reading.document is None
    assert reading.why.startswith(
        "this runtime binds no remote execution (remote_execution.provider none); "
    )
    assert "offers no operation contract" in reading.why


async def test_the_baseline_steps_overlay_is_the_one_delivery_plays_its_baseline_on():
    """#3044 2b, #3053: ``baseline_scenario_overlay`` (the baseline step, before development) and
    delivery's evaluation build one overlay. The pin holds an earlier increment's criterion file,
    which only the increment's placed-file rule keeps out. Bug caught: the two lanes staging
    different trees, so the reading taken before development binds to a revision delivery never
    judges and is never credited there; or the earlier criterion's file staged on one side only."""
    from squadops.campaigns.change_request import stored_change_request, validate_proposal
    from squadops.campaigns.increment_tree import increment_scenario_files
    from squadops.execution.product_acceptance import baseline_scenario_overlay
    from tests.unit.campaigns.test_product_increment_seams import _BLOCK, _cycle
    from tests.unit.campaigns.test_scenario_criterion import _ctx
    from tests.unit.campaigns.test_scenario_criterion import _request as scenario_request

    request = stored_change_request(validate_proposal(scenario_request(), _ctx()).change_request)
    earlier = "checks/check_criterion_F1.py"
    pin = {"criterion_id": "F1", "test_path": earlier, "bundle_ref": "a", "bundle_address": "b"}
    cycle = _cycle(campaign_proposal={**_BLOCK, "frozen_criteria": [pin]})
    head = {**_tree(SHUT, scenario=False), earlier: b"# an earlier increment's check\n"}
    declaration = increment_scenario_files(request)

    overlay = baseline_scenario_overlay(
        cycle, request, "C-2", accepted=FileTree.of(head), profile=_profile()
    )
    port = _Port()
    await evaluate_on_runner(
        _runs(),
        increment_id="inc_2",
        accepted=SandboxTree(head),
        candidate=SandboxTree(head, changes={**declaration, WORLD_PATH: json.dumps(OPEN).encode()}),
        new=[NewCriterion("C-2", SCENARIO_PATH)],
        frozen=[FrozenCriterion("F1", earlier, None)],
        retired=(),
        routes=(),
        scenarios=_scenarios(port),
        approved_digests={"C-2": door_opens().digest},
    )
    on_baseline = next(r for r in port.asked if r.task_id.endswith(":baseline"))

    assert on_baseline.source_files == {p: c.decode() for p, c in overlay.as_dict().items()}
    assert earlier not in on_baseline.source_files
    assert on_baseline.source_files[SCENARIO_PATH] == declaration[SCENARIO_PATH]
