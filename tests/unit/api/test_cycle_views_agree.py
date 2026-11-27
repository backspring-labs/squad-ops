"""The 2.9 plan's item 3 (#3224, #3244): every view of a Campaign's cycles agrees.

Entered through the Spark lane's read (``scripts/dev/read_cycle_views.py``, ``read_project``),
as the done-when reads it on a deploy, with its ``get`` answered by the real runtime routes: the
campaign list, its ledger and control log, each cycle's route and the status-filtered cycle list,
over shared memory registries.

What bugs would these catch?
- A one-workload cycle (a Campaign's repair or retry) whose route names no ending though one is
  recorded (#3244: the 2.8.1 cut's two repair cycles).
- A cycle the status-filtered list leaves out under the status its own route gives (#3224: a
  cycle a gate ended, a cycle cancelled after it ended, a cycle waiting between workloads).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.cycles.factory import create_project_registry
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.api.routes.cycles.cycles import router as cycles_router
from squadops.campaigns.models import CampaignState, CycleKind, LaunchRequest
from squadops.cycles.cycle_end import CycleStopReason, RecordedEnd
from squadops.cycles.models import Run
from tests.unit.campaigns.builders import campaign, cycle_for, move, policy

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "read_cycle_views.py"
_spec = importlib.util.spec_from_file_location("read_cycle_views", _SCRIPT)
views = importlib.util.module_from_spec(_spec)
sys.modules["read_cycle_views"] = views
_spec.loader.exec_module(views)

S = CampaignState
CID = "cmp_views0000001"
PROJECT = "group_run"
_TWO_WORKLOADS = [{"type": "framing", "gate": "plan"}, {"type": "implementation"}]


class _Deploy:
    """The runtime's routes over shared memory registries, and a Campaign that launched one
    cycle of each shape the 2.8.1 cut and the Spark's 2026-11-26 read found."""

    def __init__(self) -> None:
        self.campaigns = MemoryCampaignRegistry()
        self.cycles = MemoryCycleRegistry()
        app = FastAPI()
        app.include_router(campaigns_router)
        app.include_router(cycles_router)
        register_domain_error_handlers(app)
        app.state.campaign_registry = self.campaigns
        app.state.cycle_registry = self.cycles
        app.state.project_registry = create_project_registry("config")
        self.client = TestClient(app)
        self.launched: dict[str, str] = {}

    def get(self, path: str, params: dict | None = None):
        resp = self.client.get(path, params=params)
        assert resp.status_code == 200, f"{path} {params}: {resp.status_code} {resp.text}"
        return resp.json()

    async def launch(self, name: str, to: CampaignState, kind: CycleKind, *, workloads=None):
        """Move the Campaign to ``to`` with a launch of ``kind``, and launch its cycle."""
        intent = (
            await self.campaigns.transition(CID, move(to, f"k-{name}", launch=LaunchRequest(kind)))
        ).intent
        cycle = cycle_for(intent, project_id=PROJECT)
        if workloads is not None:
            import dataclasses

            cycle = dataclasses.replace(cycle, applied_defaults={"workload_sequence": workloads})
        await self.cycles.create_cycle(cycle)
        await self.campaigns.mark_launch_intent_launched(
            intent.launch_id, cycle.cycle_id, actor="l"
        )
        self.launched[name] = cycle.cycle_id
        return cycle.cycle_id

    async def runs(self, cycle_id: str, *statuses: str, workload: str = "implementation") -> str:
        last = ""
        for n, status in enumerate(statuses, start=1):
            last = f"run_{cycle_id}_{n}"
            await self.cycles.create_run(
                Run(
                    run_id=last,
                    cycle_id=cycle_id,
                    run_number=n,
                    status=status,
                    initiated_by="campaign",
                    resolved_config_hash="h",
                    workload_type=workload,
                )
            )
        return last

    async def ended(self, cycle_id: str, last_run: str, reason: CycleStopReason) -> None:
        await self.cycles.record_cycle_end(RecordedEnd(cycle_id, last_run, reason))


@pytest.fixture
async def deploy() -> _Deploy:
    d = _Deploy()
    await d.campaigns.create_campaign(
        campaign(CID, policy=policy(), project_id=PROJECT),
        actor="o",
        actor_role="o",
        reason="r",
        idempotency_key="c",
    )
    # A calibration that ran to its end.
    cal = await d.launch("calibration", S.CALIBRATING, CycleKind.CALIBRATION)
    await d.ended(cal, await d.runs(cal, "completed"), CycleStopReason.SEQUENCE_COMPLETED)
    # An increment whose framing completed and whose gate rejected the plan (#3224).
    inc = await d.launch("increment", S.AT_PROPOSAL, CycleKind.INCREMENT, workloads=_TWO_WORKLOADS)
    await d.ended(
        inc, await d.runs(inc, "completed", workload="framing"), CycleStopReason.PLAN_REJECTED
    )
    await d.campaigns.transition(CID, move(S.AWAITING_RULING, "k-ruling"))
    await d.campaigns.transition(CID, move(S.BUILDING, "k-building"))
    await d.campaigns.transition(CID, move(S.EVALUATING, "k-evaluating"))
    # A repair cycle whose one run completed (#3244, ``cyc_aeb6c8e22b64``'s shape).
    rep = await d.launch("repair", S.REPAIRING, CycleKind.REPAIR)
    await d.ended(rep, await d.runs(rep, "completed"), CycleStopReason.SINGLE_WORKLOAD_ENDED)
    await d.campaigns.transition(CID, move(S.EVALUATING, "k-evaluating-2"))
    # A retry cycle whose one run was cancelled (#3244, ``cyc_bd5078b22c8e``'s shape).
    ret = await d.launch("retry", S.RETRYING, CycleKind.RETRY)
    await d.ended(ret, await d.runs(ret, "cancelled"), CycleStopReason.SINGLE_WORKLOAD_ENDED)
    return d


async def test_every_view_of_every_campaign_cycle_agrees(deploy):
    read = views.read_project(deploy.get, PROJECT)

    by_cycle = {seen.cycle_id: seen for seen in read}
    assert set(by_cycle) == set(deploy.launched.values())
    assert {c: seen.disagreements for c, seen in by_cycle.items()} == {c: [] for c in by_cycle}
    named = {
        name: (by_cycle[c].route_status, by_cycle[c].route_ending)
        for name, c in deploy.launched.items()
    }
    assert named == {
        "calibration": ("completed", "sequence_completed"),
        "increment": ("failed", "plan_rejected"),
        "repair": ("completed", "single_workload_ended"),
        "retry": ("cancelled", "single_workload_ended"),
    }
    assert views.main([PROJECT], get=deploy.get) == 0


async def test_a_cycle_cancelled_after_it_ended_is_listed_under_its_endings_status(deploy):
    """``cyc_929c449744f1``'s shape: the abort cancelled a cycle that had already ended. Its
    route reads the ending, with the conflict named, and the list returns it there."""
    cal = deploy.launched["calibration"]
    await deploy.cycles.cancel_cycle(cal)

    [seen] = [s for s in views.read_project(deploy.get, PROJECT) if s.cycle_id == cal]

    assert (seen.route_status, seen.route_ending, seen.route_conflict) == (
        "completed",
        "sequence_completed",
        "cancelled_after_ending",
    )
    assert (seen.listed_under_status, seen.disagreements) == (True, [])
