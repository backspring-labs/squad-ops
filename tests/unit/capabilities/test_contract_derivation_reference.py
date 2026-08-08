"""M0a — the contract deriver is pinned to the deployed reference pair (#777).

SIP-0103 §5b Correction 1 asserted that contract v9 was hand-authored and that no
``derive_contract(manifest)`` existed. Measurement at build time found the opposite:
the deriver is :func:`squadops.capabilities.scaffold_contract.emit_contract_dict`
(SIP-0098 phase 98.2), and the ingested contract ``art_4f368ea08799`` is precisely its
output for the ingested manifest ``art_8becd104e9fc``. The v1.6 plan carries that
correction; this module makes the equality it uncovered impossible to lose quietly.

**Why pin it.** Three things in Track M now rest on this deriver: M0b derives a
contract at seed time for authored manifests, M3's winnability gate dry-runs the
derived contract, and Guard 1b requires the reference manifest to produce
byte-identical downstream artifacts. An unpinned invariant with three dependents is a
regression waiting for a quiet afternoon.

**Both ends are held**, because either alone is defeatable:

* the in-repo reference manifest must still be the artifact the 1.4 evidence used —
  otherwise the deriver could keep "matching" a reference that had drifted;
* the deriver must still reproduce the *ingested* contract from it — the bytes bind-mode
  cycles actually load, not a copy regenerated from the deriver under test.

**No regeneration hatch, deliberately.** The pinned contract here is not a
golden that tracks code evolution; it is a reference tied to banked evidence — the 1.4
Functional App Yield window (6/6, five consecutive) was measured against this contract.
A one-env-var regen would invite exactly the casual update the plan's M0 divergence
taxonomy exists to prevent. Changing it is a deliberate act, classified per that
taxonomy, and its ``reference_defect`` class carries a retrospective obligation.

Bug classes guarded: a deriver change that silently alters the criteria the deployed
contract asserts; an edit to the reference manifest without a corresponding contract
update (or the reverse); and a reference pair that quietly stops being the vault's.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold_contract import emit_contract_dict, emit_contract_yaml

_REPO = Path(__file__).resolve().parents[3]
# The manifest is a genuine product input: scripts/dev/contract_gate.py defaults to
# it, and it is the file ingested to the vault as art_8becd104e9fc. It stays in
# examples/ where a human can read and copy it.
_MANIFEST = _REPO / "examples" / "03_group_run" / "interface_manifest.yaml"
# The contract is NOT an input. contract_gate.py *generates* it from the manifest
# and prints the `artifacts ingest` command; committing it beside the manifest put
# a generated artifact in the source tree, in a directory that reads as
# user-facing examples. It lives here instead: its only consumer is this test.
_CONTRACT = (
    _REPO / "tests" / "fixtures" / "reference_contract" / "contract_v9_art_4f368ea08799.yaml"
)

# The ingested artifacts, by content hash. Measured 2026-08-07 against the vault:
#   art_8becd104e9fc — interface manifest v4
#   art_4f368ea08799 — verification contract v9
# These are the exact bytes the 1.4 FAY window and every bind-mode cycle since have
# run against. A change here is a change to the evidence base, not a refactor.
_MANIFEST_SHA256 = "52d8ea7e204e0ceca9c94a60a7b10f18a24519e594ce5c51654674b82a15a826"
_CONTRACT_SHA256 = "7622f570c949fe9504bfebdcd0562e77e78b4d8bff54d9d670001b7f6482e6fe"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reference_manifest_is_still_the_ingested_artifact():
    """Guard the input end: the deriver matching a drifted reference proves nothing."""
    assert _sha256(_MANIFEST) == _MANIFEST_SHA256, (
        "examples/03_group_run/interface_manifest.yaml no longer matches ingested "
        "manifest v4 (art_8becd104e9fc). If this change is intended, it changes the "
        "reference instance the 1.4 evidence was measured against — classify it per "
        "the M0 divergence taxonomy in docs/plans/1-6-0-authorship-plan.md before "
        "updating this hash."
    )


def test_reference_contract_is_still_the_ingested_artifact():
    """Guard the output end against a regenerated-in-place copy.

    If someone regenerates the committed contract from the deriver, the equality test
    below becomes a tautology — the deriver proving it equals itself. This hash is
    what stops that.
    """
    assert _sha256(_CONTRACT) == _CONTRACT_SHA256, (
        "tests/fixtures/reference_contract/contract_v9_art_4f368ea08799.yaml no longer "
        "matches ingested "
        "contract v9 (art_4f368ea08799). These are the bytes bind-mode cycles load; "
        "regenerating them locally would make the derivation test tautological."
    )


def test_deriver_reproduces_the_deployed_contract_byte_for_byte():
    """The invariant M0b, M3, and Guard 1b all rest on.

    Byte equality rather than semantic equality: the emitted YAML *is* the artifact
    that gets ingested, so serialization is part of the contract, not an accident of it.
    """
    manifest = InterfaceManifest.from_yaml(_MANIFEST.read_text(encoding="utf-8"))

    assert emit_contract_yaml(manifest) == _CONTRACT.read_text(encoding="utf-8")


def test_derived_criteria_match_the_deployed_contract_semantically():
    """The same equality one layer up, so a failure says *which section* moved.

    Byte equality alone reports "these files differ"; a structural comparison names
    the section, which is the difference between a five-minute diagnosis and an hour.
    """
    manifest = InterfaceManifest.from_yaml(_MANIFEST.read_text(encoding="utf-8"))
    derived = emit_contract_dict(manifest)
    deployed = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))

    assert set(derived) == set(deployed)
    for section in sorted(derived):
        assert derived[section] == deployed[section], f"derived contract diverges in {section!r}"


def test_the_reference_pair_is_non_trivial():
    """A guard over an empty contract would pass while proving nothing.

    Pins the shape the 1.4 evidence actually covered: four fill slots and five probes.
    """
    deployed = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))

    assert len(deployed["fill_files"]) == 4
    assert len(deployed["behavioral"]["probes"]) == 5
