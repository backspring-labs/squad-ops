#!/usr/bin/env python3
"""Prove ``roblox-studio/play_scenario`` on the worker, across a Studio restart (#3039).

# Platform: dev-mac (Roblox Studio and its StudioMCP run on the worker's Mac)

The worker's own loop (``Worker.serve``, the call ``worker_main`` makes) runs the runner its
package creates from the worker's settings (``SQUADOPS__WORKER__ROBLOX_STUDIO_*``). The runtime
is in this process: the real ``WorkerRegistry`` over its memory store, called as the worker's
HTTP client would call it. Nothing connects to another machine. Three rounds:

1. a scenario is queued, claimed and played, and its records read;
2. a second is cancelled while it plays, so the worker stops it and resets its tool. Studio is
   quit, the place restored from its baseline file, and Studio reopened, with no person
   involved;
3. a third is played on the restarted Studio.

Studio's input acts only on a Studio in front (R5.18), so Studio must be in front at the start
and again after the reopening. Round 3 says so when it isn't.

    python scripts/dev/studio_worker_proof.py ~/Code/z_tower-ascension scenario.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import time
from collections.abc import Mapping
from pathlib import Path

from adapters.remote_execution.game_dev_roblox_studio import worker as studio_worker
from adapters.remote_execution.game_dev_roblox_studio.front import SETTINGS as FRONT_SETTINGS
from adapters.remote_execution.game_dev_roblox_studio.runner import OPERATION, PROVIDER
from adapters.remote_execution.game_dev_roblox_studio.vocabulary import VOCABULARY
from adapters.remote_execution.memory_worker_registry_store import MemoryWorkerRegistryStore
from squadops.ports.remote_execution import WorkerApiPort
from squadops.remote_execution.models import RemoteOperationRequest
from squadops.remote_execution.registry import WorkerRegistry, cadence
from squadops.remote_execution.scenario import frozen_scenario, staged_revision
from squadops.remote_execution.serving import Worker
from squadops.remote_execution.workers import Enqueued, Enrolment, OperationState

_PREFIX = "SQUADOPS__WORKER__"
#: Whose operations the proof's are (R5.30, #3282): an operation names its owner, or the registry
#: refuses it. The proof's registry is its own, in this process, and holds no cycle.
OWNER = {"cycle_id": "cyc_studio_worker_proof"}
#: How long a round may take before the proof gives up on it.
ROUND_SECONDS = 600.0
#: How long round 2 plays before it is cancelled.
CANCEL_AFTER_SECONDS = 20.0


class InProcessWorkerApi(WorkerApiPort):
    """The runtime as the worker calls it, straight onto the registry."""

    def __init__(self, registry: WorkerRegistry) -> None:
        self._registry = registry

    async def register(self, registration):
        session = await self._registry.register(registration)
        heartbeat, lease = cadence()
        return Enrolment(session.session_id, heartbeat, lease)

    async def heartbeat(self, session_id, runtime_status):
        await self._registry.heartbeat(session_id, runtime_status, None)

    async def renew(self, session_id, runtime_status, fence):
        return await self._registry.heartbeat(session_id, runtime_status, fence)

    async def claim(self, session_id):
        return await self._registry.claim(session_id)

    async def submit_result(self, fence, result):
        return await self._registry.submit_result(fence, result)

    async def close(self):
        return None


def _request(repo: Path, scenario_file: Path, round_no: int) -> RemoteOperationRequest:
    files = {
        p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((repo / "src").rglob("*"))
        if p.is_file()
    }
    return RemoteOperationRequest(
        contract="game.scenario_verification", mode="play", provider=PROVIDER,
        operation=OPERATION, location="worker", source_revision=staged_revision(files),
        source_files=files,
        scenario=frozen_scenario(json.loads(scenario_file.read_text()), VOCABULARY),
        task_id=f"proof-round-{round_no}", dispatch_id=f"proof-round-{round_no}-send-1",
    )  # fmt: skip


async def _round(registry, request, *, cancel_after: float | None = None) -> bool:
    queued = await registry.enqueue(request, OWNER, max_attempts=1, only_with_worker=True)
    if not isinstance(queued, Enqueued):
        print(f"  not queued: {queued}")
        return False
    operation_id = queued.operation.operation_id
    started, claimed_at, cancelled = time.monotonic(), None, False
    while time.monotonic() - started < ROUND_SECONDS:
        op = await registry.operation(operation_id)
        if op.state is OperationState.CLAIMED and claimed_at is None:
            claimed_at = time.monotonic()
            print(f"  claimed after {claimed_at - started:.1f}s")
        if cancel_after is not None and claimed_at and not cancelled:
            if time.monotonic() - claimed_at >= cancel_after:
                await registry.cancel(operation_id)
                cancelled = True
                print(f"  cancel asked after {time.monotonic() - claimed_at:.1f}s of play")
        if op.result is not None:
            result = op.result
            print(f"  {result.status.value} after {time.monotonic() - started:.1f}s "
                  f"{result.reason}")  # fmt: skip
            for record in result.records:
                print(f"    {record.assertion_id}: {record.outcome.value} ({record.context}) "
                      f"observed {record.observed}, expected {record.expected}")  # fmt: skip
            return True
        await asyncio.sleep(1.0)
    print(f"  no result within {ROUND_SECONDS:g}s")
    return False


def worker_settings(environ: Mapping[str, str]) -> dict[str, str]:
    """The worker's ``roblox-studio`` settings, as the worker reads them: each one it requires,
    and each of R5.33's four optional ones that is written (#3193). An optional setting left out
    is never defaulted, so a proof on a worker its owner hasn't declared dedicated refuses as
    the worker does."""
    return {
        **{name: environ.get(_PREFIX + name.upper(), "") for name in studio_worker.SETTINGS},
        **{
            name: environ[_PREFIX + name.upper()]
            for name in FRONT_SETTINGS
            if _PREFIX + name.upper() in environ
        },  # fmt: skip
    }


async def _main(repo: Path, scenario_file: Path) -> int:
    runner = studio_worker.create_runner(worker_settings(os.environ))
    registry = WorkerRegistry(MemoryWorkerRegistryStore())
    worker = Worker(
        InProcessWorkerApi(registry),
        runner,
        worker_id="studio-worker-proof",
        platform=f"{platform.system().lower()}-{platform.machine().lower()}",
    )
    serving = asyncio.ensure_future(worker.serve())
    try:
        while not await registry.sessions():
            if serving.done():
                serving.result()  # what stopped the worker is the answer
            await asyncio.sleep(0.5)
        [(session, _)] = await registry.sessions()
        print(f"registered: {dict(session.tool_versions)}")
        done = True
        for round_no, label, cancel_after in (
            (1, "a scenario played", None),
            (2, "a scenario cancelled while it plays", CANCEL_AFTER_SECONDS),
            (3, "a scenario played on the restarted Studio", None),
        ):
            print(f"round {round_no}: {label}")
            done = await _round(
                registry, _request(repo, scenario_file, round_no), cancel_after=cancel_after
            ) and done  # fmt: skip
        return 0 if done else 1
    finally:
        serving.cancel()
        await asyncio.wait({serving})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo", type=Path, help="the product repository whose src/ is played")
    parser.add_argument("scenario", type=Path, help="a squadops.scenario/1 declaration (JSON)")
    args = parser.parse_args()
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    return asyncio.run(_main(args.repo.expanduser(), args.scenario))


if __name__ == "__main__":
    sys.exit(main())
