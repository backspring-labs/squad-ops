"""Gate 1's standing pin — reference manifest + generator version ⇒ byte-identical scaffold.

The M0a guard shape (``test_contract_derivation_reference``) applied to SIP-0104: the
committed fixture under ``tests/fixtures/reference_verification_scaffold/`` is the scaffold
GENERATOR_VERSION 1 emits for the reference nextjs_ts manifest, and the generator must keep
reproducing it byte for byte.

**Both ends are held.** The input end pins the reference manifest's content hash (a deriver
"matching" a drifted reference proves nothing); the output end pins the fixture's aggregate
hashes inside this file, so regenerating the fixture in place to match a changed generator
turns the byte test into a tautology *and still fails here* — the two must move together,
with a GENERATOR_VERSION bump, as one deliberate act.

**No regeneration hatch, deliberately** (the M0a rationale): a one-env-var regen invites
exactly the casual update that would let generator drift ship silently. Changing the
emission means: bump GENERATOR_VERSION, regenerate the fixture, update the two pinned
hashes here, and say why in the commit.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from squadops.capabilities.verification_scaffold import VerificationScaffoldManifest
from squadops.capabilities.verification_scaffold_emission import (
    GENERATOR_VERSION,
    emit_verification_scaffold,
)
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "reference_verification_scaffold"
)

# The reference nextjs_ts manifest (the shared fixture's /api re-stack of the group_run
# reference). Also pinned in test_stack_nextjs_ts; repeated here so THIS file is
# self-contained evidence that the input end did not move.
_MANIFEST_HASH = "ac1e7be378c54d5966680b85824c6f2c2e4d158eb8dec14d081209223e07053a"

# The fixture's own identity. Regenerated at GENERATOR_VERSION 7 (2026-08-22, #1029 — the
# frozen spine now asserts the SUCCESS body's floor as well as the error envelope: the
# declared-required fields of the responding entity are present, and a declared
# collection's elements match their declared kind. #913 did this one status class over;
# success bodies were where the last green roll spent its entire correction budget).
#
# Version 7 is the version-6 shape: only the SHELLS changed, so the spine hash moves. The
# rejection shell is the discriminator — a 4xx body is the envelope's business, so it takes
# NO success floor, and its bytes are unchanged from version 6. A pin that moved every
# shell equally would not show that the emission is per-behavior.
#
# These stop an in-place fixture regeneration from making the byte test self-referential.
# Version 8 (2026-08-25, #1096 + #1087) moved the FROZEN tree and not one shell: the model
# types `participants` as `Participant[]` instead of `string[]`, the store exports a table
# only for root-persisted entities, and the harness addresses one of those. So only the
# manifest's `expanded_tree_hash` changed, and the two pins below are byte-identical to
# version 7 — which is the evidence that the fix touched exactly the files it meant to and
# nothing the qa author fills.
_AGGREGATE_SPINE_HASH = "1ff59445d016f6d7385d713c5f31de7620fe3f065344db6a083bae7b1a0ab962"
_SCAFFOLD_HASH = "6fc46f50369bc9afd34e40607350b2464b74f79a6a8ef62772470037f5e98854"


@pytest.fixture(scope="module")
def emission():
    return emit_verification_scaffold(manifest_for_stack("nextjs_ts"))


def test_the_reference_manifest_is_unmoved():
    assert manifest_for_stack("nextjs_ts").content_hash() == _MANIFEST_HASH, (
        "the reference nextjs_ts manifest moved — the byte-equivalence pin below would be "
        "measuring a different input. If intended, this changes the reference instance the "
        "Gate 1 evidence is measured against; update deliberately."
    )


def test_generator_version_is_the_fixture_generation(emission):
    """A generator change without a version bump is drift by definition (SIP §4.3);
    a bump without regenerating the fixture is a pin measuring the wrong version."""
    assert GENERATOR_VERSION == 8
    assert emission.manifest.generator_version == 8
    stored = yaml.safe_load(
        (_FIXTURE_DIR / "verification_scaffold_manifest.yaml").read_text(encoding="utf-8")
    )
    assert stored["generator_version"] == 8


def test_emission_reproduces_the_fixture_byte_for_byte(emission):
    """Gate 1's exit criterion, exactly as the plan states it."""
    for f in emission.files:
        fixture = _FIXTURE_DIR / f["name"].rsplit("/", 1)[-1]
        assert fixture.exists(), f"fixture missing for emitted file {f['name']}"
        assert f["content"] == fixture.read_text(encoding="utf-8"), (
            f"{f['name']}: emitted bytes diverge from the committed reference — either "
            f"generator drift (bump GENERATOR_VERSION and regenerate deliberately) or an "
            f"unintended emission change"
        )
    assert emission.manifest_yaml == (
        _FIXTURE_DIR / "verification_scaffold_manifest.yaml"
    ).read_text(encoding="utf-8")


def test_no_fixture_file_is_orphaned(emission):
    """A deleted shell must fail the pin too — shrinkage is drift, not cleanup."""
    emitted = {f["name"].rsplit("/", 1)[-1] for f in emission.files}
    emitted.add("verification_scaffold_manifest.yaml")
    on_disk = {p.name for p in _FIXTURE_DIR.iterdir()}
    assert on_disk == emitted


def test_the_fixture_is_not_regenerated_in_place(emission):
    """The anti-tautology end: these hashes only change by editing THIS file."""
    assert emission.manifest.aggregate_spine_hash() == _AGGREGATE_SPINE_HASH
    assert emission.manifest.scaffold_hash() == _SCAFFOLD_HASH


def test_the_fixture_is_non_trivial(emission):
    """A pin over an empty scaffold would pass while proving nothing: the reference
    design must exercise every v1 shell kind — create, rejection, two chained child
    actions, a duplicate-conflict, a list read, a chained read, and an unknown-id read."""
    assert len(emission.files) == 8
    slots = [s for f in emission.manifest.files for s in f.slots]
    assert len(slots) == 8
    assert sum(1 for s in slots if s.probe_id) == 5


def test_the_stored_fixture_manifest_loads_and_verifies():
    """The committed record must round-trip the schema, including its aggregate
    verification — a hand-edited fixture manifest refuses to load."""
    stored = yaml.safe_load(
        (_FIXTURE_DIR / "verification_scaffold_manifest.yaml").read_text(encoding="utf-8")
    )
    loaded = VerificationScaffoldManifest.from_dict(stored)
    assert loaded.aggregate_spine_hash() == _AGGREGATE_SPINE_HASH
