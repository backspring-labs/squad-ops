"""How a manifest came to be, recorded on the manifest (#803, M5).

Bug classes guarded:

- **the stamp moving the manifest hash** — the load-bearing one. `content_hash()` is what the
  verification contract binds, what M0a's standing guard pins, and what every bind-mode cycle
  checks. A provenance-only edit that moved it would break all three at once, and would do it
  silently, because nothing about adding a record *looks* like a structural change. This is
  the M2 `decisions` lesson, and it is the reason both live outside `_canonical`;
- a seeded manifest — the reference included — failing to parse because the field is not
  optional;
- the stamp rewriting the author's document instead of appending to it, which would discard
  the comments and grouping a design document exists to carry;
- an author-supplied block surviving, so the one field that must be *observed* becomes one
  the author can *assert*;
- revisions recorded as a bare count, which cannot distinguish a schema failure from a
  winnability rejection from the author's own refinement — three causes with opposite
  remedies (§5c.5);
- a clean first attempt inventing a revision it never had.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.capabilities.handlers.planning.manifest import (
    _stamp_provenance,
    _without_authored_provenance,
)
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.authoring_failure import assess_authoring_outcome
from squadops.cycles.manifest_authoring import AUTHORED_MODE

pytestmark = [pytest.mark.domain_capabilities]

_REFERENCE_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)
_REFERENCE = _REFERENCE_PATH.read_text(encoding="utf-8")


class _Ctx:
    cycle_id = "cyc_77cbb5aab7ca"
    task_id = "task-run_516f0fed-003-development.author_manifest"


def _broken(mutate) -> str:
    data = yaml.safe_load(_REFERENCE)
    mutate(data)
    return yaml.dump(data, sort_keys=False)


# --------------------------------------------------------------------------- #
# The hash must not move
# --------------------------------------------------------------------------- #


def test_stamping_provenance_does_not_move_the_manifest_hash():
    """The whole reason provenance sits outside `_canonical`. The contract binds this hash;
    if recording *how* a manifest was written changed *what* it describes, every bound cycle
    would break on a bookkeeping edit."""
    before = InterfaceManifest.from_yaml(_REFERENCE).content_hash()

    stamped = _stamp_provenance(_REFERENCE, _Ctx(), [assess_authoring_outcome(_REFERENCE)])

    assert InterfaceManifest.from_yaml(stamped).content_hash() == before


def test_the_reference_manifests_hash_is_the_one_the_contract_binds():
    """Pinned literally, not just self-consistently: M0a's guard and contract v9 both key on
    this exact value, so a test comparing the manifest only to itself would let the pair
    drift together."""
    assert InterfaceManifest.from_yaml(_REFERENCE).content_hash().startswith("bb472e267e53")


@pytest.mark.parametrize(
    "revisions",
    [[], [{"attempt": 1, "classes": {"authoring_defect": 1}, "proofs": ["parses"]}]],
)
def test_the_hash_ignores_what_the_provenance_says(revisions):
    """Not merely 'a provenance block is ignored' — its *contents* are too. Two runs that
    authored the same design in a different number of attempts must produce the same hash, or
    the golden benchmark stops comparing designs and starts comparing luck."""
    base = InterfaceManifest.from_yaml(_REFERENCE).content_hash()
    doc = (
        _REFERENCE
        + "\n"
        + yaml.safe_dump(
            {
                "provenance": {
                    "mode": AUTHORED_MODE,
                    "attempts": len(revisions),
                    "revisions": revisions,
                }
            }
        )
    )

    assert InterfaceManifest.from_yaml(doc).content_hash() == base


# --------------------------------------------------------------------------- #
# Presence, absence, and shape
# --------------------------------------------------------------------------- #


def test_a_seeded_manifest_has_no_provenance_and_stays_valid():
    """Absence is the signal that this system did not author it — so it must parse, not
    fail. The reference instance is the case that would break everything."""
    assert InterfaceManifest.from_yaml(_REFERENCE).provenance is None


def test_the_stamp_records_what_the_loop_actually_observed():
    outcomes = [
        assess_authoring_outcome(_broken(lambda d: d.pop("source_prd"))),
        assess_authoring_outcome(_REFERENCE),
    ]

    stamped = InterfaceManifest.from_yaml(_stamp_provenance(_REFERENCE, _Ctx(), outcomes))
    prov = stamped.provenance

    assert prov.mode == AUTHORED_MODE
    assert prov.cycle_id == "cyc_77cbb5aab7ca"
    assert prov.attempts == 2
    assert len(prov.revisions) == 1, "only the rejected attempt is a revision"
    assert prov.revisions[0].attempt == 1
    assert prov.revisions[0].classes == {"authoring_defect": 1}
    assert prov.revisions[0].proofs == ("source_prd",)


def test_a_clean_first_attempt_records_no_revisions():
    """A record that invented a revision would put an authoring defect in B1's baseline that
    never happened — the counts are read as evidence, so they cannot be decorative."""
    stamped = InterfaceManifest.from_yaml(
        _stamp_provenance(_REFERENCE, _Ctx(), [assess_authoring_outcome(_REFERENCE)])
    )

    assert stamped.provenance.attempts == 1
    assert stamped.provenance.revisions == ()


def test_the_reason_is_a_class_not_a_count():
    """§5c.5's requirement, as an assertion. 'Three attempts' cannot distinguish a schema
    failure from a winnability rejection from a deriver defect, and those have opposite
    remedies — the class is what makes the record actionable."""
    outcomes = [
        assess_authoring_outcome(_broken(lambda d: d["api"].update(endpoints=[]))),
        assess_authoring_outcome(_REFERENCE),
    ]

    prov = InterfaceManifest.from_yaml(_stamp_provenance(_REFERENCE, _Ctx(), outcomes)).provenance

    assert prov.revisions[0].classes, "a revision with no class is the bucket M6 exists to prevent"
    assert "lint" in prov.revisions[0].proofs


# --------------------------------------------------------------------------- #
# The author's document survives; the author's provenance does not
# --------------------------------------------------------------------------- #


def test_the_authors_document_is_left_byte_intact_above_the_stamp():
    """Appended, never re-emitted. A round-trip through the parser would silently strip the
    comments and grouping that make a manifest readable — and the reference's own header
    comments are the example of what would be lost."""
    stamped = _stamp_provenance(_REFERENCE, _Ctx(), [assess_authoring_outcome(_REFERENCE)])

    assert stamped.startswith(_REFERENCE.rstrip("\n"))
    assert "# group_run interface manifest — Phase-0.5 spike reference instance." in stamped


def test_an_author_supplied_provenance_block_is_discarded():
    """The one field that must be observed rather than claimed. Left in place it would also
    leave two top-level `provenance` keys in one document — parseable by last-wins, and
    unreadable."""
    claimed = _REFERENCE + "\nprovenance:\n  mode: authored\n  attempts: 1\n  revisions: []\n"
    outcomes = [
        assess_authoring_outcome(_broken(lambda d: d.pop("source_prd"))),
        assess_authoring_outcome(_REFERENCE),
    ]

    stamped = _stamp_provenance(claimed, _Ctx(), outcomes)

    assert stamped.count("provenance:") == 1
    assert InterfaceManifest.from_yaml(stamped).provenance.attempts == 2


def test_stripping_a_provenance_block_leaves_neighbouring_keys_alone():
    """Line-scoped removal: the block ends at the next top-level key, so a `persistence:` or
    `decisions:` that follows it must survive."""
    doc = (
        "version: 1\n"
        "provenance:\n"
        "  mode: authored\n"
        "  revisions:\n"
        "    - attempt: 1\n"
        "persistence: in_memory\n"
    )

    stripped = _without_authored_provenance(doc)

    assert "provenance" not in stripped
    assert yaml.safe_load(stripped) == {"version": 1, "persistence": "in_memory"}


def test_a_malformed_provenance_block_does_not_make_the_design_unparseable():
    """A record is not a contract. A bookkeeping defect must never reject a design the squad
    got right."""
    manifest = InterfaceManifest.from_yaml(_REFERENCE + "\nprovenance: not-a-mapping\n")

    assert manifest.provenance is None
    assert manifest.lint() == []
