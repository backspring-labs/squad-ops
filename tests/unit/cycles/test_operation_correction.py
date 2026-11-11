"""The correction route for a remote operation (SIP-0117 R4.4, R5.1; phase 2a, part 2).

A failed assertion is repaired in the application, and the repair is accepted only when the
operation, re-run on the repaired tree, executes every assertion and passes it. Each test
enters at a seam the live run calls: the repair's target, the runner's re-run and delivery
here, and the executor's outcome classification and patch acceptance in
``test_outcome_routing.py``, beside the fixtures they share."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.noop.ports import NoOpFailurePatternRecall
from squadops.cycles.failure_evidence import FailureLocus
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_outcome import TaskOutcome
from squadops.cycles.task_plan import REPAIR_TASK_STEPS, repair_steps_for
from squadops.execution.correction_repair import _locus_and_repair_target
from squadops.execution.execution_errors import _ExecutionError
from squadops.execution.source_delivery import squad_changes
from squadops.sandbox.models import RevisionOrigin, WorkspaceRevision
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 11, 10, tzinfo=UTC)
OPERATION = {
    "contract": "game.scenario_verification",
    "mode": "play",
    "role": "qa",
    "skillset": "fixture-qa",
    "skillset_digest": "digest-1",
    "agent_id": "eve",
}
SCENARIO = {"scenario_id": "open-the-map", "digest": "sha256:s", "assertions": ["opens", "closes"]}
TREE = {"src/map.py": "def open_map():\n    return False\n", "src/menu.py": "MENU = 1\n"}
SURFACE = ["src/map.py", "src/menu.py"]


def _row(assertion: str, status: str, reason: str = "") -> dict:
    check = f"scenario:open-the-map:{assertion}"
    row = {"check": check, "criterion_id": check, "status": status, "reason": reason}
    if status == "skipped":
        row["evidence_gap"] = True
    return row


def _records(name: str = "operation_assertions.json", content: str = "{}") -> dict:
    return {"name": name, "content": content, "type": "remote_operation_assertions"}


def _envelope(**inputs) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task-run_001-m002-qa.run_remote_operation",
        agent_id="eve",
        cycle_id="cyc_001",
        pulse_id="p",
        project_id="hello_squad",
        task_type="qa.run_remote_operation",
        correlation_id="corr",
        causation_id=None,
        trace_id="t",
        span_id="s",
        inputs={
            "resolved_config": {},
            "operation": OPERATION,
            "operation_scenario": SCENARIO,
            "implementation_artifacts": SURFACE,
            "acceptance_workspace_files": TREE,
            "workspace_revision_id": "rev_before",
            "acceptance_criteria": [],
            **inputs,
        },
        metadata={"role": "qa"},
    )


def _failed_result(*rows: dict, error: str = "scenario:open-the-map:opens: observed") -> TaskResult:
    return TaskResult(
        task_id="task-run_001-m002-qa.run_remote_operation",
        status="FAILED",
        outputs={
            "summary": "[qa] 1 passed, 1 failed",
            "role": "qa",
            "validation_result": {"checks": list(rows)},
            "artifacts": [_records(content='{"status": "completed", "run": "first"}')],
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
        },
        error=error,
    )


FAILED = _failed_result(
    _row("opens", "failed", "observed 'False', expected 'True'"), _row("closes", "passed")
)
REPAIR = [{"name": "src/map.py", "content": "def open_map():\n    return True\n"}]


# --- the repair: where it is aimed -----------------------------------------------------------


def test_an_operations_failure_routes_to_the_dev_repair_for_every_locus():
    for locus in (FailureLocus.SUBJECT, FailureLocus.OWN_ARTIFACT, FailureLocus.UNKNOWN):
        assert repair_steps_for("qa.run_remote_operation", locus) == REPAIR_TASK_STEPS


@pytest.mark.parametrize(
    ("analysis", "target"),
    [
        (None, SURFACE),
        ({"implicated_files": ["src/map.py"]}, ["src/map.py"]),
        ({"implicated_files": ["src/elsewhere.py", "operation_assertions.json"]}, SURFACE),
    ],
    ids=["no analysis", "the analyzer names a file of the plan", "the analyzer names none of it"],
)
def test_the_repair_is_aimed_at_the_implementation_never_at_the_operations_evidence(
    analysis, target
):
    """Bug caught: the loop's default aiming the repair at the failed task's own artifacts,
    which for an operation are its assertion records."""
    locus, expected, _focus, _description = _locus_and_repair_target(
        "qa.run_remote_operation", {"validation_result": {}}, _envelope().inputs, analysis
    )

    assert (locus, expected) == (FailureLocus.SUBJECT, target)


def test_an_operation_with_no_implementation_surface_is_refused_rather_than_aimed_at_nothing():
    with pytest.raises(_ExecutionError, match="no implementation surface"):
        _locus_and_repair_target(
            "qa.run_remote_operation", {}, _envelope(implementation_artifacts=[]).inputs
        )


def test_a_plan_that_runs_an_operation_and_authors_no_source_is_refused():
    plan = ImplementationPlan.from_yaml(
        yaml.safe_dump(
            {
                "version": 1,
                "project_id": "p",
                "cycle_id": "c",
                "prd_hash": "h",
                "tasks": [
                    {
                        "task_index": 0,
                        "task_type": "qa.run_remote_operation",
                        "role": "qa",
                        "focus": "open the map",
                        "description": "play",
                        "contract": "game.scenario_verification",
                        "mode": "play",
                    }
                ],
                "summary": {"total_dev_tasks": 0, "total_qa_tasks": 1, "total_tasks": 1},
            }
        )
    )

    assert plan.validate_operation_tasks() == [
        "Task(s) 0: the plan runs an operation and no task authors source, so there is no "
        "implementation for it to verify or for a repair to change"
    ]


# --- the re-run: the operation, on the repaired tree ------------------------------------------


def _runner(answer):
    from squadops.execution.correction_runner import CorrectionRunner

    class _Dispatcher:
        def __init__(self):
            self.dispatched = []

        async def dispatch_task(self, envelope, run_id, **_kwargs):
            self.dispatched.append(envelope)
            return answer(envelope)

        async def create_task_run_if_enabled(self, _flow_run_id, _envelope):
            return None

    dispatcher = _Dispatcher()
    runner = CorrectionRunner(
        cycle_registry=AsyncMock(),
        artifact_vault=AsyncMock(),
        event_bus=MagicMock(),
        task_dispatcher=dispatcher,
        store_artifact=AsyncMock(),
        failure_recall=NoOpFailurePatternRecall(),
    )
    return runner, dispatcher


_PROFILE = SquadProfile(
    profile_id="full",
    name="F",
    description="",
    version=1,
    agents=(AgentProfileEntry("eve", "qa", "m", True, {}, ("qa",)),),
    created_at=NOW,
)
_CYCLE = Cycle(
    cycle_id="cyc_001",
    project_id="hello_squad",
    created_at=NOW,
    created_by="s",
    prd_ref="prd",
    squad_profile_id="full",
    squad_profile_snapshot_ref="sha",
    task_flow_policy=TaskFlowPolicy(mode="sequential"),
    build_strategy="fresh",
)
_STATE = {
    "prior_outputs": {},
    "all_artifact_refs": [],
    "stored_artifacts": [],
    "completed_task_ids": [],
    "plan_delta_refs": [],
}


async def test_the_rerun_is_the_same_operation_on_the_candidate_with_the_repair_laid_over_it():
    """Bug caught: the re-run verifying the tree the operation already failed on, or a tree
    holding the failed run's own evidence files as if they were the product's."""
    runner, dispatcher = _runner(lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED"))
    patched = [
        *REPAIR,
        _records(),
        {"name": "console.log", "content": "x", "type": "remote_operation_evidence"},
    ]

    result = await runner.reexecute_operation(
        "run_001", _CYCLE, _envelope(), patched, 1, profile=_PROFILE, **_STATE
    )

    assert result is not None and result.status == "SUCCEEDED"
    (rerun,) = dispatcher.dispatched
    repaired_tree = {**TREE, "src/map.py": "def open_map():\n    return True\n"}
    assert rerun.inputs["acceptance_workspace_files"] == repaired_tree
    assert (
        rerun.inputs["workspace_revision_id"]
        == WorkspaceRevision.cut(
            cycle_id="cyc_001", origin=RevisionOrigin.ACCEPTANCE_ASSEMBLY, files=repaired_tree
        ).revision_id
    )
    assert rerun.inputs["workspace_revision_id"] != "rev_before"
    assert (rerun.inputs["operation"], rerun.inputs["operation_scenario"]) == (OPERATION, SCENARIO)
    assert rerun.inputs["implementation_artifacts"] == SURFACE
    assert (rerun.task_type, rerun.agent_id) == ("qa.run_remote_operation", "eve")
    assert rerun.task_id == "retest-run_001-01-s00-qa.run_remote_operation"
    assert rerun.causation_id == _envelope().task_id
    assert rerun.metadata == {"role": "qa", "retest": True}


@pytest.mark.parametrize(
    ("envelope", "patched"),
    [
        (_envelope(acceptance_workspace_files=None), REPAIR),
        (_envelope(), [_records()]),
        (_envelope(operation={k: v for k, v in OPERATION.items() if k != "role"}), REPAIR),
    ],
    ids=["no candidate tree", "a repair that changed no file", "no role recorded"],
)
async def test_nothing_is_rerun_when_there_is_nothing_to_run_it_on(envelope, patched):
    runner, dispatcher = _runner(lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED"))

    result = await runner.reexecute_operation(
        "run_001", _CYCLE, envelope, patched, 1, profile=_PROFILE, **_STATE
    )

    assert result is None
    assert dispatcher.dispatched == []


# --- delivery: the repaired source is part of what the squad changed --------------------------


def _ref(artifact_id: str, filename: str, artifact_type: str, producer: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        project_id="prj",
        cycle_id="cyc_1",
        run_id="run_1",
        artifact_type=artifact_type,
        filename=filename,
        content_hash="h",
        size_bytes=1,
        media_type="text/plain",
        created_at=NOW,
        metadata={"producing_task_type": producer},
    )


def test_source_accepted_from_an_operations_failure_is_delivered_and_its_evidence_is_not():
    """An accepted patch is re-stored as the failed task's own. Bug caught: delivery leaving
    out every producer that authors neither source nor a suite, so the repair that made the
    scenario pass never reaches the product's change."""
    checkout = {"src/map.py": b"def open_map():\n    return False\n"}
    repaired = _ref("art_1", "src/map.py", "source", "qa.run_remote_operation")
    records = _ref(
        "art_2",
        "operation_assertions.json",
        "remote_operation_assertions",
        "qa.run_remote_operation",
    )
    console = _ref("art_3", "console.log", "remote_operation_evidence", "qa.run_remote_operation")
    contents = {
        "art_1": b"def open_map():\n    return True\n",
        "art_2": b"{}",
        "art_3": b"log",
    }

    changes, left_out = squad_changes(
        [(r.artifact_id, r) for r in (repaired, records, console)], contents, checkout
    )

    assert changes == {"src/map.py": b"def open_map():\n    return True\n"}
    assert list(left_out) == []
