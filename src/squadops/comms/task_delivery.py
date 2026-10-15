"""Which send of a dispatched task a delivery is (#2333).

The agent's delivery record (#1977) dedupes a completed task and bounds a dying one. It has to
tell two things apart that share a task id:

- **a redelivery:** the broker delivers one send again, because its ack was lost or the agent
  died holding it. A completed one is a duplicate, and each one counts against the bound;
- **a re-dispatch:** the runtime sends the task again on purpose, for a fresh execution: a retry
  after a retryable failure, or the original task's re-run after a correction round's patch
  retest fails. It is new work, and runs.

A task id alone can't (#1929 found the same for a restarted runtime's copy). Keyed by the task id,
the record took every re-dispatch for a redelivery of the first send: acked, never run, never
answered, and the runtime waited out its per-task wait three times on one roll (#2333).

So the dispatcher stamps each send with its own id, and the record is keyed by the task id and
that id. A broker redelivery is the same message, so it has the same key.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: The envelope metadata key a send's own id travels under.
DISPATCH_ID_METADATA_KEY = "dispatch_id"


def delivery_key(task_id: str, metadata: Mapping[str, Any] | None) -> str:
    """The delivery record's key: the task id and the send it came in, or the task id alone for
    an envelope that carries no send id (one dispatched before #2333)."""
    dispatch = (metadata or {}).get(DISPATCH_ID_METADATA_KEY)
    return f"{task_id}@{dispatch}" if dispatch else task_id
