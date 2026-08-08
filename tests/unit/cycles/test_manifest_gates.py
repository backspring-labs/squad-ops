"""The winnability gate: can this manifest be won? (#781, M3)

Bug classes guarded:

- a gate that rejects the **known-good** manifest — worse than no gate, because it
  blocks the one design proven to work;
- a proof that fires on the wrong manifest, so a rejection points at the wrong fix;
- #772's shape — a collection POST with no ``success_status`` — reaching a cycle, where
  the derived contract asserts 201 against a scaffold emitting 200 and the probe fails
  on correct code (this cost a roll at pf-39 before the field existed);
- short-circuiting, which would make an author fix one defect per revision and exhaust
  ``manifest_max_attempts`` on a manifest that had several.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.cycles.manifest_gates import (
    PROOF_EXPANDS,
    PROOF_PARSES,
    PROOF_STATUS_DECLARED,
    PROOF_TESTID_COVERAGE,
    assess_winnability,
)

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _reference_dict() -> dict:
    return yaml.safe_load(_REFERENCE.read_text(encoding="utf-8"))


def _as_yaml(data: dict) -> str:
    return yaml.dump(data, sort_keys=False)


def _proofs(findings) -> set[str]:
    return {f.proof for f in findings}


def test_the_reference_manifest_is_winnable():
    """A gate that rejects the design the 1.4 evidence was measured against is wrong
    about the rule, not about the manifest."""
    assert assess_winnability(_REFERENCE.read_text(encoding="utf-8")) == ()


def test_unparseable_manifest_reports_only_the_parse_failure():
    """Nothing downstream can run without a parsed manifest, so piling on findings
    derived from a half-read document would misdirect the fix."""
    findings = assess_winnability("this: [is not: valid\n  yaml at all")

    assert _proofs(findings) == {PROOF_PARSES}


def test_collection_post_without_success_status_is_unwinnable():
    """#772's designed-failure probe.

    The deriver expects ``success_status or 201`` for a collection POST while the
    scaffold omits ``status_code=`` when undeclared, so FastAPI returns 200 — the
    contract asserts 201 against a correct implementation.
    """
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if ep["method"] == "POST" and "{" not in ep["path"]:
            ep.pop("success_status", None)

    findings = assess_winnability(_as_yaml(data))

    assert PROOF_STATUS_DECLARED in _proofs(findings)
    detail = next(f.detail for f in findings if f.proof == PROOF_STATUS_DECLARED)
    assert "201" in detail and "200" in detail  # names both sides of the disagreement
    assert "success_status" in detail  # names the fix


def test_child_post_without_success_status_is_fine():
    """Deliberately narrow: child actions default to 200 on BOTH sides and agree.

    Requiring the field everywhere would reject the reference manifest, which declares
    it on 1 of 5 endpoints.
    """
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if "{" in ep["path"]:
            ep.pop("success_status", None)

    assert PROOF_STATUS_DECLARED not in _proofs(assess_winnability(_as_yaml(data)))


def test_get_without_success_status_is_fine():
    """GETs derive no status probe, so there is nothing to disagree about."""
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if ep["method"] == "GET":
            ep.pop("success_status", None)

    assert PROOF_STATUS_DECLARED not in _proofs(assess_winnability(_as_yaml(data)))


def test_route_without_testids_is_unwinnable():
    """A view with no declared anchor leaves qa guessing at markup the dev may change."""
    data = _reference_dict()
    data["frontend"]["routes"][0].pop("testids", None)
    dropped = data["frontend"]["routes"][0]["path"]

    findings = assess_winnability(_as_yaml(data))

    assert PROOF_TESTID_COVERAGE in _proofs(findings)
    assert dropped in next(f.detail for f in findings if f.proof == PROOF_TESTID_COVERAGE)


def test_manifest_with_no_endpoints_or_routes_has_nothing_to_implement():
    """Every file frozen means the cycle would 'succeed' having produced nothing."""
    data = _reference_dict()
    data["api"]["endpoints"] = []
    data["frontend"]["routes"] = []

    findings = assess_winnability(_as_yaml(data))

    assert findings  # rejected on some proof
    assert PROOF_EXPANDS in _proofs(findings) or "lint" in _proofs(findings)


def test_all_proofs_run_so_one_revision_can_fix_everything():
    """No short-circuit: an author who sees one defect per attempt burns the revision
    budget on a manifest that had two."""
    data = _reference_dict()
    for ep in data["api"]["endpoints"]:
        if ep["method"] == "POST" and "{" not in ep["path"]:
            ep.pop("success_status", None)
    data["frontend"]["routes"][0].pop("testids", None)

    proofs = _proofs(assess_winnability(_as_yaml(data)))

    assert {PROOF_STATUS_DECLARED, PROOF_TESTID_COVERAGE} <= proofs


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(lambda d: d["api"].__setitem__("endpoints", []), id="no-endpoints"),
        pytest.param(lambda d: d.__setitem__("stack", "not_a_real_stack"), id="unknown-stack"),
    ],
)
def test_structurally_doomed_manifests_are_rejected(mutation):
    """The classes the SIP-0099 linter already names, reached through this gate."""
    data = _reference_dict()
    mutation(data)

    assert assess_winnability(_as_yaml(data)) != ()


# ---------------------------------------------------------------------------
# M2 — the schema gate: provenance and the decisions[] record (#783)
#
# Bug classes guarded: adding `decisions` to the model moving the manifest's
# structural hash, which would invalidate the contract bound to it and break every
# bind-mode cycle; a choice recorded with no citation back to the PRD, which is
# indistinguishable from an invention; an `unresolved` marker that defers a design
# question without saying which one; and a decision leaking into the derived contract,
# where it could become something a check depends on.
# ---------------------------------------------------------------------------

from squadops.capabilities.scaffold import InterfaceManifest  # noqa: E402
from squadops.cycles.manifest_gates import (  # noqa: E402
    PROOF_DECISION_RECORD,
    PROOF_SOURCE_PRD,
    assess_schema,
)

# The manifest hash contract v9 is bound to (`skeleton.interface_manifest_hash`).
_BOUND_MANIFEST_HASH = "bb472e267e53d5ad29406663b4340de45613dd68fa091fe7f2d06a99b7267530"


def test_reference_manifest_passes_the_schema_gate():
    assert assess_schema(_REFERENCE.read_text(encoding="utf-8")) == ()


def test_decisions_do_not_move_the_structural_hash():
    """The constraint that governs this whole item.

    `_canonical()` is "every field the expander reads, and nothing else" — provenance is
    excluded so a provenance-only edit cannot invalidate the contract bound to the hash.
    Decisions are judgment, not structure. If they entered the projection, contract v9's
    binding would break and every bind-mode cycle with it.
    """
    manifest = InterfaceManifest.from_yaml(_REFERENCE.read_text(encoding="utf-8"))

    assert manifest.decisions  # the field is populated, not silently empty
    assert manifest.content_hash() == _BOUND_MANIFEST_HASH


def test_revising_a_decision_never_invalidates_the_contract():
    """The consequence worth stating: an author may improve an explanation without
    re-deriving anything, because the design did not change."""
    data = _reference_dict()
    data["decisions"][0]["warrant"] = "§9.9 — a completely different citation"
    data["decisions"].append(
        {"id": "added-later", "choice": "something", "warrant": "§1.1 — anything"}
    )

    revised = InterfaceManifest.from_yaml(_as_yaml(data))

    assert revised.content_hash() == _BOUND_MANIFEST_HASH


def test_decisions_never_reach_the_derived_contract():
    """Lifecycle rule 3 holds *by construction*: since decisions are absent from the
    contract, no derived check can depend on an unresolved one. Pinned rather than
    re-checked — a detector for an impossible condition is the pattern this repo rejects.
    """
    from squadops.capabilities.scaffold_contract import emit_contract_yaml

    data = _reference_dict()
    data["decisions"].append(
        {"id": "open-question", "unresolved": True, "question": "should runs expire?"}
    )

    emitted = emit_contract_yaml(InterfaceManifest.from_yaml(_as_yaml(data)))

    assert "open-question" not in emitted
    assert "should runs expire" not in emitted


def test_unresolved_decision_round_trips_and_is_preserved():
    """Preserved, never consumed: approval does not silently drop the open question."""
    data = _reference_dict()
    data["decisions"].append(
        {"id": "pagination", "unresolved": True, "question": "page size for GET /runs?"}
    )

    manifest = InterfaceManifest.from_yaml(_as_yaml(data))

    (open_one,) = [d for d in manifest.decisions if d.unresolved]
    assert open_one.id == "pagination"
    assert open_one.question == "page size for GET /runs?"
    assert assess_schema(_as_yaml(data)) == ()


@pytest.mark.parametrize(
    ("entry", "expected_fragment"),
    [
        ({"id": "no-warrant", "choice": "did a thing"}, "warrant"),
        ({"id": "no-choice", "warrant": "§1.1"}, "choice"),
        ({"id": "silent-defer", "unresolved": True}, "question"),
        ({"choice": "x", "warrant": "§1.1"}, "id"),
    ],
)
def test_malformed_decision_records_are_rejected(entry, expected_fragment):
    data = _reference_dict()
    data["decisions"].append(entry)

    findings = assess_schema(_as_yaml(data))

    assert PROOF_DECISION_RECORD in _proofs(findings)
    assert any(expected_fragment in f.detail for f in findings)


def test_manifest_without_source_prd_is_rejected():
    """A design that does not say what it was designed from cannot be reviewed."""
    data = _reference_dict()
    data["source_prd"] = ""

    findings = assess_schema(_as_yaml(data))

    assert PROOF_SOURCE_PRD in _proofs(findings)
