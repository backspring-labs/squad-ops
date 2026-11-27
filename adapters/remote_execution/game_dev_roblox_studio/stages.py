"""How long each stage of a play took (the 2.9 plan's item 13, #3250).

The certification window measures a matched set's claim-to-completion time before and after a
change meant to cut it by a fifth. Which stage to cut is read from here: each play's runner times
its own stages, and the result carries them as an evidence item, ``stages.json``.

**What is timed, by name.** The stages of the transaction, in the order they run:

- ``session_open_s``: the harness session to Studio's MCP opened, with its live tool list;
- ``proof_s``: the running Studio held to its proof (R2.4, R5.29);
- ``front_s``: R5.18's check, and R5.33's activation when it ran;
- ``identity_s``: the place found in the running Studio;
- ``place_state_s``: the place's non-script state read against its pin;
- ``sync_s``: the candidate's scripts written into the place;
- ``marks_s``: the synced scripts read for attributes and tags;
- ``baseline_before_s``: the place's state read before play;
- ``play_start_s``: play started;
- ``scenario_s``: the scenario's setup and steps, with each wait's own time in ``waits``;
- ``player_s``: the session's player read, for redaction;
- ``console_s``: the console read;
- ``stop_s``: play stopped;
- ``baseline_after_s``: the place's state read after play;
- ``read_back_s``: the place's scripts read back against what was synced;
- ``reset_s``: the reset, when the run began with one (R5.17's drift).

A stage that didn't run is absent. One that raised is timed to where it raised, and named in
``stopped_at``. **A stage's time is its sum over the play's attempts at the transaction:** R5.17
begins the transaction again once after a drifted place's reset, and ``transactions`` says how
many attempts there were, so a play begun again is never read as one slow attempt. Claim-to-completion and delivery are read from the runtime's records of the
operation, not here: the result is built before it is delivered.

Seconds are wall-clock (``time.monotonic``), rounded to the millisecond.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

STAGES_NAME = "stages.json"
SCHEMA = "squadops.play-stages/1"
STAGES = (
    "session_open_s",
    "proof_s",
    "front_s",
    "identity_s",
    "place_state_s",
    "sync_s",
    "marks_s",
    "baseline_before_s",
    "play_start_s",
    "scenario_s",
    "player_s",
    "console_s",
    "stop_s",
    "baseline_after_s",
    "read_back_s",
    "reset_s",
)


@dataclass
class PlayStages:
    """One play's stage times. ``stage`` times a block; ``wait`` records one wait's time."""

    clock: Callable[[], float] = time.monotonic
    seconds: dict[str, float] = field(default_factory=dict)
    waits: list[float] = field(default_factory=list)
    stopped_at: str | None = None
    #: How many attempts at the transaction the play made: 1, or 2 after a drift's reset.
    transactions: int = 0

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        if name not in STAGES:
            raise ValueError(f"{name!r} isn't one of the play's stages: {', '.join(STAGES)}")
        began = self.clock()
        try:
            yield
        except BaseException:
            self.stopped_at = name
            raise
        finally:
            self.seconds[name] = round(self.seconds.get(name, 0.0) + self.clock() - began, 3)

    def wait(self, seconds: float) -> None:
        self.waits.append(round(seconds, 3))

    def document(self) -> str:
        """The evidence item's text: each stage that ran, in the order they run."""
        return json.dumps(
            {
                "schema": SCHEMA,
                "transactions": self.transactions,
                "stages": {name: self.seconds[name] for name in STAGES if name in self.seconds},
                "waits": self.waits,
                "stopped_at": self.stopped_at,
            },
            indent=2,
        )
