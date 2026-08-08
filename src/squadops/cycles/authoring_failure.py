"""Why did this manifest fail — and whose problem is it? (#785, M6)

One classification, three consumers: M5's provenance records *why* each revision
happened, B1's baseline counts *which classes recur*, and the authored-mode measurement
window needs *which subsystem* a failure is attributable to. Built three times, those
become three vocabularies that must later be reconciled — the exact problem the post-1.5
reconciliation names as intention 2.

It exists before the first authored manifest is rejected, because **a rejection recorded
without a class is data that cannot be recovered later**. Without it the window's output
collapses into one "manifest rejected" bucket, which cannot say whether authored mode is
limited by the author, the schema, the blueprint, or the deriver — the entire question
the release is asking.

Keyed alongside the vocabulary that already exists (``FailureEvidenceCategory``,
``OWNERSHIP_*``, locus classification) rather than as a parallel set: this adds the
*authoring* dimension those lack, and borrows their ownership semantics rather than
inventing a second answer to "whose problem is it?".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from squadops.cycles.acceptance_check_spec import (
    OWNERSHIP_CONTRACT,
    OWNERSHIP_INFRASTRUCTURE,
    OWNERSHIP_PLAN,
)
from squadops.cycles.manifest_gates import (
    PROOF_CHECKS_LIVE,
    PROOF_CONTRACT_DERIVES,
    PROOF_DECISION_RECORD,
    PROOF_EXPANDS,
    PROOF_LINT,
    PROOF_PARSES,
    PROOF_PROVENANCE,
    PROOF_STATUS_DECLARED,
    PROOF_TESTID_COVERAGE,
    WinnabilityFinding,
    assess_schema,
    assess_winnability,
)

#: The manifest is wrong; schema, blueprint and deriver are all fine. Retrying the
#: authoring stage with rejection context is the right response.
AUTHORING_DEFECT = "authoring_defect"

#: The manifest could not express something the design needs. Fixing it means changing
#: the schema, which is a blueprint-version change (SIP-0103 §5c.4) — never silent drift.
SCHEMA_GAP = "schema_gap"

#: The stack's closed vocabulary cannot express the design. Adjudicated by the blueprint
#: admission rule (S5: a new field must be demonstrated on ≥2 stacks).
BLUEPRINT_LIMITATION = "blueprint_limitation"

#: Authoring was sound; the deriver mishandled it. The fix is in M0's code, never in the
#: manifest — asking an author to work around a broken deriver teaches them a superstition.
DERIVATION_DEFECT = "derivation_defect"

#: The PRD does not determine the answer. Handled by ``decisions[]`` with
#: ``unresolved: true`` and the human review gate — NOT by asking the author to guess.
PRD_INSUFFICIENCY = "prd_insufficiency"

#: Ownership, borrowed from the check registry's vocabulary rather than restated. The
#: author owns their own document; a schema or blueprint gap is a contract-level
#: concern; a deriver defect is ours, in the same sense infrastructure failures are.
CLASS_OWNERSHIP: dict[str, str] = {
    AUTHORING_DEFECT: OWNERSHIP_PLAN,
    SCHEMA_GAP: OWNERSHIP_CONTRACT,
    BLUEPRINT_LIMITATION: OWNERSHIP_CONTRACT,
    DERIVATION_DEFECT: OWNERSHIP_INFRASTRUCTURE,
    PRD_INSUFFICIENCY: OWNERSHIP_PLAN,
}

# How each gate proof classifies at a SINGLE occurrence.
#
# Read the conservative entries with the recurrence rule in mind (see
# `classify_finding`): `expands` and `checks_live` are ambiguous in one sighting and
# resolve only across cycles.
_PROOF_CLASS: dict[str, str] = {
    PROOF_PARSES: AUTHORING_DEFECT,
    PROOF_LINT: AUTHORING_DEFECT,
    PROOF_PROVENANCE: AUTHORING_DEFECT,
    PROOF_DECISION_RECORD: AUTHORING_DEFECT,
    PROOF_TESTID_COVERAGE: AUTHORING_DEFECT,
    PROOF_STATUS_DECLARED: AUTHORING_DEFECT,
    PROOF_EXPANDS: AUTHORING_DEFECT,
    # Derivation succeeded structurally but produced something unusable, on a manifest
    # that already passed lint and expansion. That is the deriver's problem by
    # elimination, not the author's.
    PROOF_CONTRACT_DERIVES: DERIVATION_DEFECT,
    PROOF_CHECKS_LIVE: DERIVATION_DEFECT,
}


@dataclass(frozen=True)
class ClassifiedFinding:
    """A gate finding with its authoring class and the owner who can act on it."""

    proof: str
    detail: str
    failure_class: str
    ownership: str


@dataclass(frozen=True)
class AuthoringOutcome:
    """What a manifest's gates say, classified for the three downstream consumers."""

    findings: tuple[ClassifiedFinding, ...] = ()
    #: Declared open questions. NOT failures — see :func:`assess_authoring_outcome`.
    open_questions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def rejected(self) -> bool:
        """True when a gate found something that must be fixed before proceeding."""
        return bool(self.findings)

    def class_counts(self) -> dict[str, int]:
        """Occurrences per class — the shape B1's baseline accumulates across cycles."""
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.failure_class] = counts.get(f.failure_class, 0) + 1
        if self.open_questions:
            counts[PRD_INSUFFICIENCY] = len(self.open_questions)
        return counts


