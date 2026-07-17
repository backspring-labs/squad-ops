"""Tests for the verification-contract schema, loader, and linter (SIP-0098 phase 98.1).

The linter is the emission-time "verify the verifier" gate (§6.2 job 1): a contract
that lints clean cannot carry the schema-level defect classes from §2's criteria
lottery — env mismatches, uncompilable/style regexes on source, off-safelist
commands, class-confused checks, colliding ids, an unbound skeleton. Each rejection
test names the exact §2 bug it would have caught. Loader tests pin the parsed shape
and hash stability (the frozen hash the yield baseline measures against).
"""

from __future__ import annotations

import pytest
import yaml

from squadops.cycles.verification_contract import (
    KNOWN_CAPABILITIES,
    VerificationContract,
)

pytestmark = [pytest.mark.domain_capabilities]

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64


def _valid_contract_dict() -> dict:
    """A well-formed group_run contract — mirrors the group_run skeleton (§6.1).

    Kept as a builder so each rejection test can deep-copy and inject exactly one
    defect, proving the linter rejects that defect *and* that the base is clean."""
    return {
        "contract_version": 1,
        "skeleton": {
            "expander": "fullstack_fastapi_react",
            "interface_manifest_hash": _HASH_A,
        },
        "capabilities": ["python", "node"],
        "frozen": [
            {"path": "backend/errors.py", "sha256": _HASH_B},
            {"path": "frontend/src/api.js", "sha256": _HASH_C},
        ],
        "fill_files": {
            "backend/routes.py": {
                "interface": [
                    {
                        "check": "endpoint_defined",
                        "id": "vc-routes-endpoints",
                        "methods_paths": [
                            "GET /runs",
                            "POST /runs",
                            "GET /runs/{id}",
                            "POST /runs/{id}/join",
                            "POST /runs/{id}/leave",
                        ],
                    },
                    {
                        "check": "import_present",
                        "id": "vc-routes-apierror",
                        "module": ".errors",
                        "symbol": "ApiError",
                    },
                ],
                "implementation": [
                    {
                        "check": "command_exit_zero",
                        "id": "vc-routes-compiles",
                        "argv": ["python", "-m", "py_compile", "backend/routes.py"],
                        "requires": "python",
                    },
                ],
            },
            "frontend/src/views/RunDetailView.jsx": {
                "interface": [
                    {
                        "check": "import_present",
                        "id": "vc-detail-apifetch",
                        "module": "../api",
                        "symbol": "apiFetch",
                    },
                ],
                "implementation": [
                    {
                        "check": "command_exit_zero",
                        "id": "vc-detail-parses",
                        "argv": ["node", "--check", "frontend/src/views/RunDetailView.jsx"],
                        "requires": "node",
                    },
                ],
            },
        },
        "behavioral": {
            "build": [
                {"check": "frontend_build", "id": "vc-frontend-builds", "requires": "node"},
            ],
            "suite": {
                "checks": [
                    {"check": "tests_pass", "id": "vc-suite-passes", "requires": "python"},
                ],
                "coverage_expectations": [
                    "create/list/get/join/leave happy paths",
                    "duplicate join -> 409, unknown run/participant -> 404",
                ],
            },
            "probes": [
                {
                    "id": "vc-probe-create",
                    "subject": "backend",
                    "request": {
                        "method": "POST",
                        "path": "/runs",
                        "json": {"title": "T", "datetime": "D", "location": "L"},
                    },
                    "expect": {"status": 200, "json_has": ["id", "participants"]},
                },
                {
                    "id": "vc-probe-dup-join",
                    "subject": "backend",
                    "request": {"method": "POST", "path": "/runs/x/join", "json": {"name": "A"}},
                    "expect": {"status": 409, "error_code": "duplicate_participant"},
                },
            ],
        },
    }


def _lint(mutate=None) -> list[str]:
    data = _valid_contract_dict()
    if mutate is not None:
        mutate(data)
    return VerificationContract.from_dict(data).lint()


# --------------------------------------------------------------------------- #
# Loader + identity
# --------------------------------------------------------------------------- #


def test_from_yaml_parses_structure_and_binds_skeleton():
    contract = VerificationContract.from_yaml(yaml.safe_dump(_valid_contract_dict()))

    assert contract.contract_version == 1
    assert contract.skeleton.expander == "fullstack_fastapi_react"
    assert contract.skeleton.interface_manifest_hash == _HASH_A
    assert contract.capabilities == ("python", "node")
    assert [f.path for f in contract.frozen_files] == ["backend/errors.py", "frontend/src/api.js"]
    assert [ff.path for ff in contract.fill_files] == [
        "backend/routes.py",
        "frontend/src/views/RunDetailView.jsx",
    ]

    routes = next(ff for ff in contract.fill_files if ff.path == "backend/routes.py")
    endpoints = routes.interface[0]
    assert endpoints.check == "endpoint_defined"
    # the file target is the fill_files key, NOT an inline param (contract vs plan check)
    assert "file" not in endpoints.params
    assert endpoints.params["methods_paths"][0] == "GET /runs"
    assert routes.implementation[0].requires == "python"

    assert [c.id for c in contract.behavioral.build] == ["vc-frontend-builds"]
    assert contract.behavioral.suite.checks[0].check == "tests_pass"
    assert contract.behavioral.suite.coverage_expectations[0].startswith("create/list")
    assert [p.id for p in contract.behavioral.probes] == ["vc-probe-create", "vc-probe-dup-join"]
    assert contract.behavioral.probes[1].expect["error_code"] == "duplicate_participant"


