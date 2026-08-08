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

from squadops.cycles.manifest_winnability import (
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
