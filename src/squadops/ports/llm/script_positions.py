"""Where a scripted cycle's answer positions are kept, across agent restarts (#3005).

The scripted provider keys each answer by ``(task_type, occurrence, call)`` (#2495,
:mod:`squadops.llm.script`):
- the occurrence is the task's ordinal among the tasks of its type that the cycle has asked
  about, in the order their first calls came;
- the call is the task's own call count.

Both are counts over the cycle's history. While they lived in the agent's process, an agent that
restarted mid-cycle counted the cycle's tasks from the first again. The next task of a type that
had already run was then answered with an earlier task's recorded answer instead of failing.
So the counts are kept outside the process, per cycle, and a restarted agent goes on from where
the cycle was.

The script a cycle named is kept the same way. A step whose envelope carries no resolved config
(a pulse-check repair) is answered from the script an earlier task of its cycle named. After a
restart that earlier task must still be known.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ScriptPositionsPort(ABC):
    """One scripted cycle's answer positions, kept for the cycle's life."""

    @abstractmethod
    async def next_call(self, cycle_id: str, task_type: str, task_id: str) -> tuple[int, int]:
        """Count one call of ``task_id`` and return its ``(occurrence, call)``.

        The occurrence is ``task_id``'s 1-based place among the distinct tasks of
        ``task_type`` this cycle has called for, in the order of their first calls. The call is
        this task's own count, this one included. Both read the same whichever process asks.
        """

    @abstractmethod
    async def bind_script(self, cycle_id: str, named: str | None) -> str | None:
        """The script ``cycle_id`` is bound to.

        With ``named``, the cycle is bound to it unless it is already bound, and the binding is
        returned: a caller compares it with ``named``, since a cycle has one script. With
        ``None``, the binding is returned, or ``None`` when the cycle has none yet.
        """
