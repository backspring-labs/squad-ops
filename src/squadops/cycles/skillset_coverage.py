"""Coverage: does the squad's routed agent carry what the work requires? (SIP-0116 §5.3, §9)

The work declares the skillsets it requires on its development profile, and each agent in a
squad profile declares the skillsets it carries. This module compares the two for one cycle,
on the agent each responsibility routes to, and says what a planner may be offered as a result.

It is a function of declared configuration alone (§5.3): the profile's requirements, the squad
profile, the skillset catalog and the capability contracts. The objective, the PRD and the plan
never select a requirement or a supplier.

Two kinds of finding, kept apart because they have different owners (§9):

- **coverage**: the routed agent lacks a required skillset, or carries an incompatible version.
  The operator selects another squad.
- **declaration**: something written is wrong whatever squad is selected: an unknown skillset,
  a skillset the agent's roles don't allow, two required skillsets adding to one capability, or
  a requirement its skillset can't meet. The profile's or the squad's author fixes it.

Authorization and availability are the tools' outcomes, and arrive with them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from squadops.capabilities.capability_contracts import (
    CapabilityContractDeclaration,
    capability_contract,
)
from squadops.capabilities.skillsets import Skillset
from squadops.cycles.agent_config import UnservedRoleError, resolve_agent_config
from squadops.cycles.models import AgentProfileEntry, SquadProfile
from squadops.stacks.development_profiles import (
    effective_development_profile,
    get_development_profile,
)
from squadops.stacks.requirements import (
    PlatformTarget,
    ResponsibilityRequirement,
    SkillsetRequirement,
    requirement_errors,
    version_satisfies,
)
from squadops.tasks.task_types import TaskType

COVERAGE = "coverage"
DECLARATION = "declaration"
#: SIP-0116 §9, phase 4: a required tool outside the authority governing its operation.
AUTHORIZATION = "authorization"
#: SIP-0116 §9, phase 4: a required tool no provider can run now.
AVAILABILITY = "availability"


@dataclass(frozen=True)
class CoverageFinding:
    kind: str
    message: str


@dataclass(frozen=True)
class Assignment:
    """One requirement, met: the agent it routed to and the skillset that agent supplied."""

    role: str
    agent_id: str
    skillset: str
    version: int
    digest: str


@dataclass(frozen=True)
class OfferedContract:
    """A contract, in a mode, that a requirement names and an assigned skillset supplies."""

    contract: str
    mode: str
    task_type: TaskType
    role: str
    agent_id: str
    skillset: str


@dataclass(frozen=True)
class Coverage:
    assignments: tuple[Assignment, ...] = ()
    offered: tuple[OfferedContract, ...] = ()
    findings: tuple[CoverageFinding, ...] = ()

    @property
    def covered(self) -> bool:
        return not self.findings


def routed_agent(profile: SquadProfile, role: str) -> AgentProfileEntry | None:
    """The agent a responsibility routes to (§5.3), or ``None`` when no agent serves it.

    Asked of ``resolve_agent_config``, the rule dispatch itself uses, so the agent coverage
    checks is the agent the step is sent to. A second copy of "the first enabled agent serving
    the role" here could drift from it, and coverage would then vouch for the wrong agent."""
    try:
        agent_id = resolve_agent_config(role, profile).agent_id
    except UnservedRoleError:
        return None
    return next(a for a in profile.agents if a.agent_id == agent_id and a.enabled)


def resolve_coverage(
    profile: SquadProfile,
    platform: PlatformTarget | None,
    requires: tuple[ResponsibilityRequirement, ...],
    catalog: Mapping[str, Skillset],
    contracts: Mapping[str, CapabilityContractDeclaration] | None = None,
) -> Coverage:
    """Compare what the work requires with what the routed agents carry. Every finding is
    reported, so a refusal names everything the operator or author has to change."""
    assignments: list[Assignment] = []
    offered: list[OfferedContract] = []
    findings: list[CoverageFinding] = []
    missing: list[str] = []

    for entry in requires:
        agent = routed_agent(profile, entry.role)
        for alternative in entry.any_of:
            findings.extend(
                CoverageFinding(DECLARATION, message)
                for message in _requirement_defects(alternative, platform, catalog, contracts)
            )
        supplied = _first_supplied(entry, agent, catalog)
        if agent is None or supplied is None:
            missing.append(_missing(entry, agent, catalog))
            continue
        requirement, skillset = supplied
        if entry.role not in skillset.roles:
            findings.append(
                CoverageFinding(
                    DECLARATION,
                    f"Agent `{agent.agent_id}` declares skillset `{skillset.id}` for `{entry.role}`, "
                    f"and that skillset is for {_listed(skillset.roles)}.",
                )
            )
            continue
        assignments.append(
            Assignment(entry.role, agent.agent_id, skillset.id, skillset.version, skillset.digest)
        )
        for need in requirement.needs:
            contract = capability_contract(need.contract, contracts)
            if contract is not None:
                offered.append(
                    OfferedContract(
                        need.contract,
                        need.mode,
                        contract.task_type,
                        entry.role,
                        agent.agent_id,
                        skillset.id,
                    )
                )

    if missing:
        findings.insert(
            0,
            CoverageFinding(
                COVERAGE,
                f"Squad skillset requirements not met. Selected squad: `{profile.profile_id}`. "
                f"Missing: {', '.join(missing)}. Select or configure a squad with an eligible "
                f"agent carrying each skillset.",
            ),
        )
    findings.extend(_overlaps(offered))
    return Coverage(tuple(assignments), tuple(offered), tuple(findings))


