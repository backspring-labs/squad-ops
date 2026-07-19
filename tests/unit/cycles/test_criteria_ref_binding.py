"""Bind-mode plan validation and contract-ref resolution (SIP-0098 phase 98.3, slice A).

The verification contract owns the acceptance of contract-covered fill files; in bind
mode a plan *binds* those criteria by stable id (``criteria_refs``) rather than authoring
its own typed checks. This module's unit under test is the pure cycles-domain surface that
makes that possible: the contract resolution helpers, the ``criteria_refs`` / ``TypedCheck.id``
model fields (incl. their A2A-wire round-trip), and ``ImplementationPlan.validate_criteria_refs``.
"""

from __future__ import annotations

import dataclasses

import pytest

from squadops.cycles.acceptance_evaluation import split_acceptance_criteria
from squadops.cycles.implementation_plan import (
    ImplementationPlan,
    TypedCheck,
    _serialize_acceptance_criterion,
    resolve_contract_refs,
)
from squadops.cycles.verification_contract import VerificationContract
from squadops.cycles.verification_normalize import normalize_task_checks

pytestmark = [pytest.mark.domain_capabilities]


def _contract() -> VerificationContract:
    """A two-fill-file contract: routes (2 interface + 1 implementation) and a view
    (1 interface). Behavioral checks add a file-less id to prove the index handles them."""
    return VerificationContract.from_dict(
        {
            "contract_version": 1,
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "a" * 64,
            },
            "capabilities": ["python", "node"],
            "frozen": [{"path": "backend/errors.py", "sha256": "b" * 64}],
            "fill_files": {
                "backend/routes.py": {
                    "interface": [
                        {
                            "check": "endpoint_defined",
                            "id": "vc-routes-endpoints",
                            "methods_paths": ["GET /items"],
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
                "frontend/src/views/ItemView.jsx": {
                    "interface": [
                        {
                            "check": "import_present",
                            "id": "vc-view-apifetch",
                            "module": "../api",
                            "symbol": "apiFetch",
                        },
                    ],
                    "implementation": [],
                },
            },
            "behavioral": {
                "build": [
                    {"check": "frontend_build", "id": "vc-frontend-builds", "requires": "node"}
                ],
                "suite": {"checks": [], "coverage_expectations": []},
                "probes": [],
            },
        }
    )


def _plan_yaml(
    *, refs: str = "", authored: str = "", artifacts: str = "[backend/routes.py]"
) -> str:
    return f"""
version: 1
project_id: p
cycle_id: cy
prd_hash: h
tasks:
  - task_index: 0
    task_type: development.develop
    role: neo
    focus: routes
    description: fill the routes module
    expected_artifacts: {artifacts}
    criteria_refs: {refs or "[]"}
    acceptance_criteria:{authored or " []"}
summary: {{total_dev_tasks: 1, total_qa_tasks: 0, total_tasks: 1}}
"""


# --------------------------------------------------------------------------- #
# Contract resolution helpers
# --------------------------------------------------------------------------- #


def test_criterion_index_maps_id_to_criterion_and_owning_path():
    idx = _contract().criterion_index()
    # every typed criterion (not probes) is present, keyed by id
    assert set(idx) == {
        "vc-routes-endpoints",
        "vc-routes-apierror",
        "vc-routes-compiles",
        "vc-view-apifetch",
        "vc-frontend-builds",
    }
    # fill-file criteria carry their owning path; behavioral checks are file-less
    assert idx["vc-routes-compiles"][1] == "backend/routes.py"
    assert idx["vc-view-apifetch"][1] == "frontend/src/views/ItemView.jsx"
    assert idx["vc-frontend-builds"][1] == ""
    assert idx["vc-routes-endpoints"][0].check == "endpoint_defined"


def test_covered_fill_paths_are_exactly_the_fill_file_keys():
    assert _contract().covered_fill_paths() == frozenset(
        {"backend/routes.py", "frontend/src/views/ItemView.jsx"}
    )


def test_required_ref_ids_for_lists_interface_then_implementation_in_order():
    c = _contract()
    assert c.required_ref_ids_for("backend/routes.py") == (
        "vc-routes-endpoints",
        "vc-routes-apierror",
        "vc-routes-compiles",
    )
    # a view with no implementation criteria still returns its interface id
    assert c.required_ref_ids_for("frontend/src/views/ItemView.jsx") == ("vc-view-apifetch",)


def test_required_ref_ids_for_unknown_path_is_empty():
    # a file the contract does not cover imposes no binding requirement
    assert _contract().required_ref_ids_for("backend/uncovered.py") == ()


# --------------------------------------------------------------------------- #
# Model: criteria_refs + TypedCheck.id parsing / serialization
# --------------------------------------------------------------------------- #


def test_criteria_refs_parse_onto_plan_task():
    plan = ImplementationPlan.from_yaml(
        _plan_yaml(refs="[vc-routes-endpoints, vc-routes-compiles]")
    )
    assert plan.tasks[0].criteria_refs == ["vc-routes-endpoints", "vc-routes-compiles"]


@pytest.mark.parametrize("bad", ["not-a-list", "[1, 2]", "[vc-ok, 3]"])
def test_criteria_refs_must_be_a_list_of_strings(bad):
    with pytest.raises(ValueError, match="criteria_refs must be a list of strings"):
        ImplementationPlan.from_yaml(_plan_yaml(refs=bad))


def test_absent_criteria_refs_defaults_to_empty():
    # contract-less plans never author the field; it must default cleanly
    y = _plan_yaml().replace("    criteria_refs: []\n", "")
    assert ImplementationPlan.from_yaml(y).tasks[0].criteria_refs == []


def test_typed_check_id_parses_and_round_trips_through_serialize():
    authored = (
        "\n      - {check: import_present, file: backend/other.py, "
        "module: .errors, symbol: ApiError, id: vc-manual}"
    )
    plan = ImplementationPlan.from_yaml(
        _plan_yaml(authored=authored, artifacts="[backend/other.py]")
    )
    crit = plan.tasks[0].acceptance_criteria[0]
    assert isinstance(crit, TypedCheck)
    assert crit.id == "vc-manual"
    assert "id" not in crit.params  # id is a wrapper key, never a check param
    # serialize keeps id at top level, alongside check/params/severity
    assert _serialize_acceptance_criterion(crit)["id"] == "vc-manual"


def test_typed_check_id_excluded_from_fingerprint():
    # id labels provenance, not identity — two checks differing only by id must share
    # a per-criterion error counter (SIP-0092 retry accounting must not reset).
    a = TypedCheck(check="import_present", params={"file": "x.py", "module": "m", "symbol": "s"})
    b = dataclasses.replace(a, id="vc-x")
    assert a.fingerprint() == b.fingerprint()


def test_resolved_typed_check_id_survives_the_a2a_wire():
    # A TypedCheck resolved from a criteria_ref crosses the wire as a
    # dataclasses.asdict row (params nested + id). split_acceptance_criteria must
    # re-parse it with the contract id intact — else evidence loses its criterion id.
    resolved = TypedCheck(
        check="import_present",
        params={"file": "backend/routes.py", "module": ".errors", "symbol": "ApiError"},
        id="vc-routes-apierror",
    )
    wire_row = dataclasses.asdict(resolved)
    assert wire_row["id"] == "vc-routes-apierror"  # asdict keeps it nested-with-params shape

    split = split_acceptance_criteria([wire_row])
    assert not split.unparseable
    assert len(split.typed) == 1
    assert split.typed[0].id == "vc-routes-apierror"
    assert split.typed[0].check == "import_present"


# --------------------------------------------------------------------------- #
# validate_criteria_refs — the three rejection classes + the clean path
# --------------------------------------------------------------------------- #


def test_fully_bound_plan_validates_clean():
    plan = ImplementationPlan.from_yaml(
        _plan_yaml(refs="[vc-routes-endpoints, vc-routes-apierror, vc-routes-compiles]")
    )
    assert plan.validate_criteria_refs(_contract()) == []


def test_unresolvable_ref_is_rejected():
    plan = ImplementationPlan.from_yaml(
        _plan_yaml(refs="[vc-routes-endpoints, vc-routes-apierror, vc-routes-compiles, vc-bogus]")
    )
    errors = plan.validate_criteria_refs(_contract())
    assert any("vc-bogus" in e and "does not resolve" in e for e in errors)


def test_missing_coverage_is_rejected_with_the_unbound_ids():
    # binds only 1 of routes.py's 3 criteria → silent descoping of the other two
    plan = ImplementationPlan.from_yaml(_plan_yaml(refs="[vc-routes-endpoints]"))
    errors = plan.validate_criteria_refs(_contract())
    assert len(errors) == 1
    assert "backend/routes.py" in errors[0]
    assert "vc-routes-apierror" in errors[0] and "vc-routes-compiles" in errors[0]


def test_authored_typed_criterion_on_covered_file_is_rejected():
    authored = (
        "\n      - {check: import_present, file: backend/routes.py, "
        "module: .errors, symbol: ApiError}"
    )
    plan = ImplementationPlan.from_yaml(
        _plan_yaml(
            refs="[vc-routes-endpoints, vc-routes-apierror, vc-routes-compiles]", authored=authored
        )
    )
    errors = plan.validate_criteria_refs(_contract())
    assert any("authored typed criterion" in e and "backend/routes.py" in e for e in errors)


def test_authored_typed_criterion_on_uncovered_file_is_allowed():
    # binding routes fully, and authoring a check on an UNCOVERED file, is legal —
    # the contract only owns acceptance of the files it covers.
    authored = (
        "\n      - {check: import_present, file: backend/helpers.py, module: .util, symbol: helper}"
    )
    plan = ImplementationPlan.from_yaml(
        _plan_yaml(
            refs="[vc-routes-endpoints, vc-routes-apierror, vc-routes-compiles]",
            authored=authored,
            artifacts="[backend/routes.py, backend/helpers.py]",
        )
    )
    assert plan.validate_criteria_refs(_contract()) == []


def test_task_not_touching_covered_files_imposes_no_binding():
    # a task producing only an uncovered artifact needs no refs at all
    plan = ImplementationPlan.from_yaml(_plan_yaml(artifacts="[backend/helpers.py]"))
    assert plan.validate_criteria_refs(_contract()) == []


# --------------------------------------------------------------------------- #
# Dispatch enrichment: resolve_contract_refs (criteria_refs -> TypedCheck)
# --------------------------------------------------------------------------- #


def test_resolve_contract_refs_builds_typed_checks_with_id_and_file():
    c = _contract()
    checks = resolve_contract_refs(list(c.required_ref_ids_for("backend/routes.py")), c)
    by_id = {tc.id: tc for tc in checks}
    assert set(by_id) == {"vc-routes-endpoints", "vc-routes-apierror", "vc-routes-compiles"}
    # file-targeting checks get the owning fill path stamped as their `file` param
    assert by_id["vc-routes-endpoints"].check == "endpoint_defined"
    assert by_id["vc-routes-endpoints"].params["file"] == "backend/routes.py"
    assert by_id["vc-routes-apierror"].params["file"] == "backend/routes.py"
    # command_exit_zero targets via argv, not a file param — no file injected
    assert "file" not in by_id["vc-routes-compiles"].params
    assert by_id["vc-routes-compiles"].params["argv"][:3] == ["python", "-m", "py_compile"]


def test_resolve_contract_refs_skips_behavioral_and_unresolvable():
    c = _contract()
    # vc-frontend-builds is a behavioral framework check (materialized by the qa/build
    # handlers, not the typed-acceptance seam); an unknown id resolves to nothing.
    assert resolve_contract_refs(["vc-frontend-builds", "nope"], c) == []


def test_resolved_check_survives_wire_and_reaches_check_result():
    # resolve -> asdict wire row -> split re-parse keeps the id; and a produced
    # evidence row carrying that id normalizes onto CheckResult.criterion_id.
    import dataclasses

    c = _contract()
    tc = resolve_contract_refs(["vc-routes-apierror"], c)[0]
    reparsed = split_acceptance_criteria([dataclasses.asdict(tc)]).typed[0]
    assert reparsed.id == "vc-routes-apierror"

    outputs = {
        "validation_result": {
            "checks": [
                {
                    "check": "acceptance:import_present",
                    "status": "passed",
                    "criterion_id": "vc-routes-apierror",
                }
            ]
        }
    }
    results = normalize_task_checks(outputs, subject="task-routes")
    assert [(r.check_id, r.criterion_id) for r in results] == [
        ("acceptance:import_present", "vc-routes-apierror")
    ]


def test_author_mode_check_result_has_no_criterion_id():
    # a row without a criterion_id (author mode / framework check) normalizes to None
    outputs = {
        "validation_result": {
            "checks": [{"check": "acceptance:endpoint_defined", "status": "passed"}]
        }
    }
    results = normalize_task_checks(outputs, subject="t")
    assert results[0].criterion_id is None


# --------------------------------------------------------------------------- #
# dispatch-time residue attachment (#509) — bug caught: binding keyed on exact
# LLM-authored path strings, so a plan that named a covered file differently
# bound nothing and criterion coverage varied roll to roll (criteria_total went
# 3 -> 1 -> 1 across identical seeded contracts in the night rolls).
# --------------------------------------------------------------------------- #

from squadops.cycles.implementation_plan import CHECK_SPECS  # noqa: E402
from squadops.cycles.task_plan import _attach_unbound_contract_criteria  # noqa: E402
from squadops.tasks.models import TaskEnvelope  # noqa: E402


def _envelope(task_type: str, inputs: dict | None = None) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=f"t-{task_type}",
        agent_id="qa",
        cycle_id="cyc_x",
        pulse_id="p1",
        project_id="proj",
        task_type=task_type,
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs=inputs if inputs is not None else {},
        metadata={},
    )


def _typed_ids(contract: VerificationContract) -> set[str]:
    # resolve_contract_refs materializes only typed-acceptance criteria; behavioral
    # ones (frontend_build / tests_pass vocabulary) run via the qa/build handlers.
    return {
        rid for rid, (crit, _) in contract.criterion_index().items() if crit.check in CHECK_SPECS
    }


def _criterion_ids(envelope: TaskEnvelope) -> set[str]:
    return {
        c.id
        for c in envelope.inputs.get("acceptance_criteria", ())
        if isinstance(c, TypedCheck) and c.id
    }


def test_unbound_criteria_attach_to_tail_qa_test_with_ids():
    contract = _contract()
    dev = _envelope("development.develop")
    qa = _envelope("qa.test", inputs={"acceptance_criteria": []})
    _attach_unbound_contract_criteria([dev, qa], None, contract)
    # every typed criterion in the contract lands on the tail qa.test, stamped
    assert _criterion_ids(qa) == _typed_ids(contract)
    assert dev.inputs.get("acceptance_criteria") is None


def test_bound_refs_are_excluded_from_residue():
    contract = _contract()
    plan = ImplementationPlan.from_yaml(
        _plan_yaml(refs=["vc-routes-endpoints", "vc-routes-apierror", "vc-routes-compiles"])
    )
    qa = _envelope("qa.test")
    _attach_unbound_contract_criteria([qa], plan, contract)
    ids = _criterion_ids(qa)
    assert "vc-routes-endpoints" not in ids
    assert ids == _typed_ids(contract) - {
        "vc-routes-endpoints",
        "vc-routes-apierror",
        "vc-routes-compiles",
    }


def test_residue_attaches_to_last_qa_test_only():
    contract = _contract()
    qa1 = _envelope("qa.test")
    qa2 = _envelope("qa.test")
    _attach_unbound_contract_criteria([qa1, qa2], None, contract)
    assert _criterion_ids(qa1) == set()
    assert _criterion_ids(qa2) == _typed_ids(contract)


def test_author_mode_and_missing_qa_are_no_ops():
    dev = _envelope("development.develop")
    _attach_unbound_contract_criteria([dev], None, None)  # author mode
    assert "acceptance_criteria" not in dev.inputs
    _attach_unbound_contract_criteria([dev], None, _contract())  # no qa.test envelope
    assert "acceptance_criteria" not in dev.inputs
