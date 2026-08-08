"""The authoring failure taxonomy (#785, M6).

Bug classes guarded:

- a gate proof with **no** authoring class — the undifferentiated "manifest rejected"
  bucket this module exists to prevent, and the failure mode that would make the
  authored-mode window's numbers unactionable;
- a new proof added later without a class, which is how that bucket comes back;
- `prd_insufficiency` never being reported, because an unresolved decision *passes* both
  gates and a findings-only classifier would see nothing — leaving a PRD that
  under-specifies indistinguishable from a squad that cannot design;
- an open question being treated as a rejection, which would punish an author for
  correctly declaring ambiguity;
- ownership drifting from the vocabulary the check registry already uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.cycles import manifest_gates
from squadops.cycles.authoring_failure import (
    AUTHORING_DEFECT,
    CLASS_OWNERSHIP,
    DERIVATION_DEFECT,
    PRD_INSUFFICIENCY,
    AuthoringOutcome,
    ClassifiedFinding,
    assess_authoring_outcome,
    classify_finding,
)
from squadops.cycles.manifest_gates import WinnabilityFinding

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _reference_dict() -> dict:
    return yaml.safe_load(_REFERENCE.read_text(encoding="utf-8"))


def _as_yaml(data: dict) -> str:
    return yaml.dump(data, sort_keys=False)


def test_every_gate_proof_has_a_class():
    """The drift guard: a proof added to the gates without a class here silently
    re-creates the bucket. Enumerated from the gate module so it cannot be forgotten.
    """
    proofs = {
        value
        for name, value in vars(manifest_gates).items()
        if name.startswith("PROOF_") and isinstance(value, str)
    }
    assert proofs, "no proofs discovered — the enumeration itself broke"

    for proof in proofs:
        classified = classify_finding(WinnabilityFinding(proof, "detail"))
        assert classified.failure_class in CLASS_OWNERSHIP, f"{proof} has no authoring class"


def test_unknown_proof_is_filed_conservatively_rather_than_lost():
    """Losing a finding is worse than filing it under the author's column."""
    classified = classify_finding(WinnabilityFinding("a_proof_from_the_future", "detail"))

    assert classified.failure_class == AUTHORING_DEFECT


def test_derivation_failures_are_ours_not_the_authors():
    """Asking an author to work around a broken deriver teaches a superstition."""
    for proof in (manifest_gates.PROOF_CONTRACT_DERIVES, manifest_gates.PROOF_CHECKS_LIVE):
        classified = classify_finding(WinnabilityFinding(proof, "detail"))
        assert classified.failure_class == DERIVATION_DEFECT
        assert classified.ownership == "infrastructure"


def test_clean_manifest_reports_nothing():
    outcome = assess_authoring_outcome(_REFERENCE.read_text(encoding="utf-8"))

    assert outcome.rejected is False
    assert outcome.class_counts() == {}


def test_open_questions_are_counted_without_rejecting():
    """The distinction the class exists for.

    Declaring ambiguity is correct behavior, so the manifest passes — but the ambiguity
    must still be *counted*, or a PRD that under-specifies looks exactly like a squad
    that cannot design, and the two have opposite remedies.
    """
    data = _reference_dict()
    data["decisions"].append(
        {"id": "pagination", "unresolved": True, "question": "page size for GET /runs?"}
    )

    outcome = assess_authoring_outcome(_as_yaml(data))

    assert outcome.rejected is False
    assert outcome.open_questions == ("page size for GET /runs?",)
    assert outcome.class_counts() == {PRD_INSUFFICIENCY: 1}


def test_authoring_defect_is_attributed_to_the_author():
    """#772's shape, classified: the manifest is wrong and the author can fix it."""
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if ep["method"] == "POST" and "{" not in ep["path"]:
            ep.pop("success_status", None)

    outcome = assess_authoring_outcome(_as_yaml(data))

    assert outcome.rejected is True
    assert outcome.class_counts() == {AUTHORING_DEFECT: 1}
    assert outcome.findings[0].ownership == "plan"


def test_findings_and_open_questions_are_counted_together():
    """B1 accumulates this shape across cycles; both dimensions must survive."""
    data = _reference_dict()
    data["frontend"]["routes"][0].pop("testids", None)
    data["decisions"].append({"id": "q", "unresolved": True, "question": "unknown thing?"})

    counts = assess_authoring_outcome(_as_yaml(data)).class_counts()

    assert counts[AUTHORING_DEFECT] >= 1
    assert counts[PRD_INSUFFICIENCY] == 1


def test_unparseable_manifest_does_not_double_report():
    """The parse failure is already a finding; adding 'and it has no decisions' would
    misdirect the fix.

    #791: and it must be reported exactly ONCE. Both gates parse independently, so
    composing them naively gives the operator two identical rejection lines and gives B1's
    baseline ``authoring_defect: 2`` for a single defect — a counted class that inflates
    with every unparseable roll.
    """
    outcome = assess_authoring_outcome("not: [valid\n yaml")

    assert outcome.rejected is True
    assert outcome.open_questions == ()
    assert [f.proof for f in outcome.findings] == [manifest_gates.PROOF_PARSES]
    assert outcome.class_counts() == {AUTHORING_DEFECT: 1}


@pytest.mark.parametrize("failure_class", sorted(CLASS_OWNERSHIP))
def test_every_class_names_an_owner_from_the_shared_vocabulary(failure_class):
    """Ownership is borrowed from the check registry, not restated — two answers to
    'whose problem is it?' is the drift this codebase keeps paying for."""
    from squadops.cycles import acceptance_check_spec as spec

    known = {
        value
        for name, value in vars(spec).items()
        if name.startswith("OWNERSHIP_") and isinstance(value, str)
    }
    assert CLASS_OWNERSHIP[failure_class] in known


def test_outcome_is_empty_by_default():
    """A default-constructed outcome must read as 'nothing wrong', not as unknown."""
    assert AuthoringOutcome().rejected is False
    assert AuthoringOutcome().class_counts() == {}


def test_classified_finding_preserves_the_operator_facing_detail():
    """The class is for machines; the detail is what a person acts on. Losing it would
    trade a readable rejection for a label."""
    classified = classify_finding(WinnabilityFinding("lint", "declare at least one endpoint"))

    assert isinstance(classified, ClassifiedFinding)
    assert classified.detail == "declare at least one endpoint"
