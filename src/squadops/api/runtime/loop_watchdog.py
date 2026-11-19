"""What holds the runtime's event loop, and how long its requests take (#3218).

The 2.8 demonstration's worker had 17 requests go unanswered, about 13–16 s after a gate entry or a
Campaign transition, each answered at the next poll. Nothing the runtime logged said why. Two
causes fit and read differently:
- **the loop is held:** a synchronous call in a coroutine stops every request at once;
- **the pool is spent:** the loop runs, but requests wait for one of its ten connections.

So the runtime now names both:
- ``LoopWatchdog``: an asyncio task stamps a heartbeat, and a daemon thread reads it. When the
  heartbeat is older than ``STALL_THRESHOLD_S`` it logs the loop thread's stack, which is where the
  loop is held, again every ``RESAMPLE_S`` while it stays held, and the stall's length when it
  clears;
- ``slow_request`` (``api/middleware/timing.py``): a request slower than a second is logged with
  its path and time;
- ``slow_pool_acquire`` (``adapters/persistence/transient.py``): a connection that took longer than
  ``SLOW_ACQUIRE_S`` to come from the pool.

A stalled loop with no slow acquire is the loop's; slow acquires with no stall are the pool's.
These are instruments, not tunables: the thresholds sit below the 2.8.1 plan's 2 s bar.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import traceback
from collections.abc import Callable

logger = logging.getLogger(__name__)

#: A heartbeat older than this is a held loop.
STALL_THRESHOLD_S = 1.0
#: How often the heartbeat is stamped and read.
HEARTBEAT_S = 0.1
#: While the loop stays held, its stack is read again this often, so a stall made of several calls
#: names each.
RESAMPLE_S = 5.0


class LoopWatchdog:
    """Logs the event loop thread's stack while the loop is held."""

    def __init__(
        self,
        *,
        threshold_s: float = STALL_THRESHOLD_S,
        heartbeat_s: float = HEARTBEAT_S,
        resample_s: float = RESAMPLE_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold_s = threshold_s
        self._heartbeat_s = heartbeat_s
        self._resample_s = resample_s
        self._clock = clock
        self._beat = clock()
        self._loop_thread_id: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start from inside the running loop: the heartbeat task and the reading thread."""
        self._loop_thread_id = threading.get_ident()
        self._beat = self._clock()
        self._task = asyncio.get_running_loop().create_task(self._heartbeat())
        self._thread = threading.Thread(target=self._watch, name="loop-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
        if self._thread is not None:
            self._thread.join(timeout=2 * self._heartbeat_s + 1)

    async def _heartbeat(self) -> None:
        while True:
            self._beat = self._clock()
            await asyncio.sleep(self._heartbeat_s)

    def _stack(self) -> str:
        frame = sys._current_frames().get(self._loop_thread_id or -1)
        return "".join(traceback.format_stack(frame)) if frame is not None else "<no frame>"

    def _watch(self) -> None:
        stalled_from: float | None = None
        sampled_at = 0.0
        while not self._stop.wait(self._heartbeat_s):
            now = self._clock()
            lag = now - self._beat
            if lag > self._threshold_s:
                if stalled_from is None or now - sampled_at >= self._resample_s:
                    logger.warning(
                        "event_loop_stalled lag_s=%.2f loop thread at:\n%s", lag, self._stack()
                    )
                    sampled_at = now
                if stalled_from is None:
                    stalled_from = self._beat
            elif stalled_from is not None:
                logger.warning("event_loop_stall_ended held_s=%.2f", self._beat - stalled_from)
                stalled_from = None
