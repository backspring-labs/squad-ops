"""A dispatch is handed the skills its task loads, from its cycle's kept copy (SIP-0116 §7, §7.1).

The runtime hands them, on the envelope, each time a task goes out: its first dispatch, a
re-dispatch, and a repair. An agent has no way to the vault, and reads no skill from its own
tree, so what a task was handed is what its cycle kept when it was created.

Which skills (§7, §7.1):

- **a task** loads the skills of its capability, from the skillset its agent was assigned to
  supply (``skillset_content.skills_for``);
- **a repair** loads the skills of the step whose output it revises
  (``task_plan.revised_task_type``), from the skillset the repair's own agent supplies. A
  repair of the application after a failed suite or a failed operation is given the
  developer's guidance, never the suite's or the operation's;
- **a step that runs an operation** is handed none. Its handler calls no model, so a skill
  has nowhere to be read.

Handing replaces what an earlier dispatch of the same envelope was handed.

Only an authoring seam's handler has a place to show a skill (``authoring_seam_of``, the
seams memory's sections go to). A record that offers skills to any other step raises at its
dispatch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.cycles.skillset_content import (
    SKILLS_INPUT,
    LoadedSkill,
    SkillsetContentError,
    kept_document_of,
    skills_for,
    skills_input,
)
from squadops.cycles.task_plan import revised_task_type
from squadops.tasks.task_types import runs_an_operation

if TYPE_CHECKING:
    from collections.abc import Mapping

    from squadops.cycles.models import Cycle
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
    from squadops.tasks.models import TaskEnvelope


def skills_for_dispatch(
    document: Mapping[str, Any], record: Mapping[str, Any], envelope: TaskEnvelope
) -> tuple[LoadedSkill, ...]:
    """The skills ``envelope``'s dispatch loads, from the cycle's record and its kept copy."""
    task_type = str(envelope.task_type)
    if runs_an_operation(task_type):
        return ()
    revised = revised_task_type(task_type)
    if revised is not None:
        # §7.1: by lineage. A repair names no contract of its own.
        return skills_for(document, record, task_type=revised, agent_id=envelope.agent_id)
    operation = envelope.inputs.get("operation")
    contract = operation["contract"] if isinstance(operation, dict) else ""
    return skills_for(
        document, record, task_type=task_type, agent_id=envelope.agent_id, contract=contract
    )


class SkillSupply:
    """Hands each dispatch of a run its skills. One per executor, over the vault the cycles'
    copies are kept in."""

    def __init__(self, vault: ArtifactVaultPort | None) -> None:
        self._vault = vault
        #: A cycle's kept copy, once read and checked. It is written once, at creation.
        self._kept: dict[str, dict[str, Any] | None] = {}

    async def hand(self, cycle: Cycle, *envelopes: TaskEnvelope | None) -> None:
        """Hand the dispatch its skills on each of ``envelopes``: the task's own envelope
        first, and the copies the executor dispatches. The first names the task and its agent.

        A cycle created before records existed has none, and loads nothing. A record that
        names skills with no copy to load them from raises (``kept_document_of``).
        """
        held = [e for e in envelopes if e is not None]
        if not held:
            return
        record = cycle.skillset_record
        skills: tuple[LoadedSkill, ...] = ()
        if record is not None:
            document = await self._document(cycle, record)
            if document is not None:
                skills = skills_for_dispatch(document, record, held[0])
        if skills and authoring_seam_of(str(held[0].task_type)) is None:
            # No handler but an authoring seam's has a place for a skill. Handing these would
            # send them nowhere, and the task would read as one that had them.
            raise SkillsetContentError(
                f"cycle {cycle.cycle_id}'s record offers {held[0].task_type} "
                f"{len(skills)} skills, and that step's handler shows a task none"
            )
        for envelope in held:
            if skills:
                envelope.inputs[SKILLS_INPUT] = skills_input(skills)
            else:
                envelope.inputs.pop(SKILLS_INPUT, None)

    async def _document(self, cycle: Cycle, record: Mapping[str, Any]) -> dict[str, Any] | None:
        if cycle.cycle_id not in self._kept:
            self._kept[cycle.cycle_id] = await kept_document_of(
                self._vault, cycle_id=cycle.cycle_id, record=record
            )
        return self._kept[cycle.cycle_id]
