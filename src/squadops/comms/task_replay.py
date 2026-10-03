"""A task a restarted runtime asks for again is answered, not run twice (#1929).

When the runtime API restarts with a task in flight, the agent holding the task keeps working on
it, and the startup re-attach (SIP-0109 §24am) dispatches it again under the same task id. The
agent takes one message at a time, so the copy is delivered after the original has finished and
replied. Without this, the agent ran the copy in full: duplicate model time per restart, and the
run's next task to that agent queued behind it, against its own wait.

A task id alone cannot tell the copy from a retry: ``dispatch_with_retry`` re-sends the identical
envelope for a fresh execution. What tells them apart is **which runtime process sent it**. Every
dispatch carries the dispatcher's boot id. An agent keeps, for its last few finished tasks, the
reply it sent and the boot it answered:

- the same task id from a **different** boot is a restarted runtime asking again. It is answered
  with the stored reply, and the stored boot becomes the asker's;
- the same task id from the **same** boot is that process's retry, and runs fresh.

So a replayed failure is still retried: the runtime that receives it decides, and its retry comes
from its own boot. An agent restarted since holds nothing, and runs the task, as before.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

#: The envelope metadata key a dispatch's boot id travels under.
DISPATCH_BOOT_METADATA_KEY = "dispatch_boot"

#: A reply can carry whole files, so only the last few finished tasks are kept. The task in
#: flight at a restart is always among the most recent.
FINISHED_TASKS_KEPT = 16


@dataclass
class _Finished:
    reply: str
    boot: str | None


class FinishedTasks:
    """An agent's last few finished tasks: the reply each sent and the boot it answered."""

    def __init__(self, keep: int = FINISHED_TASKS_KEPT) -> None:
        self._keep = keep
        self._finished: OrderedDict[str, _Finished] = OrderedDict()

    def record(self, task_id: str, reply: str, boot: str | None) -> None:
        self._finished[task_id] = _Finished(reply, boot)
        self._finished.move_to_end(task_id)
        while len(self._finished) > self._keep:
            self._finished.popitem(last=False)

    def replay_for(self, task_id: str, boot: str | None) -> str | None:
        """The stored reply when a different runtime boot asks for a task finished here, else
        ``None``. A replay records the asker's boot, so that boot's next send is a retry."""
        finished = self._finished.get(task_id)
        if finished is None or boot is None or finished.boot == boot:
            return None
        finished.boot = boot
        return finished.reply
