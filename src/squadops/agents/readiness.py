"""An agent's readiness, as its container's health check reads it (#1691).

The health check used to import ``squadops.agents.entrypoint`` and print "Agent healthy". A
module import passes whether or not the agent process started, so ``compose up --wait`` returned
on the first "healthy" while every agent restart-looped on the #352 startup guard, and the deploy
script reported step 5 healthy either way.

Now the running agent marks itself: ``clear()`` as ``start()`` begins, so a restarted process
never inherits its predecessor's mark, and ``mark()`` on every heartbeat-loop iteration, which
begins only once the system has bootstrapped. The check passes only for a mark fresher than
three heartbeat intervals, so an agent that stopped looping goes unhealthy too.

    python -m squadops.agents.readiness      # exit 0 ready, 1 not — the Dockerfile HEALTHCHECK
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

#: Written inside the agent's own container; nothing outside it reads the file.
READY_FILE = Path("/tmp/squadops-agent-ready")

#: The heartbeat loop's period — a bare-env operational knob, like LOG_LEVEL (#333) — read here so
#: the loop and the check that ages its mark agree on it.
HEARTBEAT_INTERVAL_ENV = "HEARTBEAT_INTERVAL"
_DEFAULT_HEARTBEAT_SECONDS = 30
#: Heartbeats a mark may miss before the agent reads as not ready.
_MISSED_HEARTBEATS = 3


def heartbeat_interval_seconds() -> int:
    return int(os.getenv(HEARTBEAT_INTERVAL_ENV, str(_DEFAULT_HEARTBEAT_SECONDS)))


def clear() -> None:
    """Forget any mark a previous process in this container left."""
    READY_FILE.unlink(missing_ok=True)


def mark() -> None:
    """The agent is up and looping."""
    READY_FILE.touch()


def is_ready(now: float | None = None) -> bool:
    try:
        marked = READY_FILE.stat().st_mtime
    except OSError:
        return False
    age = (time.time() if now is None else now) - marked
    return age <= _MISSED_HEARTBEATS * heartbeat_interval_seconds()


def main() -> int:
    return 0 if is_ready() else 1


if __name__ == "__main__":
    sys.exit(main())
