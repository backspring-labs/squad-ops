"""Capability contracts and verification modes (SIP-0116 §6.1, §6.2).

A capability contract defines a kind of work in engine-neutral terms, once, for every
platform: the existing task type it runs as, the evidence it must produce, and the
verification modes it may run in. A skillset specializes contracts for one platform
(``squadops.capabilities.skillsets``); a contract never names a platform, and a platform
never adds a task type.

The three task types a planner may already offer are their own contracts and need no
declaration. A domain declares a contract over a task type where its evidence differs. None
is declared yet: the game contracts are the first, and they arrive with their own proposal.

These are the SIP-0116 contracts. The ``TaskContract`` manifests under ``manifests/contracts``
are SIP-0.8.6's, a different record with a different loader.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from squadops.tasks.base_set import base_plannable_task_types
from squadops.tasks.task_types import TaskType


class VerificationMode(StrEnum):
    """What a verification exercises (§6.2). A closed list, extended only by a SIP. A contract
    and a skillset each declare the modes they support, and one mode never implies another."""

    BUILD = "build"  # compiling or building the product
    HEADLESS = "headless"  # tests that run outside the engine's runtime (Q67)
    EDITOR = "editor"  # the product inside its editor, without running it
    PLAY = "play"  # the product running
    MULTIPLAYER = "multiplayer"  # several clients or players at once
    CAPTURE = "capture"  # screenshots or recordings, as evidence


@dataclass(frozen=True)
class CapabilityContract:
    """One engine-neutral kind of work (§6.1)."""

    id: str
    task_type: TaskType
    #: What it must produce, in SIP-0096's vocabulary.
    evidence: str
    #: The verification modes it may run in. Empty for work that isn't verification.
    modes: tuple[VerificationMode, ...] = ()


#: The declared contracts, by id. Empty until the first domain declares one.
CAPABILITY_CONTRACTS: Mapping[str, CapabilityContract] = MappingProxyType({})


def capability_contract(
    contract_id: str, declared: Mapping[str, CapabilityContract] | None = None
) -> CapabilityContract | None:
    """The contract ``contract_id`` names, or ``None``. A base-set plannable task type is its
    own contract (§6.1), so its value resolves without a declaration."""
    contracts = CAPABILITY_CONTRACTS if declared is None else declared
    found = contracts.get(contract_id)
    if found is not None:
        return found
    for task_type in base_plannable_task_types():
        if task_type.value == contract_id:
            return CapabilityContract(id=contract_id, task_type=task_type, evidence="")
    return None


def contract_errors(declared: Mapping[str, CapabilityContract]) -> list[str]:
    """Everything wrong with a set of declared contracts, each named by its id."""
    task_type_values = {t.value for t in TaskType}
    errors: list[str] = []
    for key, contract in declared.items():
        if key != contract.id:
            errors.append(f"{key}: declared under a key that isn't its id ({contract.id})")
        if contract.id in task_type_values:
            errors.append(
                f"{contract.id}: a contract's id can't be a task type's; a plannable task "
                f"type is already its own contract"
            )
        if len(set(contract.modes)) != len(contract.modes):
            errors.append(f"{contract.id}: a verification mode is listed more than once")
        if not contract.evidence.strip():
            errors.append(f"{contract.id}: a contract says what evidence it must produce")
    return errors
