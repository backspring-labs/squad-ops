"""#2007: no flow run of a run's name stays open once the run has a live process or has ended.

A restart left the dead process's flow run ``RUNNING`` beside the re-attached process's, and nine
stayed open for 20–30 hours. The wiring tests enter at ``execute_run``, which the re-attach calls,
with a flow run of the run's name already open, as a dead process leaves it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from squadops.cycles.flow_runs import end_open_flow_runs
from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.naming import flow_run_name
from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort
from squadops.tasks.models import TaskResult

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 10, 5, 5, 0, 0, tzinfo=UTC)
_NAME = flow_run_name("hello_squad", "cyc_001", "run_001")
# What ``set_flow_run_state`` writes for an ended run, as the Prefect adapter does.
_ENDED = {"COMPLETED", "FAILED", "CANCELLED"}


class _Prefect(WorkflowTrackerPort):
    """Flow runs by id: ``[name, state]``. Opens them as the adapter does, finds the open ones by
    exact name, and records every state set."""

    def __init__(self, open_before: dict[str, str] | None = None) -> None:
        self.runs: dict[str, list[str]] = {
            fid: [name, "RUNNING"] for fid, name in (open_before or {}).items()
        }
        self.created = 0
        self.fail_set: set[str] = set()
        self.events: list[str] = []

    async def ensure_flow(self, flow_name: str = "cycle-execution") -> str:
        return "flow"

    async def create_flow_run(self, flow_id, run_name, parameters=None, tags=()) -> str:
        self.created += 1
        fid = f"fr-live-{self.created}"
        self.runs[fid] = [run_name, "SCHEDULED"]
        self.events.append(f"open {fid}")
        return fid

    async def create_task_run(self, flow_run_id, task_key, task_name) -> str:
        return f"tr-{task_key}"

    async def find_active_flow_run_ids(self, run_names):
        return [f for f, (n, s) in self.runs.items() if n in run_names and s not in _ENDED]

    async def set_flow_run_state(self, flow_run_id, run_status) -> None:
        if flow_run_id in self.fail_set:
            raise RuntimeError("prefect 500")
        self.runs[flow_run_id][1] = run_status.value.upper()
        self.events.append(f"{flow_run_id} {run_status.value.upper()}")

    async def set_task_run_state(self, task_run_id, state_type, state_name) -> None:
        return None

    async def close(self) -> None:
        return None


def _executor(prefect, reply_router):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    cycle = Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref="prd",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )
    registry = AsyncMock()
    registry.get_cycle.return_value = cycle
    registry.get_run.return_value = Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )
    registry.get_latest_checkpoint.return_value = None
    agents = tuple(
        AgentProfileEntry(agent_id=a, role=r, model="m", enabled=True, serves_roles=(r,))
        for a, r in (("nat", "strat"), ("neo", "dev"), ("eve", "qa"), ("data", "data"))
        + (("max", "lead"),)
    )
    profiles = AsyncMock()
    profiles.resolve_snapshot.return_value = (
        SquadProfile(
            profile_id="full",
            name="Full",
            description="All",
            version=1,
            agents=agents,
            created_at=NOW,
        ),
        "sha256:abc",
    )
    vault = AsyncMock()
    vault.store.side_effect = lambda ref, content: ref
    reply_router.responder = lambda env: TaskResult(
        task_id=env["task_id"], status="SUCCEEDED", outputs={"summary": "ok", "artifacts": []}
    )
    return DispatchedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=vault,
        queue=reply_router.bind(AsyncMock()),
        squad_profile=profiles,
        project_registry=None,
        campaign_registry=None,
        campaign_progress=None,
        box_verdict=None,
        task_timeout=5.0,
        reply_router=reply_router,
        workflow_tracker=prefect,
    )


async def _execute(executor) -> None:
    with patch("adapters.cycles.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock):
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")


async def test_a_re_attached_run_ends_the_flow_run_its_dead_process_left_open(reply_router):
    """Bug caught: the re-attach opening a second flow run for the run and leaving the first
    ``RUNNING`` forever (rebuild 18's diagnostics: one beside each proposal and framing run)."""
    prefect = _Prefect(
        open_before={"fr-dead": _NAME, "fr-other-run": "hello_squad/cyc_001/run_002"}
    )

    await _execute(_executor(prefect, reply_router))

    assert prefect.runs["fr-dead"] == [_NAME, "CANCELLED"]
    assert prefect.runs["fr-live-1"] == [_NAME, "COMPLETED"]
    # Ended when the re-attach opened its own, not only at the run's end: while it runs, the
    # run shows one live flow run.
    assert prefect.events.index("fr-dead CANCELLED") < prefect.events.index("open fr-live-1")
    # Another run's flow run is not this run's to end.
    assert prefect.runs["fr-other-run"][1] == "RUNNING"


async def test_the_runs_end_ends_a_flow_run_opened_after_its_own(reply_router):
    """Bug caught: the run's end closing only the flow run this process opened. One a dead
    process opened under the same name after this one's (its own re-attach raced it) stays open."""
    prefect = _Prefect()
    executor = _executor(prefect, reply_router)
    real_create = prefect.create_flow_run

    async def create_then_a_stray_appears(*args, **kwargs):
        fid = await real_create(*args, **kwargs)
        prefect.runs["fr-stray"] = [_NAME, "RUNNING"]
        return fid

    prefect.create_flow_run = create_then_a_stray_appears
    await _execute(executor)

    assert prefect.runs["fr-stray"] == [_NAME, "CANCELLED"]
    assert prefect.runs["fr-live-1"] == [_NAME, "COMPLETED"]


async def test_one_flow_run_that_cannot_be_ended_does_not_stop_the_others():
    prefect = _Prefect(open_before={"fr-a": _NAME, "fr-b": _NAME, "fr-c": _NAME})
    prefect.fail_set = {"fr-b"}

    ended = await end_open_flow_runs(prefect, [_NAME], keep="fr-c")

    assert ended == ["fr-a"]
    assert prefect.runs["fr-b"][1] == "RUNNING"
    assert prefect.runs["fr-c"][1] == "RUNNING"  # the caller's own, ended by the caller


@pytest.mark.parametrize(("tracker", "names"), [(None, [_NAME]), (_Prefect(), [])])
async def test_nothing_to_end_ends_nothing(tracker, names):
    assert await end_open_flow_runs(tracker, names) == []


async def test_a_tracker_that_cannot_list_ends_nothing_and_does_not_raise():
    prefect = _Prefect(open_before={"fr-a": _NAME})
    prefect.find_active_flow_run_ids = AsyncMock(side_effect=RuntimeError("prefect down"))

    assert await end_open_flow_runs(prefect, [_NAME]) == []
    assert prefect.runs["fr-a"][1] == "RUNNING"