def classify_finding(finding: WinnabilityFinding) -> ClassifiedFinding:
    """Classify one gate finding, conservatively.

    **Some classes are recurrence-determined, and single-occurrence precision here would
    be faked.** "The expander refused this design" is genuinely ambiguous between *the
    author asked for something outside the vocabulary* (``AUTHORING_DEFECT``) and *the
    vocabulary should support it* (``BLUEPRINT_LIMITATION``); nothing available at the
    gate distinguishes them.

    So a single occurrence takes the conservative class — the author's — and
    **recurrence is what promotes it**. That promotion is measured across cycles by B1's
    baseline, not inside one assessment, which is precisely why B1 records recurrence
    rather than only totals. Same ratchet as M2's judgment surface: a class that keeps
    reappearing is evidence of a gap rather than a run of bad luck.

    Unknown proofs classify as ``AUTHORING_DEFECT`` rather than raising: an unclassified
    finding is the undifferentiated bucket this module exists to prevent, and losing the
    finding entirely would be worse than filing it conservatively.
    """
    failure_class = _PROOF_CLASS.get(finding.proof, AUTHORING_DEFECT)
    return ClassifiedFinding(
        proof=finding.proof,
        detail=finding.detail,
        failure_class=failure_class,
        ownership=CLASS_OWNERSHIP[failure_class],
    )


def assess_authoring_outcome(manifest_content: str) -> AuthoringOutcome:
    """Run both gates and classify everything they say about this manifest.

    Also reads the manifest's **declared uncertainty**. An ``unresolved`` decision
    *passes* the schema gate by design — stating an open question is correct behavior,
    not a defect — so a classifier that looked only at findings would report zero PRD
    insufficiency on a manifest whose author explicitly said the requirements were
    ambiguous. Those are recorded as ``open_questions`` and counted under
    ``PRD_INSUFFICIENCY`` without rejecting the manifest.

    That distinction is the point of the class: a PRD that under-specifies must not look
    identical to a squad that cannot design, because the remedies are opposite — one
    needs a better PRD, the other a better author.
    """
    schema = assess_schema(manifest_content)
    if any(f.proof == PROOF_PARSES for f in schema):
        # Both gates parse independently and both report the failure, so composing them
        # naively double-reports it: two identical rejection lines in the operator's note,
        # and ``authoring_defect: 2`` in a baseline counting one defect (#791 found this by
        # wiring the gates to the framing rejection). Nothing downstream can run without a
        # parsed manifest, so the parse failure returns alone.
        return AuthoringOutcome(findings=tuple(classify_finding(f) for f in schema))

    findings = tuple(classify_finding(f) for f in (*schema, *assess_winnability(manifest_content)))
    return AuthoringOutcome(findings=findings, open_questions=_open_questions(manifest_content))


def _open_questions(manifest_content: str) -> tuple[str, ...]:
    """Questions the author declined to answer, in their own words.

    An unparseable manifest has no readable decisions; the parse failure is already a
    finding, so this stays silent rather than adding a second complaint about it.
    """
    from squadops.capabilities.scaffold import InterfaceManifest

    try:
        manifest = InterfaceManifest.from_yaml(manifest_content)
    except Exception:  # noqa: BLE001 - the parse failure is reported as a finding
        return ()
    return tuple(d.question for d in manifest.decisions if d.unresolved and d.question.strip())
