"""SIP-0117 R5.32 (#3200): a candidate's own setup failure gets one correction in the run.

Entered where the live run enters: ``_TaskOutcomeRouter.screen``, which the dispatcher is handed
as ``screen_success`` and calls on every attempt an agent reports succeeded, and then the
executor's classification of the failure it returns. The play's reading is built by
``records_document``, as the handler builds it."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from squadops.cycles.models import ArtifactRef
from squadops.cycles.task_outcome import TaskOutcome
from squadops.execution import setup_failure_correction as seam
from squadops.execution.dispatched_flow_executor import DispatchedFlowExecutor, _TaskOutcomeRouter
from squadops.execution.execution_errors import _ExecutionError
from squadops.projects.models import CheckoutTree
from squadops.remote_execution.models import (
    ASSERTION_RECORDS_ARTIFACT_TYPE,
    AssertionOutcome,
    AssertionRecord,
    OperationStatus,
    ReadingSide,
    RemoteOperationResult,
    ScriptError,
    records_document,
)
from squadops.tasks.models import TaskEnvelope, TaskResult, TaskResultStatus
from tests.unit.remote_execution.registry_contract import request

pytestmark = [pytest.mark.domain_orchestration]

SCREEN = "src/client/screen.luau"
BASELINE_TEXT = "return {}\n"
CANDIDATE_TEXT = "local panel = {}\npanel.Shown = true\nreturn panel\n"
ERROR = ScriptError(SCREEN, 2, "Shown is not a valid member of Panel")
RAN_WITH = {"environment": "env-1", "served_by": "worker-a"}
TASK_ID = "task-run_1-005-qa.run_remote_operation"
NOW = datetime(2026, 11, 26, tzinfo=UTC)


def _asked(text: str):
    asked = request()
    return dataclasses.replace(asked, source_files={**asked.source_files, SCREEN: text})


def _reading(side: ReadingSide, outcome: AssertionOutcome, *errors: ScriptError, **changes):
    text = CANDIDATE_TEXT if side is ReadingSide.CANDIDATE else BASELINE_TEXT
    asked = _asked(text)
    result = RemoteOperationResult(
        status=OperationStatus.COMPLETED,
        records=tuple(
            AssertionRecord(a, outcome, "", "", "client") for a in asked.scenario.assertions
        ),
        ran_with=dict(RAN_WITH),
        script_errors=tuple(errors),
        dispatch_id=asked.dispatch_id,
    )
    return records_document(asked, dataclasses.replace(result, **changes), side, not_staged=())


def _played(reading: dict) -> TaskResult:
    """The handler's result for a play whose assertions didn't execute: succeeded, with its
    rows skipped and its reading among its artifacts."""
    rows = [
        {
            "check": f"scenario:{reading['scenario']['scenario_id']}:{a['assertion_id']}",
            "status": "skipped",
            "reason": a["outcome"],
            "evidence_gap": True,
        }
        for a in reading["assertions"]
    ]
    return TaskResult(
        task_id=TASK_ID,
        status=TaskResultStatus.SUCCEEDED,
        outputs={
            "summary": "[qa] 0 passed, 0 failed, 2 not executed of 2",
            "role": "qa",
            "validation_result": {"checks": rows},
            "artifacts": [
                {
                    "name": "operation_assertions.json",
                    "content": json.dumps(reading),
                    "type": ASSERTION_RECORDS_ARTIFACT_TYPE,
                }
            ],
        },
    )


def _envelope() -> TaskEnvelope:
    return TaskEnvelope(
        task_id=TASK_ID,
        agent_id="qa-agent",
        cycle_id="cyc_1",
        pulse_id="p",
        project_id="prj-game",
        task_type="qa.run_remote_operation",
        correlation_id="corr",
        causation_id=None,
        trace_id="t",
        span_id="s",
        inputs={
            "implementation_artifacts": [SCREEN],
            "acceptance_workspace_files": dict(_asked(CANDIDATE_TEXT).source_files),
        },
        metadata={"role": "qa"},
    )


class _Vault:
    """A vault holding this cycle's baseline readings, newest last."""

    def __init__(self, *baselines: dict) -> None:
        self._held = {
            f"art_base_{n}": json.dumps(reading).encode() for n, reading in enumerate(baselines)
        }

    async def list_artifacts(self, *, cycle_id, artifact_type):
        assert (cycle_id, artifact_type) == ("cyc_1", ASSERTION_RECORDS_ARTIFACT_TYPE)
        return [
            ArtifactRef(
                artifact_id=artifact_id,
                project_id="prj-game",
                cycle_id="cyc_1",
                run_id="run_1",
                artifact_type=artifact_type,
                filename="operation_assertions.baseline.json",
                content_hash="h",
                size_bytes=len(content),
                media_type="application/json",
                created_at=NOW.replace(minute=n),
                metadata={"side": "baseline", "criterion_id": request().scenario.scenario_id},
            )
            for n, (artifact_id, content) in enumerate(self._held.items())
        ]

    async def retrieve(self, artifact_id):
        return None, self._held[artifact_id]


