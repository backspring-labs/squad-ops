"""Contract 8, the derived development profile, as both lanes read it (SIP-0112 H.6, #2619).

The MacBook lane writes the profile; SIP-0109 §24bv and SIP-0113 §10l read it. Until the derivation
and its readers ship, these tests hold the one reader both lanes call to the fixture's recordings.
Each seam's wiring test lands with the PR that builds that seam.
"""

from __future__ import annotations

import copy

import pytest

from squadops.projects.derived_profile import (
    ProfileInvalid,
    StaleProfile,
    UnknownProfileVersion,
    parse_profile,
)
from tests.fixtures.shared_contract.repository import recorded

_ABSENT = object()


def _valid() -> dict:
    return copy.deepcopy(recorded("derived_profile", "valid"))


def _with(path: tuple, value: object) -> dict:
    doc = _valid()
    *parents, last = path
    target = doc
    for key in parents:
        target = target[key]
    if value is _ABSENT:
        del target[last]
    else:
        target[last] = value
    return doc


def test_the_recorded_profile_reads_back_as_it_was_recorded():
    profile = parse_profile(_valid())

    assert profile.to_document() == recorded("derived_profile", "valid")
    assert [(g.id, g.kind, g.stops) for g in profile.gaps] == [
        ("missing_environment", "disclosed", "verification"),
        ("no_test_id_reader", "disclosed", "per_test_reading"),
    ]
    assert profile.blocking == ()


@pytest.mark.parametrize(
    ("gap", "kind", "stops"),
    [
        ("missing_toolchain", "blocking", "work"),
        ("missing_toolchain", "disclosed", "verification"),
        ("test_files_unclassed", "blocking", "campaigns"),
    ],
)
def test_what_a_gap_stops_follows_its_id_and_kind(gap, kind, stops):
    doc = _with(("gaps", 0), {**_valid()["gaps"][0], "id": gap, "kind": kind})

    profile = parse_profile(doc)

    assert profile.gaps[0].stops == stops
    assert [g.id for g in profile.blocking] == ([gap] if kind == "blocking" else [])


@pytest.mark.parametrize(
    ("form", "error", "field"),
    [
        ("missing_field", ProfileInvalid, "development_configuration_revision"),
        ("unknown_major", UnknownProfileVersion, "schema"),
    ],
)
def test_a_bad_recording_is_refused_naming_its_field(form, error, field):
    with pytest.raises(error) as raised:
        parse_profile(recorded("derived_profile", form))

    assert type(raised.value) is error
    assert raised.value.field == field


def test_a_profile_derived_at_another_commit_or_revision_is_refused_as_stale():
    valid = parse_profile(_valid())
    stale = parse_profile(recorded("derived_profile", "stale_commit"))
    pinned = {"commit": valid.commit, "development_configuration_revision": 1}

    valid.require_current(**pinned)
    with pytest.raises(StaleProfile) as by_commit:
        stale.require_current(**pinned)
    with pytest.raises(StaleProfile) as by_revision:
        valid.require_current(commit=valid.commit, development_configuration_revision=2)

    assert by_commit.value.field == "commit"
    assert by_revision.value.field == "development_configuration_revision"


@pytest.mark.parametrize(
    ("path", "value", "field"),
    [
        (("gaps", 0, "kind"), "advisory", "gaps[0].kind"),
        (("gaps", 0, "kind"), "blocking", "gaps[0].kind"),
        (("gaps", 1, "id"), "slow_tests", "gaps[1].id"),
        (("gaps", 0, "paths"), [], "gaps[0].paths"),
        (("gaps", 0, "paths"), ["../elsewhere/**"], "gaps[0].paths"),
        (
            ("test_runners", 0, "single_file_argv"),
            ["python3", "-m", "unittest"],
            "test_runners[0].single_file_argv",
        ),
        (("test_runners", 0, "test_ids"), "junit", "test_runners[0].test_ids"),
        (("public_surfaces", 1, "argv"), "python3 -m tally", "public_surfaces[1].argv"),
        (("public_surfaces", 0, "kind"), "grpc", "public_surfaces[0].kind"),
        (("start_declared",), "yes", "start_declared"),
        (("blueprint",), _ABSENT, "blueprint"),
    ],
    ids=[
        "an unknown gap kind",
        "a kind its gap can't take",
        "an unknown gap",
        "a gap confined to nothing",
        "a path outside the repository",
        "a one-file command naming no file",
        "an unknown test-id reader",
        "a shell string for an argv",
        "an unknown surface",
        "a non-boolean",
        "a nullable field left out",
    ],
)
def test_a_value_outside_the_contract_is_refused_naming_its_field(path, value, field):
    with pytest.raises(ProfileInvalid) as raised:
        parse_profile(_with(path, value))

    assert raised.value.field == field


def test_a_field_this_reader_doesnt_know_is_left_unread():
    doc = _valid()
    doc["derived_by"] = "squadops 2.5.1"
    doc["gaps"][0]["since"] = "2026-10-24"

    assert parse_profile(doc).to_document() == recorded("derived_profile", "valid")