def cycle_coverage(
    profile: SquadProfile,
    resolved_config: Mapping[str, Any] | None,
    catalog: Mapping[str, Skillset],
    contracts: Mapping[str, CapabilityContractDeclaration] | None = None,
) -> Coverage:
    """Coverage for a cycle of ``resolved_config`` on ``profile``: its development profile's
    requirements, compared with the squad. Raises ``ValueError`` for a profile name the
    registry doesn't hold: cycle preflight refuses that name first
    (``development_profile_known_decision``), so reaching here with one is a caller's defect,
    and answering "requires nothing" would read as covered."""
    development = get_development_profile(effective_development_profile(resolved_config))
    malformed = requirement_errors(development.platform, development.requires)
    if malformed:
        # The registry's profiles are held to this by a test. A profile reaching a cycle
        # with a malformed requirement is refused here too, never half-checked.
        return Coverage(
            findings=tuple(
                CoverageFinding(DECLARATION, f"Development profile `{development.name}`: {e}.")
                for e in malformed
            )
        )
    return resolve_coverage(profile, development.platform, development.requires, catalog, contracts)


def _first_supplied(
    entry: ResponsibilityRequirement,
    agent: AgentProfileEntry | None,
    catalog: Mapping[str, Skillset],
) -> tuple[SkillsetRequirement, Skillset] | None:
    """The first declared alternative the routed agent carries at a compatible version."""
    if agent is None:
        return None
    for alternative in entry.any_of:
        skillset = catalog.get(alternative.skillset)
        if (
            skillset is not None
            and alternative.skillset in agent.skillsets
            and version_satisfies(alternative.version, skillset.version)
        ):
            return alternative, skillset
    return None


def _missing(
    entry: ResponsibilityRequirement,
    agent: AgentProfileEntry | None,
    catalog: Mapping[str, Skillset],
) -> str:
    """One unmet requirement, as §9 words it: the skillset, the responsibility and the agent."""
    wanted = " or ".join(f"`{a.skillset}`" for a in entry.any_of)
    if agent is None:
        return f"{wanted} for `{entry.role}` (no enabled agent serves that role)"
    held = [
        (a, catalog[a.skillset])
        for a in entry.any_of
        if a.skillset in agent.skillsets and a.skillset in catalog
    ]
    if held:
        alternative, skillset = held[0]
        return (
            f"`{skillset.id}` at version {alternative.version} for `{entry.role}` "
            f"(agent `{agent.agent_id}` carries version {skillset.version})"
        )
    return f"{wanted} for `{entry.role}` (agent `{agent.agent_id}`)"


def _requirement_defects(
    requirement: SkillsetRequirement,
    platform: PlatformTarget | None,
    catalog: Mapping[str, Skillset],
    contracts: Mapping[str, CapabilityContractDeclaration] | None,
) -> list[str]:
    """Why a requirement can't be met by the skillset it names, whatever squad is selected."""
    skillset = catalog.get(requirement.skillset)
    if skillset is None:
        return [f"Required skillset `{requirement.skillset}` is unknown to this deployment."]
    defects: list[str] = []
    if platform is not None and (
        skillset.platform_id != platform.id or platform.variant not in skillset.platform_variants
    ):
        defects.append(
            f"Required skillset `{skillset.id}` applies to `{skillset.platform_id}` "
            f"({_listed(skillset.platform_variants)}), and the profile's platform is "
            f"`{platform.id}` (`{platform.variant}`)."
        )
    for need in requirement.needs:
        specialized = skillset.capability_for(need.contract)
        if capability_contract(need.contract, contracts) is None or specialized is None:
            defects.append(
                f"Required skillset `{skillset.id}` doesn't specialize the contract "
                f"`{need.contract}`."
            )
        elif need.mode and need.mode not in specialized.modes:
            defects.append(
                f"Required skillset `{skillset.id}` doesn't support `{need.contract}` in "
                f"`{need.mode}` mode."
            )
    return defects


def _overlaps(offered: list[OfferedContract]) -> list[CoverageFinding]:
    """Q62: one supplier per capability. Two required skillsets that both add to one role's
    work on a task type are refused by name, and the profile's author resolves it."""
    suppliers: dict[tuple[str, TaskType], set[str]] = {}
    for item in offered:
        suppliers.setdefault((item.role, item.task_type), set()).add(item.skillset)
    return [
        CoverageFinding(
            DECLARATION,
            f"Required skillsets {_listed(sorted(names))} both add to `{task_type.value}` for "
            f"`{role}`. One skillset supplies a capability; the profile's author resolves it.",
        )
        for (role, task_type), names in sorted(suppliers.items(), key=lambda kv: str(kv[0]))
        if len(names) > 1
    ]


def _listed(names: Iterable[str]) -> str:
    return ", ".join(f"`{n}`" for n in names)
