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

from squadops.capabilities.scaffold import InterfaceManifest, expand
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
# The reference contract has two pins with two meanings (2026-08-25, #1079):
#
# * ``_EVIDENCE_CONTRACT`` — contract v9, the artifact bind-mode cycles ingested and the
#   1.4 Functional App Yield window (6/6, five consecutive) was measured against. Its bytes
#   never change; a file named for a vault artifact must stay that artifact.
# * ``_CONTRACT`` — the deriver's current form for the same manifest. It differs from v9
#   in exactly one way: the three success probes carry ``json_has`` (the responding
#   entity's declared-required fields), the producer ``json_has`` never had (#1079).
#   Classified **ambiguity_removal** per the M0 divergence taxonomy
#   (docs/plans/1-6-0-authorship-plan.md): v9 left the success body implicit; derivation
#   now states it. Not a reference defect, so the 1.4 figure carries no qualification —
#   it measured a weaker contract that every app passing this one also passes.
#   v10 stays in the fixtures directory as that form's record.
# * v11 (2026-08-27, #1127) differs from v10 in exactly one ``frozen`` entry: the sha256 of
#   ``frontend/src/test-setup.js``, which now registers ``afterEach(cleanup)``. Classified
#   **reference_defect** — the pinned harness was wrong (under vitest ``globals:false``
#   Testing Library never unmounts between tests, so a suite rendering in two tests fails
#   "Found multiple elements"), found by the 1.6.5 FastAPI+React set, not by a deriver
#   change. Retrospective obligation met by statement: that harness can only REJECT a
#   working application, never pass a broken one, so the 1.4 FAY figure (6/6) carries no
#   qualification — every app that passed under it passes under this one.
# * v12 (2026-09-06, #1087 / #1112) differs from v11 in exactly one ``frozen`` entry: the
#   sha256 of ``backend/store.py``, which now exports one store per ROOT-persisted entity
#   (``run_event_store`` on the reference) and names the embedded shapes and projections
#   that have none, instead of a dict per declared entity. Classified **reference_defect**:
#   the pinned store handed the qa author a table for a shape no correct app writes, and
#   two working applications were rejected for asserting on it in the 1.6.3 set. The
#   retrospective obligation is met by statement: a wider store can only make a working
#   app REJECTED (an assertion on an empty phantom table), never let a broken one pass, so
#   the 1.4 FAY figure (6/6) carries no qualification — every app that passed under it
#   passes under this one. v11 stays in the fixtures directory as that form's record.
# * v13 (2026-09-09, #1463) differs from v12 in exactly two ``frozen`` entries: a new
#   ``frontend/src/index.css``, and the sha256 of ``frontend/src/main.jsx``, which now
#   imports it. Classified **reference_defect** — the pinned reference describes a skeleton
#   that no longer exists, found by a deliberate scaffold change rather than a deriver one,
#   the same shape as v11 and v12. Stack #1 had shipped no stylesheet at all while stack #2
#   had one since #906, so a delivered app's presentation floor differed by stack for a
#   reason nobody chose. The retrospective obligation is met by statement: the sheet adds no
#   check and changes no criterion (``behavioral``, ``capabilities``, ``fill_files`` and
#   ``skeleton`` are byte-identical to v12), and presentation is not what the window
#   measured — so the 1.4 FAY figure (6/6) carries no qualification. It cannot make a broken
#   app pass, and the only way it could reject a working one is by failing to compile, which
#   the sandbox build disproves. v12 stays in the fixtures directory as that form's record.
_EVIDENCE_CONTRACT = (
    _REPO / "tests" / "fixtures" / "reference_contract" / "contract_v9_art_4f368ea08799.yaml"
)
_CONTRACT = (
    _REPO
    / "tests"
    / "fixtures"
    / "reference_contract"
    / "contract_v13_baseline_stylesheet_1463.yaml"
)

