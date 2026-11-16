"""The development profile a repository-backed cycle is pinned to (SIP-0112 H.13, H.26).

One function names it, and both places that need it call it: cycle creation, which pins it on
the cycle (``prepare_cycle``), and a Campaign's size preflight, which counts the skills the
first launch's record will assign under it (SIP-0116 §17m). Two readings of the same request
could otherwise pin two profiles, and the preflight would count another profile's skills with
nothing to say so.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from squadops.cycles.models import DerivedProfileNotFoundError, PreflightRejectedError
from squadops.stacks.development_profiles import (
    DEVELOPMENT_PROFILES,
    ORIGIN_OPERATOR,
    TEST_FRAMEWORK_PRODUCT_RUNNER,
    ProfileSelection,
    development_profile_conflict,
    select_development_profile,
)

if TYPE_CHECKING:
    from squadops.projects.derived_profile import DerivedProfile
    from squadops.projects.source_context import ProjectSourceContext


def development_profile_pin(
    config: Mapping[str, Any], profile: DerivedProfile | None
) -> ProfileSelection | None:
    """The development profile a product's cycle of ``config`` runs under, or ``None`` when
    nothing is pinned.

    The cycle would otherwise fall to ``python_cli``, whatever the product is: a Python package's
    prompts and a Python-only source filter on a vitest product. So the derived profile at the pin
    selects one (``select_development_profile``), to be pinned in ``execution_overrides``
    (``pinned_overrides``): one value on the cycle record, read by every task, retry and repair
    through ``effective_development_profile``, beside the record of where it came from and a
    fingerprint of what it does. It seeds nothing (``seeds_skeleton``).

    A profile the request names stands, unless it contradicts the product's runners, which raises
    :class:`PreflightRejectedError` (``development_profile_conflict``) rather than run.

    A plan-less cycle's test author is shown the product, with the profile's test prose withheld in
    favour of its conventions (H.29), but its developer's monolithic prompt still lays files out by
    the profile's ``file_structure_guidance`` and ``example_structure``. So a profile with skeleton
    prose would place its files: such a cycle gets a pin only from a profile that holds none, which
    the ones leaving the suite to the product's runner don't. Nothing is pinned with no profile at
    the pin, for a sample application's ``build_profile``, or for a name the registry doesn't hold
    (the create preflight refuses that name)."""
    if profile is None:
        return None
    runners = [r.runner for r in profile.runners]
    named = str(config.get("development_profile") or "")
    if config.get("build_profile"):
        return None  # a sample application's profile on a product: preflight says so, and why
    if named in DEVELOPMENT_PROFILES:
        conflict = development_profile_conflict(named, runners)
        if conflict:
            raise PreflightRejectedError(f"development_profile_conflict: {conflict}")
        return ProfileSelection(named, ORIGIN_OPERATOR)
    if named:
        return None  # an unknown name is the create preflight's to refuse
    selection = select_development_profile(runners, profile.blueprint_stack)
    planned = config.get("implementation_plan") or config.get("typed_acceptance")
    framework = DEVELOPMENT_PROFILES[selection.name].test_framework
    if not planned and framework != TEST_FRAMEWORK_PRODUCT_RUNNER:
        return None
    return selection


def pinned_overrides(
    overrides: Mapping[str, Any] | None, selection: ProfileSelection
) -> dict[str, Any]:
    """``overrides`` with ``selection`` pinned: its name, its record and its fingerprint."""
    record = selection.to_record()
    return {
        **(overrides or {}),
        "development_profile": selection.name,
        "development_profile_selection": record,
        "development_profile_fingerprint": record["fingerprint"],
    }


async def derived_profile_at_pin(
    registry: Any, context: ProjectSourceContext
) -> DerivedProfile | None:
    """The derived profile at the Project's pin (contract 8), or ``None`` for a baseline captured
    before profiles were. An increment pinned at its campaign branch's head reads it at the
    Project's pin all the same, as SIP-0109 §24cd point 3 rules."""
    try:
        return await registry.get_derived_profile(
            context.project_id,
            at=(context.development_baseline_commit, context.development_configuration_revision),
        )
    except DerivedProfileNotFoundError:
        return None
