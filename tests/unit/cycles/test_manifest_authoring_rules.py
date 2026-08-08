"""#791 — the manifest gates' rules reach the manifest author (the #686 binding, one level up).

Plan authoring learned this the expensive way: shk-1 authored a shape the validators
already forbade, because the rule appeared in no prompt. The manifest gates landed before
the authoring stage specifically so the binding could exist first — these tests are what
make that ordering worth anything.

Three surfaces that must not drift apart: the gate module's proof constants, the
classification table, and the managed asset the author actually reads. Plus one asymmetry
worth its own test: a proof M6 attributes to the *deriver* must NOT be taught, because
teaching an author to work around a broken deriver both teaches a superstition and moves a
defect that is ours onto their ledger.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.cycles import manifest_gates
from squadops.cycles.authoring_failure import CLASS_OWNERSHIP, DERIVATION_DEFECT, classify_finding
from squadops.cycles.manifest_authoring_rules import (
    AUTHOR_FACING,
    COVERED_ELSEWHERE,
    NOT_AUTHOR_FACING,
    classified_proofs,
    rule_ids,
)
from squadops.cycles.manifest_gates import WinnabilityFinding

pytestmark = [pytest.mark.domain_contracts]

_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "request_templates"
)
_ASSET = _TEMPLATES / "request.manifest_authoring_rules_appendix.md"


def _gate_proofs() -> set[str]:
    return {
        value
        for name, value in vars(manifest_gates).items()
        if name.startswith("PROOF_") and isinstance(value, str)
    }


def test_every_gate_proof_is_classified_exactly_once():
    """The enforcement behind "a proof added to the gates lands here the day it ships". An
    unclassified proof means a rejection reason the author is never told about — the exact
    gap #686 closed for plans."""
    proofs = _gate_proofs()
    assert proofs, "the proof family must be discoverable by name"

    unclassified = proofs - classified_proofs()
    assert not unclassified, (
        f"gate proof(s) {sorted(unclassified)} are unclassified — add each to AUTHOR_FACING, "
        f"COVERED_ELSEWHERE, or NOT_AUTHOR_FACING in manifest_authoring_rules"
    )

    tables = (set(AUTHOR_FACING), set(COVERED_ELSEWHERE), set(NOT_AUTHOR_FACING))
    for i, first in enumerate(tables):
        for second in tables[i + 1 :]:
            assert not (first & second), f"proof(s) {sorted(first & second)} classified twice"


def test_the_classification_only_covers_proofs_that_exist():
    """The reverse drift: a proof renamed or deleted in the gates leaves a table entry
    teaching a rule nothing enforces."""
    stale = classified_proofs() - _gate_proofs()
    assert not stale, f"{sorted(stale)} are classified but no longer exist in manifest_gates"


@pytest.mark.parametrize("rule_id", sorted(rule_ids()))
def test_every_author_facing_rule_is_stated_in_the_asset(rule_id):
    """The table claiming an author is taught, while the asset says nothing, is worse than
    an honest gap: it reads as coverage."""
    assert rule_id in _ASSET.read_text(encoding="utf-8"), (
        f"rule {rule_id!r} is claimed as author-facing but does not appear in {_ASSET.name}"
    )


@pytest.mark.parametrize("proof", sorted(NOT_AUTHOR_FACING))
def test_derivation_owned_proofs_are_never_taught(proof):
    """The asymmetry M6 encodes: these findings belong to the deriver. Writing a rule for
    one would ask an author to adjust a document that is already correct, and would file
    our defect under their name."""
    assert proof not in _ASSET.read_text(encoding="utf-8")
    assert classify_finding(WinnabilityFinding(proof, "detail")).failure_class == DERIVATION_DEFECT


def test_the_two_modules_agree_on_who_owns_what():
    """M6 assigns ownership, this module assigns teaching. A proof owned by infrastructure
    that is nonetheless taught to authors is the contradiction that would produce a
    superstition — assert the tables cannot disagree."""
    for proof in AUTHOR_FACING:
        ownership = CLASS_OWNERSHIP[classify_finding(WinnabilityFinding(proof, "d")).failure_class]
        assert ownership != "infrastructure", (
            f"{proof} is taught to authors but M6 attributes it to infrastructure"
        )
