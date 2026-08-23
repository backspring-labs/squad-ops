"""Which manifest gate proofs are author-facing, and where each one is taught (#791, M1).

The #686 pattern, applied one level up. Plan authoring learned it the expensive way: the
validators knew the rules and the authors were shown only the rejections, so shk-1 spent a
framing re-roll rediscovering a rule the system already held. Manifest authoring starts
with the binding in place instead of acquiring it after the first loss — the gates
(:mod:`squadops.cycles.manifest_gates`) landed before the authoring stage precisely so this
table could exist before the first authored manifest was rejected.

This module is the CLASSIFICATION, which is data. The rule prose lives in the managed asset
``request.manifest_authoring_rules_appendix`` (#448: prose in assets, Python renders data
only). ``tests/unit/cycles/test_manifest_authoring_rules.py`` binds the two: every
``PROOF_*`` in the gate module must appear in exactly one table here, and every rule id in
``AUTHOR_FACING`` must appear in the asset. A proof added to the gates therefore cannot ship
without a decision about whether authors are told.

The split is not cosmetic — it tracks M6's ownership. A proof classified
``DERIVATION_DEFECT`` there must be absent from the asset here: teaching an author to work
around a broken deriver is teaching a superstition, and it would move a defect that is ours
onto their side of the ledger.
"""

from __future__ import annotations

from squadops.cycles.manifest_gates import (
    PROOF_CHECKS_LIVE,
    PROOF_CONTRACT_DERIVES,
    PROOF_DECISION_RECORD,
    PROOF_ERROR_SHAPE,
    PROOF_EXPANDS,
    PROOF_LINT,
    PROOF_PARSES,
    PROOF_SCAFFOLD_READY,
    PROOF_SOURCE_PRD,
    PROOF_STACK_MATCHES_CONFIG,
    PROOF_STATUS_DECLARED,
    PROOF_STATUS_WARRANTED,
    PROOF_TESTID_COVERAGE,
)

# Proofs whose rule is stated in the authoring-rules asset. The value is the rule id (or
# ids) the asset carries, so the binding is checkable rather than a naming convention. A
# proof maps to more than one id where it reports genuinely distinct defects — the lint
# family is one proof and two rules, and collapsing them would leave one rule untaught
# while the table claimed coverage.
AUTHOR_FACING: dict[str, tuple[str, ...]] = {
    PROOF_LINT: ("nothing-undeclared", "declare-something-to-build"),
    PROOF_EXPANDS: ("paths-under-scaffold-roots",),
    PROOF_TESTID_COVERAGE: ("every-view-declares-anchors",),
    PROOF_STATUS_DECLARED: ("declare-the-success-status",),
    # #1067: the sibling of the rule above, and the one that removes the recurrence
    # rather than gating it. The status is authored in three places and derivable in
    # one; teaching the author to override it deliberately — or not at all — is what
    # collapses the copies.
    PROOF_STATUS_WARRANTED: ("warrant-a-status-that-breaks-convention",),
    # #795: the envelope is blueprint-owned; a declared shape rooted anywhere but
    # `error` describes a body no response will carry (V4 declared FastAPI's default).
    PROOF_ERROR_SHAPE: ("error-shape-is-the-blueprints",),
    PROOF_SOURCE_PRD: ("name-the-source-prd",),
    PROOF_DECISION_RECORD: ("record-judgments-with-warrants",),
    # #838: AUTHOR_FACING rather than COVERED_ELSEWHERE, though the authoring request's
    # schema block does render `stack: {{stack}}`. VS falsified the idea that rendering
    # it is teaching it: the author saw that line and wrote another stack's name anyway,
    # having inherited it from a technical design that named the other one eight times.
    # Filing it as already-covered would assert a teaching that has been measured failing.
    PROOF_STACK_MATCHES_CONFIG: ("use-the-stack-you-were-given",),
}

# Proofs an author is already taught by a different managed asset. Restating them would put
# the same rule in two places, free to drift; the value names the owning asset.
COVERED_ELSEWHERE: dict[str, str] = {
    # The schema block in the authoring request IS the teaching, and it is strictly more
    # useful than a prose restatement — an author reading a worked instance of the exact
    # shape cannot be told "emit valid YAML of the right kind" more precisely.
    PROOF_PARSES: "request.development_author_manifest",
}

# Proofs with no author-facing rule: nothing the author writes can trip them.
NOT_AUTHOR_FACING: dict[str, str] = {
    # M6 classifies both as DERIVATION_DEFECT: the manifest passed lint and expansion, so
    # a contract that fails to derive — or derives a check that can never execute — is the
    # deriver's problem by elimination. An author told to avoid it would be adjusting a
    # document that is already correct.
    PROOF_CONTRACT_DERIVES: "derivation-owned (M6 DERIVATION_DEFECT): the fix is in the "
    "deriver, never in the manifest",
    PROOF_CHECKS_LIVE: "derivation-owned (M6 DERIVATION_DEFECT): a dead-on-arrival check "
    "is emitted by the deriver, not authored",
    # SIP-0104 P2: an opted-in stack whose test scaffold cannot be validly emitted.
    # The generator's defect by elimination (the manifest already expanded and derived
    # a contract); teaching the author anything here would teach a superstition.
    PROOF_SCAFFOLD_READY: "derivation-owned (M6 DERIVATION_DEFECT): the fix is in the "
    "scaffold generator or its readiness gate (SIP-0104), never in the manifest",
}


def rule_ids() -> frozenset[str]:
    """Rule ids the authoring-rules asset must carry."""
    return frozenset(rid for ids in AUTHOR_FACING.values() for rid in ids)


def classified_proofs() -> frozenset[str]:
    """Every proof this module has an opinion about."""
    return frozenset(AUTHOR_FACING) | frozenset(COVERED_ELSEWHERE) | frozenset(NOT_AUTHOR_FACING)
