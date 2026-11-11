"""A fixture squad, catalog and development profile whose work requires skillsets (SIP-0116).

Shared by the tests of the kept copy and of what a dispatch is handed: a qa agent and a dev
agent, a skillset each is assigned to supply, one the qa agent only carries, and a capability
of the qa skillset the work doesn't name.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

from squadops.capabilities.capability_contracts import (
    CapabilityContractDeclaration,
    VerificationMode,
)
from squadops.capabilities.skillsets import Skillset, SkillsetCapability, skill_files_digest
from squadops.cycles.models import AgentProfileEntry, SquadProfile
from squadops.cycles.skillset_record import skillset_record_and_content
from squadops.stacks import development_profiles
from squadops.stacks.requirements import (
    ContractNeed,
    PlatformTarget,
    ResponsibilityRequirement,
    SkillsetRequirement,
)
from squadops.tasks.task_types import TaskType

NOW = datetime(2026, 11, 10, tzinfo=UTC)
LOADER = {"SKILL.md": "---\nname: test-loader\n---\nWrite specs.\n", "loader.luau": "return {}\n"}
PLAY = {"SKILL.md": "---\nname: play-scenario\n---\nPlay it.\n"}
DEV = {"SKILL.md": "---\nname: luau\n---\nStrict mode.\n"}
SHARED = {"SKILL.md": "---\nname: conventions\n---\nNames.\n"}

CONTRACTS = {
    "fixture.unit_tests": CapabilityContractDeclaration(
        "fixture.unit_tests", TaskType.QA_TEST, "per test", (VerificationMode.HEADLESS,)
    ),
    "fixture.scenario": CapabilityContractDeclaration(
        "fixture.scenario",
        TaskType.QA_RUN_REMOTE_OPERATION,
        "per assertion",
        (VerificationMode.PLAY,),
    ),
    "fixture.suite_review": CapabilityContractDeclaration(
        "fixture.suite_review", TaskType.QA_TEST, "per test", (VerificationMode.HEADLESS,)
    ),
    "fixture.implementation": CapabilityContractDeclaration(
        "fixture.implementation", TaskType.DEVELOPMENT_DEVELOP, "source", ()
    ),
}


def skillset(skillset_id, role, capabilities, files_by_skill) -> Skillset:
    digests = {name: skill_files_digest(files) for name, files in files_by_skill.items()}
    return Skillset(
        id=skillset_id,
        version=2,
        description="fixture",
        roles=(role,),
        platform_id="fixture",
        platform_variants=("local",),
        prerequisites=(),
        capabilities=capabilities,
        skill_digests=digests,
        digest=f"digest-of-{skillset_id}",
        skill_files=files_by_skill,
    )


def catalog() -> dict[str, Skillset]:
    return {
        "fixture-qa": skillset(
            "fixture-qa",
            "qa",
            (
                SkillsetCapability(
                    "fixture.unit_tests",
                    (VerificationMode.HEADLESS,),
                    ("test-loader", "shared/conventions"),
                ),
                SkillsetCapability(
                    "fixture.scenario", (VerificationMode.PLAY,), ("play-scenario",)
                ),
                # A capability of the skillset this cycle's work doesn't name.
                SkillsetCapability(
                    "fixture.suite_review", (VerificationMode.HEADLESS,), ("shared/conventions",)
                ),
            ),
            {"test-loader": LOADER, "play-scenario": PLAY, "shared/conventions": SHARED},
        ),
        "fixture-dev": skillset(
            "fixture-dev",
            "dev",
            (SkillsetCapability("fixture.implementation", (), ("luau", "shared/conventions")),),
            {"luau": DEV, "shared/conventions": SHARED},
        ),
        # Carried by an agent, required by nothing.
        "fixture-web": skillset(
            "fixture-web",
            "qa",
            (SkillsetCapability("fixture.unit_tests", (VerificationMode.HEADLESS,), ("web",)),),
            {"web": {"SKILL.md": "---\nname: web\n---\nPlaywright.\n"}},
        ),
    }


PROFILE = SquadProfile(
    profile_id="fixture-squad",
    name="Fixture",
    description="",
    version=1,
    agents=(
        AgentProfileEntry("eve", "qa", "m", True, {}, ("qa",), ("fixture-qa", "fixture-web")),
        AgentProfileEntry("neo", "dev", "m", True, {}, ("dev",), ("fixture-dev",)),
    ),
    created_at=NOW,
)


def requiring_config(monkeypatch) -> dict:
    """A cycle on a development profile whose work requires both fixture skillsets. None is
    registered, so one is put in the registry for the test."""
    requires = (
        ResponsibilityRequirement(
            "qa",
            (
                SkillsetRequirement(
                    "fixture-qa",
                    ">=2",
                    (
                        ContractNeed("fixture.unit_tests", "headless"),
                        ContractNeed("fixture.scenario", "play"),
                    ),
                ),
            ),
        ),
        ResponsibilityRequirement(
            "dev",
            (SkillsetRequirement("fixture-dev", "", (ContractNeed("fixture.implementation"),)),),
        ),
    )
    profile = dataclasses.replace(
        development_profiles.DEVELOPMENT_PROFILES["python_cli"],
        name="fixture_stack",
        platform=PlatformTarget("fixture", "local"),
        requires=requires,
    )
    monkeypatch.setitem(development_profiles.DEVELOPMENT_PROFILES, "fixture_stack", profile)
    return {"development_profile": "fixture_stack"}


def built(config, skillsets=None):
    """The record and the kept copy of a cycle created under ``config``."""
    return skillset_record_and_content(PROFILE, "hash-1", config, skillsets or catalog(), CONTRACTS)
