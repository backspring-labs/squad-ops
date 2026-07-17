"""Tests for the contract runner (SIP-0098 §6.2 structural evaluation bridge).

The gate's three CI jobs are the end-to-end proof; these guard the reusable pieces the
gate and its tests share: which criteria are structural (evaluator-backed) vs behavioral
(subprocess), that every structural criterion PASSES on the bare skeleton (the refined
§6.2 model — a walking skeleton compiles/builds, so only tests_pass/probes fail on it),
and that the file target is injected from the fill-slot key.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from squadops.capabilities.scaffold import InterfaceManifest, expand
from squadops.capabilities.scaffold_contract import emit_contract_dict
from squadops.cycles.verification_contract import VerificationContract
from squadops.cycles.verification_contract_runner import (
    FILL_BEHAVIOR_MEASURES,
    evaluate_structural,
    is_structural,
    structural_criteria,
)

pytestmark = [pytest.mark.domain_capabilities]

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)
_REFERENCE_FILL = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "reference_fills"
    / "fullstack_fastapi_react"
    / "group_run"
)


def _materialize(dest: Path) -> InterfaceManifest:
    manifest = InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))
    for f in expand(manifest):
        out = dest / f["name"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f["content"], encoding="utf-8")
    return manifest


def _contract() -> VerificationContract:
    manifest = InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))
    return VerificationContract.from_dict(emit_contract_dict(manifest))


def test_structural_criteria_selects_only_evaluator_backed_checks():
    checks = {c["check"] for c, _ in structural_criteria(_contract())}
    assert checks == {"endpoint_defined", "import_present", "command_exit_zero"}
    # behavioral checks are the gate's subprocess job, never structural
    assert "tests_pass" not in checks
    assert "frontend_build" not in checks


def test_fill_behavior_measures_is_tests_pass_only():
    # only behavior-exercising checks fail on the bare skeleton; frontend_build is a
    # regression guard that PASSES on the walking skeleton, so it is NOT listed
    assert FILL_BEHAVIOR_MEASURES == {"tests_pass"}
    assert not is_structural("tests_pass")
    assert not is_structural("frontend_build")


def test_every_structural_criterion_passes_on_bare_skeleton(tmp_path):
    # the §6.2 refinement: interface (endpoint_defined, import_present ApiError) AND the
    # compile guard (py_compile) all pass on the freshly expanded stub skeleton
    _materialize(tmp_path)
    contract = _contract()
    for criterion, fill_file in structural_criteria(contract):
        outcome = evaluate_structural(criterion, tmp_path, fill_file=fill_file)
        assert outcome.status == "passed", (
            f"{criterion['id']} -> {outcome.status} ({outcome.reason})"
        )


def test_structural_criteria_still_pass_with_reference_fill(tmp_path):
    _materialize(tmp_path)
    for src in _REFERENCE_FILL.rglob("*"):
        if src.is_file():
            out = tmp_path / src.relative_to(_REFERENCE_FILL)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
    for criterion, fill_file in structural_criteria(_contract()):
        outcome = evaluate_structural(criterion, tmp_path, fill_file=fill_file)
        assert outcome.status == "passed"


def test_endpoint_defined_fails_when_routes_file_missing(tmp_path):
    # edge: no skeleton materialized -> the interface check FAILS (not error), so a fill
    # that deleted the routes file would be caught
    criterion = {
        "check": "endpoint_defined",
        "id": "vc-routes-endpoints",
        "methods_paths": ["GET /runs", "POST /runs"],
    }
    outcome = evaluate_structural(criterion, tmp_path, fill_file="backend/routes.py")
    assert outcome.status == "failed"
    assert outcome.reason == "file_not_found"


def test_evaluate_structural_rejects_behavioral_check(tmp_path):
    with pytest.raises(ValueError, match="not a structural check"):
        evaluate_structural({"check": "tests_pass", "id": "vc-suite-passes"}, tmp_path)