@pytest.fixture
def world(monkeypatch):
    """The pinned checkout and the approved change request, as the seam reads them."""

    async def change_request(_vault, _cycle):
        return "the approved change request"

    async def tree(_repository, _project, _locator, _ref, commit):
        files = {p: t.encode() for p, t in _asked(BASELINE_TEXT).source_files.items()}
        return CheckoutTree(commit, files, frozenset(), frozenset(), frozenset(), frozenset())

    monkeypatch.setattr(seam, "approved_change_request", change_request)
    monkeypatch.setattr(seam, "approved_footprint", lambda _doc: ("src/client/**",))
    monkeypatch.setattr(seam, "baseline_tree", tree)


def _router(vault, *, budget: int = 3, spent_corrections: int = 0):
    executor = object.__new__(DispatchedFlowExecutor)
    executor._artifact_vault = vault
    executor._source_repository = object()
    executor._project_registry = SimpleNamespace(
        get_project=_returning(SimpleNamespace(source=SimpleNamespace(base_ref="main")))
    )

    async def no_head_reading(*_a, **_k):
        return None

    executor._read_criteria_on_head = no_head_reading
    state = SimpleNamespace(
        produced=SimpleNamespace(all_artifact_refs=[], stored_artifacts=[]),
        correction=SimpleNamespace(
            counter={"n": spent_corrections},
            refused_on_head=set(),
            rejection_carry={},
            head_readings={},
            setup_failure_repaired=set(),
        ),
    )
    cycle = SimpleNamespace(
        cycle_id="cyc_1",
        project_id="prj-game",
        source_context=SimpleNamespace(repo_uri="git@example:game.git", pinned_commit="c0ffee"),
        resolved_config=lambda: {"max_correction_attempts": budget},
    )
    envelope = _envelope()
    router = _TaskOutcomeRouter(
        executor=executor,
        state=state,
        envelope=envelope,
        enriched=envelope,
        cycle=cycle,
        run_id="run_1",
        flow_run_id=None,
        profile=None,
        interface_manifest=None,
        budget_guard=lambda: None,
        ledger=None,
    )
    return router, executor, state, cycle


def _returning(value):
    async def call(*_a, **_k):
        return value

    return call


def _kept(result: TaskResult) -> dict:
    [artifact] = [a for a in result.outputs["artifacts"] if a["name"] == "setup_attribution.json"]
    return json.loads(artifact["content"])


def _classify(executor, cycle, result):
    return executor._classify_unhandled_outcome(
        result.outputs.get("outcome_class"), result, _envelope(), cycle, {}, enriched_envelope=None
    )


CANDIDATE = _reading(ReadingSide.CANDIDATE, AssertionOutcome.SETUP_FAILED, ERROR)
BASELINE = _reading(ReadingSide.BASELINE, AssertionOutcome.FAILED)


async def test_an_attributed_setup_failure_is_refused_to_correction_with_the_error(world):
    """Bug caught: the play accepted as unverified, so the run ends blocked with a fault its
    first play's log had already named, and no repair is tried (rehearsal 3 of the 2.8 window)."""
    router, executor, state, cycle = _router(_Vault(BASELINE))
    played = _played(CANDIDATE)

    refused = await router.screen(played)

    assert refused.status == TaskResultStatus.FAILED
    assert refused.outputs["outcome_class"] == TaskOutcome.SEMANTIC_FAILURE
    assert "src/client/screen.luau line 2: Shown is not a valid member of Panel" in refused.error
    # No unexecuted assertion became an executed failure: the rows are the play's own.
    assert refused.outputs["validation_result"] == played.outputs["validation_result"]
    kept = _kept(refused)
    assert (kept["attributed"], kept["repair"], kept["baseline_reading"]) == (
        True,
        "dispatched",
        "art_base_0",
    )
    assert [c["holds"] for c in kept["conditions"]] == [True] * 6
    assert state.correction.setup_failure_repaired == {TASK_ID}
    # The executor's gate lets it on to the correction loop, with no executed failure in it.
    assert _classify(executor, cycle, refused) is None


