"""SIP-0117 R5.30's Studio half (#3236): a cancelled play names what it ran on, and nothing more.

A result the serve loop builds itself, the ``interrupted`` it answers a cancel with, carries
what the run had established (``running_with()``), read after the run is stopped and before
the tool is reset. Entered at ``Worker.serve()`` over the real registry, with
``RobloxStudioRunner`` over the stand-in ``StudioMCP``. The play is held at one step of its
own session, and its cycle cancelled there.

What bugs would these catch?
- A cancelled play's record that names no Studio, place or harness, so what ran isn't on the
  record (R5.30: "everything that actually ran stays on the record"). On main it read
  ``ran_with {}`` (#3236's premise).
- A record naming a fact the run never reached: a cancel before the proof carrying a
  ``qualified.*`` or ``played.*`` identity, or one before the place was read carrying its
  baseline.
- One run's facts carried into the next run's cancel.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from adapters.remote_execution.game_dev_roblox_studio.runner import RobloxStudioRunner
from adapters.remote_execution.game_dev_roblox_studio.session import StudioMcpSession
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.remote_execution.models import OperationStatus
from squadops.remote_execution.registry import WorkerRegistry
from squadops.remote_execution.serving import REASON_CANCELLED, Worker
from squadops.remote_execution.workers import Enqueued, OperationState
from tests.unit.remote_execution.registry_contract import Clock, cycle_cancel
from tests.unit.remote_execution.test_roblox_studio_place_state import BASELINE
from tests.unit.remote_execution.test_roblox_studio_play_scenario import (
    PROVED,
    STANDIN,
    _files,
    _Mac,
    _played,
    _request,
)
from tests.unit.remote_execution.worker_harness import RegistryWorkerApi, Serving, sleeping_on

#: The run's own facts, which it holds from the moment the request is read as its own.
RUN = {"roblox-studio", "reader", "source_revision"}
#: Read once the running Studio is held to its proof (R5.29).
PROOF = {
    "qualified.studio_version",
    "qualified.studio_channel",
    "qualified.studio_tools",
    "played.studio_version",
    "played.studio_channel",
    "played.studio_tools",
}


class _Hold:
    """The stand-in, with one harness session held at one step once armed: its ``open``, or
    one tool's call. The ``skip`` harness sessions opened before it pass. A held step never
    answers, so the play is stopped there."""

    def __init__(self, world: Path) -> None:
        self.world, self.at, self.skip, self.reached = world, "", 0, asyncio.Event()

    def arm(self, at: str, *, skip: int = 0) -> None:
        self.at, self.skip, self.reached = at, skip, asyncio.Event()

    def session(self, **kw) -> StudioMcpSession:
        session = StudioMcpSession([sys.executable, str(STANDIN), str(self.world)], **kw)
        if not (kw.get("harness") and self.at):
            return session
        if self.skip:
            self.skip -= 1
            return session
        at, self.at = self.at, ""  # once: the reset after the cancel runs as usual
        if at == "open":
            session.open = self._held
            return session
        if at.startswith("program:"):
            run_program = session.run_program

            async def held_program(name, *args, **kwargs):
                if name == at.removeprefix("program:"):
                    await self._held()
                return await run_program(name, *args, **kwargs)

            session.run_program = held_program
            return session
        call = session.call

        async def held_call(tool, arguments):
            if tool == at:
                await self._held()
            return await call(tool, arguments)

        session.call = held_call
        return session

    async def _held(self, *args):
        self.reached.set()
        await asyncio.Event().wait()


class _ArmsOnReopen(_Mac):
    """The Mac, calling ``on_reopen`` once, when a reset next reopens the place."""

    on_reopen = None

    def open(self, place_file: Path) -> None:
        super().open(place_file)
        armed, self.on_reopen = self.on_reopen, None
        if armed is not None:
            armed()


class _Deploy:
    """One worker serving the stand-in, over a registry in process."""

    def __init__(self, tmp_path: Path) -> None:
        self.world = world = _played(tmp_path)
        self.hold = _Hold(world)
        self.mac = _ArmsOnReopen(world=world)
        self.clock = Clock()
        self.store = MemoryWorkerRegistryStore()
        self.registry = WorkerRegistry(self.store, clock=self.clock)
        runner = RobloxStudioRunner(
            Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"),
            session_factory=self.hold.session,
            studio_version_of=lambda _: "0.747.0",
            discover_seconds=0.2,
            reopen_seconds=1.0,
            place_files=_files(tmp_path),
            proved_on=PROVED,
            app=self.mac,
        )
        self.worker = Worker(
            RegistryWorkerApi(self.registry, self.clock), runner,
            worker_id="macbook", platform="darwin-arm64",
            clock=self.clock, sleep=sleeping_on(self.clock),
        )  # fmt: skip

    async def registered(self) -> bool:
        await asyncio.sleep(0.01)  # the stand-in's sessions are real processes, in real time
        return bool(await self.registry.sessions())

    async def play(self, serving: Serving, cycle: str, *, cancel_at: str = "", held=False):
        """Queue a play for ``cycle``. With ``cancel_at``, hold its session there, or with
        ``held`` wait for a hold armed otherwise, and cancel the cycle once it is held.
        Returns the operation's stored result once it has settled."""
        if cancel_at:
            self.hold.arm(cancel_at)
        enqueued = await self.registry.enqueue(
            _request(dispatch_id=f"dispatch-{cycle}"),
            {"cycle_id": cycle},
            max_attempts=1,
            only_with_worker=False,
        )
        assert isinstance(enqueued, Enqueued), enqueued
        operation_id = enqueued.operation.operation_id

        async def is_held() -> bool:
            await asyncio.sleep(0.01)
            return self.hold.reached.is_set()

        async def settled() -> bool:
            await asyncio.sleep(0.01)
            async with self.store.exclusive() as tx:
                return (await tx.operation(operation_id)).state is OperationState.SETTLED

        if cancel_at or held:
            await serving.until(is_held, turns=6000)
            await cycle_cancel(self.registry, cycle)
        await serving.until(settled, turns=6000)
        async with self.store.exclusive() as tx:
            return (await tx.operation(operation_id)).result