# The ingested artifacts, by content hash. Measured 2026-08-07 against the vault:
#   art_8becd104e9fc — interface manifest v4
#   art_4f368ea08799 — verification contract v9
# These are the exact bytes the 1.4 FAY window and every bind-mode cycle since have
# run against. A change here is a change to the evidence base, not a refactor.
_MANIFEST_SHA256 = "52d8ea7e204e0ceca9c94a60a7b10f18a24519e594ce5c51654674b82a15a826"
_EVIDENCE_CONTRACT_SHA256 = "7622f570c949fe9504bfebdcd0562e77e78b4d8bff54d9d670001b7f6482e6fe"
_CONTRACT_SHA256 = "ee3d8a05e54cb0de16de690ca77a31c6f75b2ff31427de67a4a4324684aa56a5"


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
    assert _sha256(_EVIDENCE_CONTRACT) == _EVIDENCE_CONTRACT_SHA256, (
        "tests/fixtures/reference_contract/contract_v9_art_4f368ea08799.yaml no longer "
        "matches ingested contract v9 (art_4f368ea08799). Those are the bytes the 1.4 "
        "evidence was measured against; they are history, and history is not regenerated."
    )
    assert _sha256(_CONTRACT) == _CONTRACT_SHA256, (
        "tests/fixtures/reference_contract/contract_v12_root_tables_1087.yaml no longer matches "
        "its pinned hash. Regenerating it in place would make the derivation test below "
        "tautological — a deriver change is classified per the M0 taxonomy and lands with a "
        "new hash here, deliberately."
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


def test_the_current_form_differs_from_the_evidence_contract_only_as_classified():
    """The classifications' own check. The current form must be v9 plus exactly the two
    classified divergences and nothing else — any other drift is a different divergence with
    a different class, and this test is what makes each classification falsifiable:

    * #1079 (``ambiguity_removal``): the success probes carry ``json_has``;
    * #1127 (``reference_defect``): the frozen harness ``frontend/src/test-setup.js`` moved,
      because it now registers ``afterEach(cleanup)``;
    * #1087 (``reference_defect``): the frozen store ``backend/store.py`` moved, because it
      now exports one store per root-persisted entity and names the shapes that have none;
    * #1463 (``reference_defect``): ``frontend/src/index.css`` is ADDED and
      ``frontend/src/main.jsx`` moved to import it — the skeleton had no stylesheet at all.

    Three moved ``frozen`` entries and one added, no other, and nothing outside ``frozen``.
    """
    v9 = yaml.safe_load(_EVIDENCE_CONTRACT.read_text(encoding="utf-8"))
    current = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))
    for probe in current["behavioral"]["probes"]:
        if probe["expect"].get("status", 0) < 300:
            assert probe["expect"].pop("json_has") == [
                "id",
                "title",
                "datetime",
                "location",
                "participants",
            ]

    # Compared by path rather than positionally (#1463): the current form may ADD a frozen
    # file, which a strict zip reads as every later entry having moved.
    v9_frozen = {e["path"]: e["sha256"] for e in v9["frozen"]}
    current_frozen = {e["path"]: e["sha256"] for e in current["frozen"]}

    assert sorted(set(current_frozen) - set(v9_frozen)) == ["frontend/src/index.css"]
    assert not set(v9_frozen) - set(current_frozen), "a frozen file was dropped, not classified"

    moved = [
        (path, v9_frozen[path], sha)
        for path, sha in current_frozen.items()
        if path in v9_frozen and v9_frozen[path] != sha
    ]
    assert sorted(path for path, _, _ in moved) == [
        "backend/store.py",
        "frontend/src/main.jsx",
        "frontend/src/test-setup.js",
    ]
    expanded = {
        f["name"]: f["content"]
        for f in expand(InterfaceManifest.from_yaml(_MANIFEST.read_text(encoding="utf-8")))
    }
    # Every divergence is checked against what the expander emits TODAY, added included —
    # a classified entry whose sha nobody re-derives is a second pin that can rot.
    for path, _v9_sha, current_sha in [
        *moved,
        ("frontend/src/index.css", None, current_frozen["frontend/src/index.css"]),
    ]:
        emitted = expanded[path]
        assert hashlib.sha256(emitted.encode()).hexdigest() == current_sha, path
    # #1127: the harness unmounts between tests.
    assert "afterEach(cleanup)" in expanded["frontend/src/test-setup.js"]
    # #1087: the store is the roots only — RunEvent is stored; Participant (an embedded
    # shape) is named as having no store.
    store = expanded["backend/store.py"]
    assert "run_event_store: dict[str, RunEvent]" in store
    assert "participant_store" not in store
    assert "never rows themselves: Participant" in store
    # #1463: the sheet exists and the frozen entry point imports it. Both, because either
    # alone is a different broken state — dead bytes, or a build that fails on a missing
    # module.
    assert expanded["frontend/src/index.css"].startswith("/* Baseline presentation.")
    assert "import './index.css'\n" in expanded["frontend/src/main.jsx"]
    current["frozen"] = v9["frozen"]
    assert current == v9
