"""Tests for verification-contract emission (SIP-0098 phase 98.2).

The load-bearing test is the 98.1 ↔ 98.2 interlock: the contract the expander emits
must lint clean against the cycles-domain schema/linter — an emitter that produced a
malformed or class-confused contract would be caught here, not in a cycle. The rest
pin the derivation (frozen covers every non-fill file by real hash; each slot carries
its interface + implementation criteria; the skeleton is bound by manifest hash) and
determinism (same manifest → same contract → same frozen hash).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from squadops.capabilities.scaffold import InterfaceManifest, expand, fill_slot_paths
from squadops.capabilities.scaffold_contract import emit_contract_dict, emit_contract_yaml
from squadops.cycles.verification_contract import VerificationContract

pytestmark = [pytest.mark.domain_capabilities]

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


def _manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _raw() -> dict:
    return yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# The interlock: emitted contract must lint clean (98.1's linter)
# --------------------------------------------------------------------------- #


def test_emitted_group_run_contract_lints_clean():
    contract = VerificationContract.from_dict(emit_contract_dict(_manifest()))
    assert contract.lint() == []


def test_emitted_yaml_roundtrips_and_lints_clean():
    # the actual artifact path: YAML text -> loader -> lint
    text = emit_contract_yaml(_manifest())
    assert text.startswith("# Verification contract")
    contract = VerificationContract.from_yaml(text)
    assert contract.lint() == []


def test_contract_without_error_contract_omits_apierror_and_lints_clean():
    # the ApiError seam is emitted only when the manifest declares an error contract
    def apierror_ids(contract: dict) -> list[str]:
        return [
            c["id"]
            for c in contract["fill_files"]["backend/routes.py"]["interface"]
            if c["id"] == "vc-routes-apierror"
        ]

    assert apierror_ids(emit_contract_dict(_manifest())) == ["vc-routes-apierror"]

    raw = _raw()
    raw["api"].pop("error_contract", None)
    without_ec = emit_contract_dict(InterfaceManifest.from_dict(raw))
    assert apierror_ids(without_ec) == []
    assert VerificationContract.from_dict(without_ec).lint() == []


# --------------------------------------------------------------------------- #
# Derivation
# --------------------------------------------------------------------------- #


def test_skeleton_bound_by_interface_manifest_hash():
    manifest = _manifest()
    contract = emit_contract_dict(manifest)
    assert contract["skeleton"]["expander"] == manifest.stack
    assert contract["skeleton"]["interface_manifest_hash"] == manifest.content_hash()


def test_frozen_covers_every_non_fill_file_by_real_hash():
    manifest = _manifest()
    files = {f["name"]: f["content"] for f in expand(manifest)}
    fill = set(fill_slot_paths(manifest))

    contract = emit_contract_dict(manifest)
    frozen = {entry["path"]: entry["sha256"] for entry in contract["frozen"]}

    assert set(frozen) == set(files) - fill  # every non-fill file, nothing else
    assert "backend/routes.py" not in frozen  # a fill slot is never frozen
    # hashes are of the actual expanded content (drift in a frozen file is detectable)
    for path, digest in frozen.items():
        assert digest == _sha256(files[path])


def test_fill_slots_carry_interface_and_implementation_criteria():
    contract = emit_contract_dict(_manifest())
    routes = contract["fill_files"]["backend/routes.py"]

    endpoints = next(c for c in routes["interface"] if c["check"] == "endpoint_defined")
    assert endpoints["methods_paths"] == [
        "GET /runs",
        "POST /runs",
        "GET /runs/{id}",
        "POST /runs/{id}/join",
        "POST /runs/{id}/leave",
    ]
    assert any(c["id"] == "vc-routes-apierror" for c in routes["interface"])
    compiles = next(c for c in routes["implementation"] if c["check"] == "command_exit_zero")
    assert compiles["argv"] == ["python", "-m", "py_compile", "backend/routes.py"]
    assert compiles["requires"] == "python"

    # views carry NO per-file criteria in v1: node --check can't parse JSX and the
    # import_present evaluator skips .jsx — view compilation is verified by frontend_build
    detail = contract["fill_files"]["frontend/src/views/RunDetailView.jsx"]
    assert detail["interface"] == []
    assert detail["implementation"] == []


def test_behavioral_has_build_suite_and_self_contained_probe():
    contract = emit_contract_dict(_manifest())
    behavioral = contract["behavioral"]

    assert behavioral["build"][0]["check"] == "frontend_build"
    assert behavioral["suite"]["checks"][0]["check"] == "tests_pass"
    assert any("happy path" in exp for exp in behavioral["suite"]["coverage_expectations"])

    # one self-contained probe (POST /runs); path-param endpoints defer to 98.4
    probe_paths = {p["request"]["path"] for p in behavioral["probes"]}
    assert probe_paths == {"/runs"}
    create = behavioral["probes"][0]
    assert create["request"]["method"] == "POST"
    assert set(create["request"]["json"]) == {"title", "datetime", "location"}
    assert create["expect"]["status"] == 200


def test_capabilities_derived_from_what_criteria_require():
    contract = emit_contract_dict(_manifest())
    assert contract["capabilities"] == ["python", "node"]


def test_emission_is_deterministic():
    a = emit_contract_dict(_manifest())
    b = emit_contract_dict(_manifest())
    assert a == b
    # and the frozen hash the yield baseline measures against is stable
    assert (
        VerificationContract.from_dict(a).content_hash()
        == VerificationContract.from_dict(b).content_hash()
    )