#: R5.37 point 7: an input play with Studio already in front, on a worker that isn't dedicated.
FRONT = {"front.input", "front.activated", "front.was"}


def _named(result) -> set[str]:
    """What the run named of itself: every key but the harness digests and the registry's own
    word on who served the result, which it adds at acceptance (R5.32)."""
    assert result.ran_with["served_by"] == "macbook"
    return {k for k in result.ran_with if not k.startswith("harness.") and k != "served_by"}


@pytest.mark.parametrize(
    ("cancel_at", "established"),
    [
        # Before the session opened: the run's own facts and its harness, and no Studio.
        ("open", RUN),
        # After the proof, before the place was found: the Studio, and no place.
        # R5.37: the scenario has input, so how its input was allowed is named once read.
        ("list_roblox_studios", RUN | PROOF | FRONT),
        # During the sync (R5.36): the pin check's own reading is the place's baseline already.
        ("program:sync", RUN | PROOF | FRONT | {"place_baseline"}),
        # Mid-scenario, at the setup's click: the place's baseline too, and no play session.
        ("user_mouse_input", RUN | PROOF | FRONT | {"place_baseline"}),
    ],
    ids=["before-the-proof", "after-the-proof", "during-the-sync", "mid-scenario"],
)
async def test_a_cancelled_play_names_what_it_had_read_and_nothing_more(
    tmp_path, cancel_at, established
):
    deploy = _Deploy(tmp_path)

    async with Serving(deploy.worker) as serving:
        await serving.until(deploy.registered, turns=6000)
        result = await deploy.play(serving, "cyc_cancelled", cancel_at=cancel_at)

    assert (result.status, result.reason) == (OperationStatus.INTERRUPTED, REASON_CANCELLED)
    assert _named(result) == established
    assert any(k.startswith("harness.") for k in result.ran_with)
    assert result.ran_with["source_revision"] == "rev_candidate"
    if "played.studio_version" in established:
        assert (
            result.ran_with["played.studio_version"],
            result.ran_with["played.studio_channel"],
        ) == (
            "0.747.0",
            "production",
        )
        assert result.ran_with["qualified.studio_tools"] == PROVED.studio_tools


async def test_one_plays_facts_are_not_carried_into_the_next_plays_cancel(tmp_path):
    """A play that completed, then one cancelled before its session opened: the second names
    none of the first's Studio, place or play session."""
    deploy = _Deploy(tmp_path)

    async with Serving(deploy.worker) as serving:
        await serving.until(deploy.registered, turns=6000)
        played = await deploy.play(serving, "cyc_played")
        cancelled = await deploy.play(serving, "cyc_cancelled", cancel_at="open")

    assert played.status is OperationStatus.COMPLETED, played.reason
    assert {"place_baseline", "play_session", "played.studio_version"} <= _named(played)
    assert _named(cancelled) == RUN


async def test_a_second_attempt_after_a_drifted_place_starts_from_the_runs_own_facts(tmp_path):
    """R5.17: a place that isn't its pinned baseline is reset, and the transaction begun again
    on the Studio the reset reopened. Cancelled before that attempt's session opened, the play
    names none of the first attempt's Studio: it was read of a process the reset quit."""
    deploy = _Deploy(tmp_path)

    async with Serving(deploy.worker) as serving:
        await serving.until(deploy.registered, turns=6000)
        doc = json.loads(deploy.world.read_text())
        doc["baseline"] = [*BASELINE, "Workspace.Part.Anchored=false"]  # the place drifted
        deploy.world.write_text(json.dumps(doc))
        # The reset's own confirmation of the reopened place passes; the next attempt holds.
        deploy.mac.on_reopen = lambda: deploy.hold.arm("open", skip=1)
        result = await deploy.play(serving, "cyc_cancelled", held=True)

    assert (result.status, result.reason) == (OperationStatus.INTERRUPTED, REASON_CANCELLED)
    # The worker's start, the drift's reset, and the reset after the cancel.
    assert deploy.mac.done.count("quit") == 3
    assert _named(result) == RUN