def test_content_hash_stable_and_order_independent():
    data = _valid_contract_dict()
    reordered = {k: data[k] for k in reversed(list(data))}  # same content, keys reversed
    h1 = VerificationContract.from_dict(data).content_hash()
    h2 = VerificationContract.from_dict(reordered).content_hash()
    assert h1 == h2  # hash follows content, not source key order (the frozen-hash guarantee)
    assert len(h1) == 64

    # a real content change moves the hash (so drift is detectable, not masked)
    changed = _valid_contract_dict()
    changed["skeleton"]["interface_manifest_hash"] = _HASH_B
    assert VerificationContract.from_dict(changed).content_hash() != h1


def test_criterion_ids_span_every_section():
    contract = VerificationContract.from_dict(_valid_contract_dict())
    assert set(contract.criterion_ids()) == {
        "vc-routes-endpoints",
        "vc-routes-apierror",
        "vc-routes-compiles",
        "vc-detail-apifetch",
        "vc-detail-parses",
        "vc-frontend-builds",
        "vc-suite-passes",
        "vc-probe-create",
        "vc-probe-dup-join",
    }


def test_from_yaml_rejects_malformed_yaml():
    with pytest.raises(ValueError, match="not valid YAML"):
        VerificationContract.from_yaml("contract_version: 1\n  bad: : indent")


def test_from_yaml_rejects_non_mapping_root():
    with pytest.raises(ValueError, match="must be a mapping"):
        VerificationContract.from_yaml("- just\n- a\n- list")


def test_from_dict_rejects_structurally_wrong_sections():
    for bad in ({"fill_files": []}, {"capabilities": "python,node"}, {"frozen": {}}):
        data = _valid_contract_dict()
        data.update(bad)
        with pytest.raises(ValueError):
            VerificationContract.from_dict(data)


# --------------------------------------------------------------------------- #
# The clean base lints clean — otherwise every rejection test is vacuous
# --------------------------------------------------------------------------- #


def test_valid_contract_lints_clean():
    assert VerificationContract.from_dict(_valid_contract_dict()).lint() == []


# --------------------------------------------------------------------------- #
# One rejection test per lint rule (each names the §2 bug it catches)
# --------------------------------------------------------------------------- #


def test_lint_rejects_wrong_contract_version():
    errors = _lint(lambda d: d.__setitem__("contract_version", 2))
    assert any("contract_version" in e for e in errors)


def test_lint_rejects_missing_interface_manifest_hash():
    # P3/drift: an unbound contract could verify a different skeleton than it describes.
    errors = _lint(lambda d: d["skeleton"].__setitem__("interface_manifest_hash", ""))
    assert any("interface_manifest_hash is required" in e for e in errors)


def test_lint_rejects_non_sha256_manifest_hash():
    errors = _lint(lambda d: d["skeleton"].__setitem__("interface_manifest_hash", "deadbeef"))
    assert any("64-char sha256" in e for e in errors)


def test_lint_rejects_duplicate_ids():
    # 3.x: "same check failed in two rolls" is only knowable if ids are unique.
    def dupe(d):
        d["fill_files"]["backend/routes.py"]["interface"][1]["id"] = "vc-routes-endpoints"

    errors = _lint(dupe)
    assert any("duplicate criterion id 'vc-routes-endpoints'" in e for e in errors)


def test_lint_rejects_missing_id():
    def drop_id(d):
        del d["fill_files"]["backend/routes.py"]["interface"][0]["id"]

    errors = _lint(drop_id)
    assert any("missing a stable id" in e for e in errors)


def test_lint_rejects_unknown_declared_capability():
    errors = _lint(lambda d: d["capabilities"].append("rust"))
    assert any("unknown capability 'rust'" in e for e in errors)


def test_lint_rejects_requires_not_in_known_capabilities():
    # #462: Node-on-dev style env mismatch — a check requiring a tool that isn't a
    # known capability is exactly the 3.9 failure, caught before dispatch.
    def bad_requires(d):
        d["fill_files"]["backend/routes.py"]["implementation"][0]["requires"] = "deno"

    errors = _lint(bad_requires)
    assert any("requires unknown capability 'deno'" in e for e in errors)


def test_lint_rejects_requires_not_declared_in_capabilities():
    errors = _lint(lambda d: d["capabilities"].remove("node"))
    assert any("not declared in the top-level capabilities" in e for e in errors)


