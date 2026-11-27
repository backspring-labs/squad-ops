"""#3193: what a dedicated worker reads of the Mac before it brings Studio to the front.

The parsers are entered with ``ioreg``'s output as the MacBook gave it on 2026-11-26 (the lines
the readings depend on, with the rest of the tree trimmed).

What bugs would these catch?
- An idle counter read from the wrong unit, so a person who typed a second ago reads as gone
  for minutes, or the reverse.
- A reading that can't be made treated as "nobody is here", so the worker takes the front from
  a person because ``ioreg`` changed its output.
- A lock read as unlocked when the output names no lock.
"""

from __future__ import annotations

import pytest

from adapters.remote_execution.game_dev_roblox_studio.studio_app import (
    idle_seconds_in,
    locked_in,
)

#: ``ioreg -c IOHIDSystem``, trimmed, as the MacBook printed it.
IDLE = """+-o Root  <class IORegistryEntry, id 0x100000100, retain 22>
  +-o IOResources  <class IOResources, id 0x100000117, registered, matched, active>
    | | |   "HIDIdleTime" = 858018143166
    | | |   "HIDParameters" = {"HIDMouseAcceleration"=45056}
"""

#: ``ioreg -n Root -d1``, trimmed.
LOCK = """+-o Root  <class IORegistryEntry, id 0x100000100, retain 22>
    {
      "IOConsoleLocked" = {locked}
      "IOConsoleUsers" = ({{"kCGSSessionOnConsoleKey"=Yes}})
    }
"""


def test_the_idle_counter_is_read_in_seconds():
    assert idle_seconds_in(IDLE) == pytest.approx(858.018143166)


@pytest.mark.parametrize(
    "output",
    [
        "+-o Root  <class IORegistryEntry>\n",
        IDLE + '    | | |   "HIDIdleTime" = 5000000000\n',
    ],
    ids=["no-counter", "two-counters-that-disagree"],
)
def test_an_idle_counter_that_cant_be_read_is_an_error_never_absence(output):
    with pytest.raises(OSError, match="idle time is read from exactly one"):
        idle_seconds_in(output)


@pytest.mark.parametrize(("locked", "reads"), [("Yes", True), ("No", False)])
def test_the_lock_is_read_as_the_output_says(locked, reads):
    assert (
        locked_in(LOCK.replace("{locked}", locked).replace("{{", "{").replace("}}", "}")) is reads
    )


def test_a_lock_the_output_doesnt_name_is_an_error_never_unlocked():
    with pytest.raises(OSError, match="the lock is read from exactly one"):
        locked_in("+-o Root  <class IORegistryEntry>\n")
