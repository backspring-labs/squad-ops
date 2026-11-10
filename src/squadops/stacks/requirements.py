"""What a stack's work requires of the squad that does it (SIP-0116 §5.1).

A development profile names the platform its work targets and, for each responsibility (a
role), the skillsets the work needs, with the capability contracts and verification modes it
needs from each. These are plain declared values: this package holds a stack's settings as
data and imports neither the capability contracts nor the cycle models
(``tests/unit/architecture/test_package_import_direction.py``), so a contract and a mode are
named here by their ids, and whether a named skillset really specializes that contract in that
mode is cycle preflight's check (§9).

Empty means the work requires nothing beyond the base set, which is every profile until a
stack with requirements is switched on (§14).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: A version constraint is an exact version or a minimum (§5.1): ``"2"`` or ``">=2"``.
_CONSTRAINT = re.compile(r"^(>=)?([1-9][0-9]*)$")


@dataclass(frozen=True)
class PlatformTarget:
    """The engine or product a stack targets, and its form: ``roblox`` / ``studio-place``."""

    id: str
    variant: str


@dataclass(frozen=True)
class ContractNeed:
    """One capability contract the work needs from a skillset, and the verification mode it
    needs it in. ``mode`` is empty for a contract that isn't verification."""

    contract: str
    mode: str = ""


@dataclass(frozen=True)
class SkillsetRequirement:
    """A concrete skillset, an optional version constraint, and what the work needs from it."""

    skillset: str
    #: ``""`` accepts the version the deployment holds.
    version: str = ""
    needs: tuple[ContractNeed, ...] = ()


@dataclass(frozen=True)
class ResponsibilityRequirement:
    """What one responsibility requires: any one of ``any_of``. A plain requirement is a single
    alternative. An alternative is declared here and never inferred (§5.1)."""

    role: str
    any_of: tuple[SkillsetRequirement, ...]


def parse_version_constraint(constraint: str) -> tuple[bool, int] | None:
    """``(is_minimum, version)`` for a well-formed constraint, or ``None``. The empty
    constraint is the caller's to read as "any"."""
    match = _CONSTRAINT.match(constraint)
    return (bool(match.group(1)), int(match.group(2))) if match else None


def version_satisfies(constraint: str, version: int) -> bool:
    """Whether a skillset at ``version`` meets ``constraint``. Decided by these declared values
    alone (§5.1). A malformed constraint is met by nothing."""
    if not constraint:
        return True
    parsed = parse_version_constraint(constraint)
    if parsed is None:
        return False
    is_minimum, wanted = parsed
    return version >= wanted if is_minimum else version == wanted


def requirement_errors(
    platform: PlatformTarget | None, requires: tuple[ResponsibilityRequirement, ...]
) -> list[str]:
    """Everything wrong with a profile's ``platform`` and ``requires`` as written, each named
    by its responsibility and skillset. Shape only: ids present, constraints well formed, one
    entry per responsibility, and a platform wherever anything is required, since a skillset
    applies to a platform and a requirement with none can't be checked against it."""
    errors: list[str] = []
    if platform is not None and not (platform.id.strip() and platform.variant.strip()):
        errors.append("platform: both id and variant are required")
    if requires and platform is None:
        errors.append("requires: a profile that requires skillsets declares its platform")
    seen_roles: set[str] = set()
    for entry in requires:
        where = f"requires[{entry.role or '?'}]"
        if not entry.role.strip():
            errors.append(f"{where}: the responsibility's role is required")
        elif entry.role in seen_roles:
            errors.append(f"{where}: declared more than once")
        seen_roles.add(entry.role)
        if not entry.any_of:
            errors.append(f"{where}: names no skillset")
        for requirement in entry.any_of:
            errors.extend(f"{where}: {e}" for e in _one_requirement_errors(requirement))
    return errors


def _one_requirement_errors(requirement: SkillsetRequirement) -> list[str]:
    name = requirement.skillset or "?"
    errors: list[str] = []
    if not requirement.skillset.strip():
        errors.append("a requirement names a concrete skillset")
    if requirement.version and parse_version_constraint(requirement.version) is None:
        errors.append(
            f"{name}: version constraint {requirement.version!r} is neither an exact "
            f'version ("2") nor a minimum (">=2")'
        )
    seen: set[tuple[str, str]] = set()
    for need in requirement.needs:
        if not need.contract.strip():
            errors.append(f"{name}: a need names its contract")
        elif (need.contract, need.mode) in seen:
            errors.append(
                f"{name}: {need.contract}{' in ' + need.mode if need.mode else ''} "
                f"is needed more than once"
            )
        seen.add((need.contract, need.mode))
    return errors
