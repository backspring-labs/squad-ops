"""Capability contracts and verification modes (SIP-0116 §6.1, §6.2).

A capability contract defines a kind of work in engine-neutral terms, once, for every
platform: the existing task type it runs as, the evidence it must produce, and the
verification modes it may run in. A skillset specializes contracts for one platform
(``squadops.capabilities.skillsets``); a contract never names a platform, and a platform
never adds a task type.

The three task types a planner may already offer are their own contracts and need no
declaration. A domain declares a contract over a task type where its evidence differs. The
game contracts are the first (SIP-0118 R4.2): four, defined once, for every engine.

These are the SIP-0116 contracts. The ``TaskContract`` manifests under ``manifests/contracts``
are SIP-0.8.6's, a different record with a different loader, and the name they had before
#922 stays retired: the class here is a contract's *declaration*.
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
class CapabilityContractDeclaration:
    """One engine-neutral kind of work (§6.1)."""

    id: str
    task_type: TaskType
    #: What it must produce, in SIP-0096's vocabulary.
    evidence: str
    #: The verification modes it may run in. Empty for work that isn't verification.
    modes: tuple[VerificationMode, ...] = ()


def _declared(
    *contracts: CapabilityContractDeclaration,
) -> Mapping[str, CapabilityContractDeclaration]:
    return MappingProxyType({contract.id: contract for contract in contracts})


#: The declared contracts, by id.
#:
#: The four ``game.*`` contracts are SIP-0118 R4.2's: what the work is and the evidence it must
#: produce, for any engine. A platform's skillsets specialize them (Roblox is the first), and a
#: platform adds no task type. Declaring a contract offers it to no one: a cycle is offered one
#: only where its development profile requires it and its routed agent supplies it.
CAPABILITY_CONTRACTS: Mapping[str, CapabilityContractDeclaration] = _declared(
    CapabilityContractDeclaration(
        id="game.increment_design",
        task_type=TaskType.STRATEGY_PROPOSE_INCREMENT,
        evidence=(
            "the change request: a player-facing criterion and a play scenario for each, in the "
            "form its verification contract reads, frozen by digest before development"
        ),
    ),
    CapabilityContractDeclaration(
        id="game.gameplay_implementation",
        task_type=TaskType.DEVELOPMENT_DEVELOP,
        evidence=(
            "source files inside the change request's footprint, judged by the cycle's typed "
            "checks as any development output is"
        ),
    ),
    CapabilityContractDeclaration(
        id="game.unit_tests",
        task_type=TaskType.QA_TEST,
        evidence=(
            "one executed-passed, executed-failed or not-executed result per test, read per "
            "test id from the runner's own output; a run that collected nothing is not executed"
        ),
        modes=(VerificationMode.HEADLESS, VerificationMode.EDITOR, VerificationMode.PLAY),
    ),
    CapabilityContractDeclaration(
        id="game.scenario_verification",
        task_type=TaskType.QA_RUN_REMOTE_OPERATION,
        evidence=(
            "one record per declared assertion of a frozen scenario: passed and failed are "
            "executed; missing, setup_failed, unsupported_input and wrong_context are not "
            "executed. Each run names the source revision and the scenario's digest"
        ),
        modes=(VerificationMode.PLAY, VerificationMode.MULTIPLAYER),
    ),
)


def capability_contract(
    contract_id: str, declared: Mapping[str, CapabilityContractDeclaration] | None = None
) -> CapabilityContractDeclaration | None:
    """The contract ``contract_id`` names, or ``None``. A base-set plannable task type is its
    own contract (§6.1), so its value resolves without a declaration."""
    contracts = CAPABILITY_CONTRACTS if declared is None else declared
    found = contracts.get(contract_id)
    if found is not None:
        return found
    for task_type in base_plannable_task_types():
        if task_type.value == contract_id:
            return CapabilityContractDeclaration(id=contract_id, task_type=task_type, evidence="")
    return None


def contract_errors(declared: Mapping[str, CapabilityContractDeclaration]) -> list[str]:
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
