"""Each unit's dispatch turn (#2545; ``squadops.memory.dispatch_turns``), and the one-process
deploy it depends on.

What bugs would these catch? Two holders of one unit's turn at once; one unit's turn holding off
another unit's dispatches; a turn kept by a holder that raised; turns kept for every unit ever
dispatched; a runtime API started as several processes, whose turns would order nothing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from squadops.memory.dispatch_turns import DispatchTurns
from squadops.memory.lessons import UnitKind

pytestmark = [pytest.mark.domain_memory]

ROOT = Path(__file__).resolve().parents[3]


async def test_one_units_turn_is_taken_in_order_and_another_units_isnt_held_by_it():
    turns, order = DispatchTurns(), []
    first_in, first_out = asyncio.Event(), asyncio.Event()

    async def hold(name: str, kind: UnitKind, unit: str, until: asyncio.Event | None = None):
        async with turns.held(kind, unit):
            order.append(f"{name} in")
            if until is not None:
                first_in.set()
                await until.wait()
            order.append(f"{name} out")

    first = asyncio.create_task(hold("first", UnitKind.CYCLE, "cyc_a", first_out))
    await first_in.wait()
    second = asyncio.create_task(hold("second", UnitKind.CYCLE, "cyc_a"))
    other = asyncio.create_task(hold("other", UnitKind.CAMPAIGN, "cyc_a"))
    await other
    first_out.set()
    await asyncio.gather(first, second)

    assert order == ["first in", "other in", "other out", "first out", "second in", "second out"]
    assert len(turns) == 0


async def test_a_holder_that_raises_gives_the_turn_back_and_nothing_is_kept():
    turns = DispatchTurns()

    with pytest.raises(RuntimeError, match="the write failed"):
        async with turns.held(UnitKind.CYCLE, "cyc_a"):
            raise RuntimeError("the write failed")
    async with turns.held("cycle", "cyc_a"):
        held = len(turns)

    assert (held, len(turns)) == (1, 0)


def test_the_runtime_api_runs_one_server_process():
    """The turns order dispatches against changes within one process. Bug caught: a worker count
    given to the runtime API, so one process writes a change while another composes a dispatch it
    changes, each holding its own turn."""
    dockerfile = (ROOT / "src/squadops/api/runtime/Dockerfile").read_text().splitlines()
    [command] = [line for line in dockerfile if line.startswith("CMD")]
    service = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["runtime-api"]

    assert "uvicorn" in command and "--workers" not in command
    assert "command" not in service and "entrypoint" not in service
    assert "WEB_CONCURRENCY" not in service.get("environment", {})
