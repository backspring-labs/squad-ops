"""The runtime names what holds its event loop, and its slow requests (#3218).

The 2.8 worker's 17 unanswered requests came 13–16 s after gate entries, and nothing the runtime
logged said whether the loop was held or the pool was spent. These instruments say which.
"""

from __future__ import annotations

import asyncio
import logging
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from squadops.api.middleware import timing
from squadops.api.middleware.timing import SlowRequestMiddleware
from squadops.api.runtime.loop_watchdog import LoopWatchdog


def _blocks_the_loop(seconds: float) -> None:
    time.sleep(seconds)  # a synchronous call inside a coroutine: what #3218 suspects


async def _run_with_watchdog(body) -> None:
    dog = LoopWatchdog(threshold_s=0.2, heartbeat_s=0.02, resample_s=10.0)
    dog.start()
    try:
        await asyncio.sleep(0.05)
        await body()
        await asyncio.sleep(0.15)  # the reading thread sees the heartbeat again
    finally:
        dog.stop()


async def test_a_held_loop_is_logged_with_the_call_that_holds_it(caplog):
    """Bug caught: a watchdog that reports a stall without where the loop is, or reads its own
    thread's stack instead of the loop's, so the stall is seen and its cause isn't."""

    async def held():
        _blocks_the_loop(0.6)

    with caplog.at_level(logging.WARNING, logger="squadops.api.runtime.loop_watchdog"):
        await _run_with_watchdog(held)

    stalls = [r.getMessage() for r in caplog.records if "event_loop_stalled" in r.getMessage()]
    ended = [r.getMessage() for r in caplog.records if "event_loop_stall_ended" in r.getMessage()]
    assert len(stalls) == 1
    assert "_blocks_the_loop" in stalls[0]
    assert len(ended) == 1
    assert float(ended[0].split("held_s=")[1]) >= 0.4


async def test_a_loop_that_only_awaits_is_never_logged(caplog):
    """Bug caught: a watchdog that reads an idle await as a stall, so its lines say nothing."""

    async def idle():
        await asyncio.sleep(0.6)

    with caplog.at_level(logging.WARNING, logger="squadops.api.runtime.loop_watchdog"):
        await _run_with_watchdog(idle)

    assert not [r for r in caplog.records if "event_loop" in r.getMessage()]


@pytest.fixture
def slow_app(monkeypatch):
    monkeypatch.setattr(timing, "SLOW_REQUEST_S", 0.05)
    app = FastAPI()
    app.add_middleware(SlowRequestMiddleware)

    @app.get("/api/v1/workers/claim")
    async def slow() -> dict:
        await asyncio.sleep(0.15)
        return {}

    @app.get("/health/infra")
    async def fast() -> dict:
        return {}

    return TestClient(app)


def test_a_slow_request_is_logged_with_its_path_and_a_fast_one_is_not(slow_app, caplog):
    """Bug caught: a worker request that took longer than the bar leaving no line to read the
    2.8.1 threshold from, or every request logged so the slow ones are lost."""
    with caplog.at_level(logging.WARNING, logger="squadops.api.middleware.timing"):
        slow_app.get("/api/v1/workers/claim")
        slow_app.get("/health/infra")

    lines = [r.getMessage() for r in caplog.records if "slow_request" in r.getMessage()]
    assert len(lines) == 1
    assert "path=/api/v1/workers/claim status=200" in lines[0]
