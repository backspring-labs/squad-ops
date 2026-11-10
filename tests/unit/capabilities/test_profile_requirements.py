"""What a development profile requires of a squad (SIP-0116 §5.1, phase 1): declared, shape
checked, and covered by the profile's fingerprint only where declared."""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from squadops.stacks import development_profiles
from squadops.stacks.development_profiles import (
    DEVELOPMENT_PROFILES,
    development_profile_fingerprint,
)
from squadops.stacks.requirements import (
    ContractNeed,
    PlatformTarget,
    ResponsibilityRequirement,
    SkillsetRequirement,
    requirement_errors,
    version_satisfies,
)
from squadops.tasks.base_set import base_plannable_task_types

pytestmark = [pytest.mark.domain_capabilities]

PLATFORM = PlatformTarget("fixture", "local")
QA = ResponsibilityRequirement(
    "qa",
    (
        SkillsetRequirement(
            "fixture-qa",
            ">=2",
            (ContractNeed("fixture.unit_tests", "headless"), ContractNeed("fixture.design")),
        ),
    ),
)


@pytest.mark.parametrize("name", sorted(DEVELOPMENT_PROFILES))
def test_a_profile_that_requires_nothing_keeps_the_fingerprint_it_had(name):
    """Bug caught: a new dataclass field entering every profile's digest. Each stored
    ``development_profile_selection`` would then stop matching, and every retry of a pinned
    cycle would report drift on a profile nobody changed. The expected digest is built from
    the definition as it was before SIP-0116, without the two keys."""
    profile = DEVELOPMENT_PROFILES[name]
    assert profile.platform is None and profile.requires == ()
    before = dataclasses.asdict(profile)
    del before["platform"], before["requires"]
    expected = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()[:16]

    assert development_profile_fingerprint(name) == expected


def test_declared_requirements_are_part_of_the_fingerprint(monkeypatch):
    """Bug caught: a profile whose requirements change keeping its fingerprint, so a retry
    can't tell that the work now asks something else of the squad."""
    plain = DEVELOPMENT_PROFILES["python_cli"]
    monkeypatch.setitem(
        development_profiles.DEVELOPMENT_PROFILES,
        "requires_one",
        dataclasses.replace(plain, name="requires_one", platform=PLATFORM, requires=(QA,)),
    )
    stricter = dataclasses.replace(QA, any_of=(dataclasses.replace(QA.any_of[0], version="3"),))
    monkeypatch.setitem(
        development_profiles.DEVELOPMENT_PROFILES,
        "requires_other",
        dataclasses.replace(plain, name="requires_one", platform=PLATFORM, requires=(stricter,)),
    )
    monkeypatch.setitem(
        development_profiles.DEVELOPMENT_PROFILES,
        "requires_none",
        dataclasses.replace(plain, name="requires_one"),
    )

    prints = {
        development_profile_fingerprint(n)
        for n in ("requires_one", "requires_other", "requires_none")
    }

    assert len(prints) == 3


def test_every_registered_profile_declares_well_formed_requirements():
    for name, profile in DEVELOPMENT_PROFILES.items():
        assert requirement_errors(profile.platform, profile.requires) == [], name


def test_a_well_formed_requirement_has_no_errors():
    alternatives = ResponsibilityRequirement(
        "dev", (SkillsetRequirement("fixture-dev"), SkillsetRequirement("fixture-dev-b", "1"))
    )

    second_for_qa = ResponsibilityRequirement("qa", (SkillsetRequirement("fixture-capture"),))

    assert requirement_errors(PLATFORM, (QA, alternatives, second_for_qa)) == []
    assert requirement_errors(None, ()) == []


@pytest.mark.parametrize(
    ("platform", "requires", "expected"),
    [
        (None, (QA,), ["requires: a profile that requires skillsets declares its platform"]),
        (PlatformTarget("fixture", " "), (), ["platform: both id and variant are required"]),
        (PLATFORM, (QA, QA), ["requires[qa]: fixture-qa is required more than once"]),
        (PLATFORM, (ResponsibilityRequirement("qa", ()),), ["requires[qa]: names no skillset"]),
        (
            PLATFORM,
            (ResponsibilityRequirement("qa", (SkillsetRequirement("fixture-qa", ">2"),)),),
            [
                "requires[qa]: fixture-qa: version constraint '>2' is neither an exact "
                'version ("2") nor a minimum (">=2")'
            ],
        ),
        (
            PLATFORM,
            (ResponsibilityRequirement("qa", (SkillsetRequirement(""),)),),
            ["requires[qa]: a requirement names a concrete skillset"],
        ),
        (
            PLATFORM,
            (
                ResponsibilityRequirement(
                    "qa",
                    (
                        SkillsetRequirement(
                            "fixture-qa",
                            needs=(
                                ContractNeed("fixture.unit_tests", "headless"),
                                ContractNeed("fixture.unit_tests", "headless"),
                                ContractNeed(""),
                            ),
                        ),
                    ),
                ),
            ),
            [
                "requires[qa]: fixture-qa: fixture.unit_tests in headless is needed more than once",
                "requires[qa]: fixture-qa: a need names its contract",
            ],
        ),
    ],
)
def test_a_malformed_requirement_is_named_by_responsibility_and_skillset(
    platform, requires, expected
):
    assert requirement_errors(platform, requires) == expected


@pytest.mark.parametrize(
    ("constraint", "version", "met"),
    [
        ("", 1, True),
        ("2", 2, True),
        ("2", 3, False),
        (">=2", 2, True),
        (">=2", 5, True),
        (">=2", 1, False),
        ("~2", 2, False),
        (">=0", 1, False),
        ("2.1", 2, False),
    ],
)
def test_a_version_constraint_is_an_exact_version_or_a_minimum(constraint, version, met):
    assert version_satisfies(constraint, version) is met


def test_an_unknown_base_set_version_is_refused_by_name():
    with pytest.raises(ValueError, match=r"Unknown base set 'base@7'\. Known: base@1"):
        base_plannable_task_types("base@7")