def test_lint_rejects_frozen_traversal_path_and_bad_hash():
    def bad_frozen(d):
        d["frozen"][0]["path"] = "../etc/passwd"
        d["frozen"][1]["sha256"] = "nothex"

    errors = _lint(bad_frozen)
    assert any("traversal" in e for e in errors)
    assert any("frozen[frontend/src/api.js]: sha256" in e for e in errors)


def test_lint_rejects_unknown_check_name():
    def unknown(d):
        d["fill_files"]["backend/routes.py"]["interface"][0]["check"] = "vibes_present"

    errors = _lint(unknown)
    assert any("unknown check 'vibes_present'" in e for e in errors)


def test_lint_rejects_check_in_wrong_class():
    # command_exit_zero measures the fill — it is an implementation check, never
    # an interface one; placing it in interface confuses the bare-skeleton gate.
    def misclass(d):
        d["fill_files"]["backend/routes.py"]["interface"].append(
            {
                "check": "command_exit_zero",
                "id": "vc-x",
                "argv": ["python", "-m", "py_compile", "backend/routes.py"],
                "requires": "python",
            }
        )

    errors = _lint(misclass)
    assert any("not allowed in the interface class" in e for e in errors)


def test_lint_rejects_missing_required_param():
    def drop_param(d):
        del d["fill_files"]["backend/routes.py"]["interface"][0]["methods_paths"]

    errors = _lint(drop_param)
    assert any("missing required param(s): methods_paths" in e for e in errors)


def test_lint_rejects_unknown_param():
    def extra(d):
        d["fill_files"]["backend/routes.py"]["interface"][1]["nonsense"] = "x"

    errors = _lint(extra)
    assert any("unknown param(s): nonsense" in e for e in errors)


def test_lint_rejects_wrong_param_type():
    def wrong_type(d):
        d["fill_files"]["backend/routes.py"]["interface"][0]["methods_paths"] = "GET /runs"

    errors = _lint(wrong_type)
    assert any("must be list" in e for e in errors)


def test_lint_rejects_off_safelist_command():
    # 3.9 class: a command that can never execute (pytest is not on the safelist).
    def bad_cmd(d):
        d["fill_files"]["backend/routes.py"]["implementation"][0]["argv"] = ["pytest", "-q"]

    errors = _lint(bad_cmd)
    assert any("not in the execution safelist" in e for e in errors)


def test_lint_rejects_regex_match_against_source_file():
    # 3.10/3.14 class: source-file regexes prescribe another roll's style. #464 as
    # a schema rule — regex_match is document-only, and fill files are source.
    def source_regex(d):
        d["fill_files"]["backend/routes.py"]["implementation"].append(
            {
                "check": "regex_match",
                "id": "vc-style",
                "file": "backend/routes.py",
                "pattern": r"runs_store\s*=\s*\[",
            }
        )

    errors = _lint(source_regex)
    assert any("regex_match may only target document" in e for e in errors) or any(
        "not allowed in the implementation class" in e for e in errors
    )


def test_lint_rejects_uncompilable_regex():
    # 3.14 class: a pattern syntactically incapable of matching anything.
    def bad_regex(d):
        d["fill_files"]["backend/routes.py"]["implementation"].append(
            {
                "check": "regex_match",
                "id": "vc-broken",
                "file": "qa_handoff.md",
                "pattern": r"(unclosed[",
            }
        )

    errors = _lint(bad_regex)
    assert any("does not compile" in e for e in errors)


def test_lint_rejects_unknown_behavioral_check():
    def bad_behavioral(d):
        d["behavioral"]["build"][0]["check"] = "vibe_check"

    errors = _lint(bad_behavioral)
    assert any("unknown framework check 'vibe_check'" in e for e in errors)


def test_lint_rejects_incomplete_probe():
    def bad_probe(d):
        d["behavioral"]["probes"][0]["subject"] = ""
        del d["behavioral"]["probes"][0]["expect"]["status"]

    errors = _lint(bad_probe)
    assert any("probe[vc-probe-create]: missing 'subject'" in e for e in errors)
    assert any("expect must declare a 'status'" in e for e in errors)


def test_lint_rejects_empty_fill_files():
    errors = _lint(lambda d: d.__setitem__("fill_files", {}))
    assert any("fill_files is empty" in e for e in errors)


def test_known_capabilities_are_python_and_node():
    # Guards the vocabulary the whole contract binds against; python is the always-
    # present base, node the one provisionable tool (check_registry.TOOL_NODE, #306).
    assert KNOWN_CAPABILITIES == {"python", "node"}


def test_lint_accumulates_multiple_defects():
    # collect-all, not raise-first: the whole contract is validated in one pass so
    # authors see every defect at once (unlike the plan parser's first-error raise).
    def many(d):
        d["skeleton"]["interface_manifest_hash"] = ""
        d["capabilities"].append("rust")
        d["fill_files"]["backend/routes.py"]["implementation"][0]["argv"] = ["make"]

    errors = _lint(many)
    assert len(errors) >= 3
