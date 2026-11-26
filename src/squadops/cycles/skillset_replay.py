"""What a task would be handed if its cycle required a skillset, for the replay that tests a skill
before any development profile requires it (SIP-0116 §7, §17p).

A skill is replay-tested on the models that will run it before it is used (Q47), so the test
can't wait for a profile's ``requires``. This builds the task's equipment the way a cycle does,
from the same catalog through the same supply: an assignment of the skillset to the agent, the
copy a cycle keeps of it (``kept_document``), and the skills that copy loads for the task's type
(``skills_for``). Nothing here selects a skill by another rule than a cycle's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from squadops.capabilities.capability_contracts import (
    CapabilityContractDeclaration,
    capability_contract,
)
from squadops.capabilities.skillsets import Skillset
from squadops.cycles.skillset_content import (
    kept_document,
    scenario_vocabulary_for,
    skills_for,
    skills_input,
)
from squadops.cycles.skillset_coverage import Assignment


@dataclass(frozen=True)
class TaskEquipment:
    """A task's equipment under a skillset: its skills as a handler is handed them, and the
    scenario vocabulary its cycle would keep, as a document, where one was asked for."""

    skills: list[dict[str, Any]]
    scenario_vocabulary: dict[str, Any] | None = None

    def digests(self) -> dict[str, str]:
        """Each handed skill's digest, by ``skillset/skill``: what a record names the test by."""
        return {f"{s['skillset']}/{s['skill']}": s["digest"] for s in self.skills}


def task_equipment(
    catalog: Mapping[str, Skillset],
    *,
    skillset: str,
    role: str,
    agent_id: str,
    task_type: str,
    vocabulary_skillset: str = "",
    contracts: Mapping[str, CapabilityContractDeclaration] | None = None,
) -> TaskEquipment:
    """The equipment ``agent_id``, serving ``role``, is handed for a ``task_type`` task when its
    cycle requires every capability of ``skillset``.

    ``vocabulary_skillset`` names the skillset whose scenario vocabulary the cycle keeps (the
    supplier of the scenario operation, which may be another role's), or ``""`` for none.

    Raises:
        ValueError: The catalog holds no such skillset, it isn't for ``role``, it loads no skill
            for ``task_type``, or ``vocabulary_skillset`` holds no vocabulary or more than one.
    """
    held = _held(catalog, skillset)
    if role not in held.roles:
        raise ValueError(f"skillset {skillset} is for {', '.join(held.roles)}, not {role}")
    offered = _offered(held, agent_id, contracts)
    document = kept_document(
        [Assignment(role, agent_id, held.id, held.version, held.digest)], catalog
    )
    skills = skills_input(
        skills_for(document, {"offered": offered}, task_type=task_type, agent_id=agent_id)
    )
    if not skills:
        raise ValueError(f"skillset {skillset} loads no skill for a {task_type} task")
    vocabulary = (
        _vocabulary(catalog, vocabulary_skillset, contracts) if vocabulary_skillset else None
    )
    return TaskEquipment(skills=skills, scenario_vocabulary=vocabulary)


def _held(catalog: Mapping[str, Skillset], skillset: str) -> Skillset:
    held = catalog.get(skillset)
    if held is None:
        raise ValueError(
            f"the catalog holds no skillset {skillset}: it holds {', '.join(sorted(catalog))}"
        )
    return held


def _offered(
    held: Skillset,
    agent_id: str,
    contracts: Mapping[str, CapabilityContractDeclaration] | None,
) -> list[dict[str, Any]]:
    """The rows a cycle's record would hold for an agent supplying every capability of ``held``
    (``skillset_record``'s ``offered``). A capability naming a contract nobody declares is
    refused: the skillset's load refuses it too, so a catalog holding one was built another way."""
    rows = []
    for capability in held.capabilities:
        contract = capability_contract(capability.contract, contracts)
        if contract is None:
            raise ValueError(
                f"skillset {held.id} specializes {capability.contract}, which no contract declares"
            )
        rows.append(
            {
                "agent_id": agent_id,
                "contract": capability.contract,
                "task_type": contract.task_type.value,
                "skillset": held.id,
            }
        )
    return rows


def _vocabulary(
    catalog: Mapping[str, Skillset],
    skillset: str,
    contracts: Mapping[str, CapabilityContractDeclaration] | None,
) -> dict[str, Any]:
    supplier = _held(catalog, skillset)
    document = kept_document(
        [Assignment(supplier.roles[0], "", supplier.id, supplier.version, supplier.digest)],
        catalog,
    )
    record = {"offered": _offered(supplier, "", contracts)}
    found = [
        vocabulary
        for capability in supplier.capabilities
        if (vocabulary := scenario_vocabulary_for(document, record, capability.contract))
        is not None
    ]
    if len(found) != 1:
        raise ValueError(
            f"skillset {skillset} holds {len(found)} scenario vocabularies, and a cycle keeps one"
        )
    return found[0].to_document()