@pytest.mark.parametrize(
    ("baselines", "failing"),
    [
        ((), "baseline_setup_met"),
        (
            (_reading(ReadingSide.BASELINE, AssertionOutcome.FAILED, ERROR),),
            "error_absent_from_baseline",
        ),
        (
            (
                _reading(
                    ReadingSide.BASELINE,
                    AssertionOutcome.FAILED,
                    ran_with={**RAN_WITH, "served_by": "worker-b"},
                ),
            ),
            "same_environment",
        ),
    ],
    ids=["no baseline in the cycle", "the baseline raised it too", "another worker's play"],
)
async def test_a_setup_failure_that_isnt_attributed_keeps_todays_routing(world, baselines, failing):
    """The play stays succeeded with its unverified rows, and the reading is kept all the same,
    naming the condition that didn't hold."""
    router, _executor, state, _cycle = _router(_Vault(*baselines))
    played = _played(CANDIDATE)

    kept_result = await router.screen(played)

    assert kept_result.status == TaskResultStatus.SUCCEEDED
    assert kept_result.error is None
    assert "outcome_class" not in kept_result.outputs
    kept = _kept(kept_result)
    assert (kept["attributed"], kept["repair"]) == (False, "not_dispatched")
    assert failing in [c["condition"] for c in kept["conditions"] if not c["holds"]]
    assert state.correction.setup_failure_repaired == set()


async def test_the_newest_baseline_reading_is_the_one_read(world):
    """A retried run stores a second baseline reading. Bug caught: the first one read, so an
    error the newest baseline also raised is attributed to the candidate."""
    stale = BASELINE
    newest = _reading(ReadingSide.BASELINE, AssertionOutcome.FAILED, ERROR)
    router, *_ = _router(_Vault(stale, newest))

    kept = _kept(await router.screen(_played(CANDIDATE)))

    assert (kept["attributed"], kept["baseline_reading"]) == (False, "art_base_1")


@pytest.mark.parametrize(
    ("budget", "spent_corrections", "already", "why"),
    [
        (0, 0, False, seam.NOT_REPAIRED_NO_BUDGET),
        (2, 2, False, seam.NOT_REPAIRED_NO_BUDGET),
        (3, 0, True, seam.NOT_REPAIRED_ALREADY),
    ],
    ids=["in-run correction off", "the run's corrections are spent", "this task had its one"],
)
async def test_an_attributed_failure_with_no_correction_to_spend_stays_unverified(
    world, budget, spent_corrections, already, why
):
    """With ``max_correction_attempts`` 0 the 2.8.1 row-8 diagnostic must still end blocked and
    route to the Campaign's repair. Bug caught: the screen refusing anyway, so the run fails on
    an exhausted budget and row 8 is never reached."""
    router, _executor, state, _cycle = _router(
        _Vault(BASELINE), budget=budget, spent_corrections=spent_corrections
    )
    if already:
        state.correction.setup_failure_repaired.add(TASK_ID)

    kept_result = await router.screen(_played(CANDIDATE))

    assert kept_result.status == TaskResultStatus.SUCCEEDED
    kept = _kept(kept_result)
    assert (kept["attributed"], kept["repair"], kept["not_repaired_because"]) == (
        True,
        "not_dispatched",
        why,
    )


async def test_a_pin_that_cant_be_read_attributes_nothing(world, monkeypatch):
    """Evidence missing. No file reads as changed, so the third condition fails by name."""

    async def unreadable(*_a, **_k):
        raise RuntimeError("the managed clone is gone")

    monkeypatch.setattr(seam, "baseline_tree", unreadable)
    router, *_ = _router(_Vault(BASELINE))

    kept = _kept(await router.screen(_played(CANDIDATE)))

    assert kept["attributed"] is False
    [third] = [c for c in kept["conditions"] if c["condition"] == "error_in_changed_footprint_file"]
    assert third["evidence"] == (
        "no named error is in a changed file: src/client/screen.luau (unchanged by the candidate)"
    )


@pytest.mark.parametrize(
    "reading",
    [
        _reading(ReadingSide.CANDIDATE, AssertionOutcome.PASSED),
        _reading(ReadingSide.CANDIDATE, AssertionOutcome.MISSING),
    ],
    ids=["a play that passed", "a play that recorded nothing"],
)
async def test_a_play_whose_setup_didnt_fail_is_passed_on_untouched(world, reading):
    router, *_ = _router(_Vault(BASELINE))
    played = _played(reading)

    assert await router.screen(played) is played


async def test_an_unexecuted_play_with_no_attribution_still_ends_the_run_if_it_failed(world):
    """The gate's other side. A failed result of this task with neither an executed failure nor
    an attribution ends the run, as R5.1 has it."""
    router, executor, _state, cycle = _router(_Vault())
    failed = dataclasses.replace(
        _played(CANDIDATE),
        status=TaskResultStatus.FAILED,
        outputs={
            **_played(CANDIDATE).outputs,
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "setup_attribution": {"attributed": False},
        },
        error="provider raised",
    )

    with pytest.raises(_ExecutionError, match="no executed failure to repair"):
        _classify(executor, cycle, failed)


def test_the_reading_this_reads_is_the_file_the_handler_writes():
    from squadops.capabilities.handlers.cycle.run_remote_operation import (
        ASSERTION_RECORDS_FILENAME,
    )

    assert seam._CANDIDATE_READING == ASSERTION_RECORDS_FILENAME
