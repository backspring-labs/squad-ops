"""A project instruction's applicability, checked against what dispatches carry (SIP-0110 Appendix A §3.6;
the second read of PR #2515). One check for every route that writes one: the records API and chat's
capture (#2180 stage B), so an instruction is refused the same way however it is written."""

from __future__ import annotations

from typing import Any

from squadops.agents.models import DEFAULT_ROLES
from squadops.api.errors import http_error
from squadops.capabilities.context_assembly import authoring_seam_of
from squadops.stacks.development_profiles import DEVELOPMENT_PROFILES


def unmatched(applicability: Any) -> list[str]:
    """What an applicability names that no dispatch carries: a task type that authors nothing, a role
    no squad has, a stack no profile builds. Each would never match, so the instruction would bind
    nothing and say nothing."""
    vocabularies = (
        ("task type", applicability.task_types, lambda t: authoring_seam_of(t) is not None),
        ("role", applicability.roles, lambda r: r in DEFAULT_ROLES),
        ("stack", applicability.stacks, lambda s: s in DEVELOPMENT_PROFILES),
    )
    return [
        f"{name} {value!r}"
        for name, values, known in vocabularies
        for value in values
        if value != "*" and not known(value)
    ]


def refuse_unmatched(applicability: Any) -> None:
    """Refused (422) when the applicability names what no dispatch carries, listing the vocabulary."""
    found = unmatched(applicability)
    if found:
        raise http_error(
            422,
            "VALIDATION_ERROR",
            f"the applicability names what no dispatch carries: {', '.join(found)} "
            f"(roles: {', '.join(sorted(DEFAULT_ROLES))}; stacks: "
            f"{', '.join(sorted(DEVELOPMENT_PROFILES))}; '*' for any)",
        )
