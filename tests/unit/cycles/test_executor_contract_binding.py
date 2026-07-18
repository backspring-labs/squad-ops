"""Executor-side contract seeding + bind-mode plan validation (SIP-0098 phase 98.3, slice B).

A seeded ``contract_ref`` switches a cycle to bind mode: the executor loads the
verification contract, and the gate-time plan-validation net (net-b) rejects a plan
that fails to bind the contract's covered-file criteria, or a contract bound to a
different skeleton. Contract absent = author mode = byte-identical to today. Mirrors
``test_executor_interface_manifest.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold_contract import emit_contract_yaml
from squadops.cycles.verification_contract import VerificationContract

_MANIFEST_YAML = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")
_MANIFEST = InterfaceManifest.from_yaml(_MANIFEST_YAML)
_CONTRACT_YAML = emit_contract_yaml(_MANIFEST)
_CONTRACT = VerificationContract.from_yaml(_CONTRACT_YAML)

# A bind-mode plan: the routes task binds all three of routes.py's contract criteria.
_ROUTES_REFS = list(_CONTRACT.required_ref_ids_for("backend/routes.py"))
_BIND_PLAN_YAML = f"""
version: 1
project_id: group_run
cycle_id: cyc
prd_hash: h
tasks:
  - task_index: 0
    task_type: development.develop
    role: neo
    focus: routes
    description: fill routes
    expected_artifacts: [backend/routes.py]
    criteria_refs: [{", ".join(_ROUTES_REFS)}]
    acceptance_criteria: []
summary: {{total_dev_tasks: 1, total_qa_tasks: 0, total_tasks: 1}}
"""


@dataclass
class _Ref:
    artifact_id: str
    filename: str
    artifact_type: str
    metadata: dict = field(default_factory=dict)


def _make_executor(store: dict[str, tuple[_Ref, bytes]]) -> DispatchedFlowExecutor:
    executor = DispatchedFlowExecutor.__new__(DispatchedFlowExecutor)
    executor._artifact_vault = MagicMock()

    async def _retrieve(ref_id: str):
        return store[ref_id]

    executor._artifact_vault.retrieve = AsyncMock(side_effect=_retrieve)
    return executor


def _make_cycle(**overrides) -> MagicMock:
    cycle = MagicMock()
    cycle.execution_overrides = {}
    cycle.applied_defaults = {"implementation_plan": True}
    cycle.project_id = "group_run"
    cycle.cycle_id = "cyc"
    for k, v in overrides.items():
        setattr(cycle, k, v)
    return cycle


def _make_run(artifact_refs=()) -> MagicMock:
    run = MagicMock()
    run.run_id = "run_abcdef123456"
    run.artifact_refs = list(artifact_refs)
    return run


# --------------------------------------------------------------------------- #
# _is_bind_mode
# --------------------------------------------------------------------------- #


def test_is_bind_mode_true_only_when_contract_ref_present():
    assert DispatchedFlowExecutor._is_bind_mode(
        _make_cycle(execution_overrides={"contract_ref": "c"})
    )
    assert not DispatchedFlowExecutor._is_bind_mode(_make_cycle(execution_overrides={}))
    # an empty/false ref is not bind mode (data-driven presence check)
    assert not DispatchedFlowExecutor._is_bind_mode(
        _make_cycle(execution_overrides={"contract_ref": ""})
    )


# --------------------------------------------------------------------------- #
# _load_contract_for_run
# --------------------------------------------------------------------------- #


async def test_load_contract_returns_parsed_contract():
    store = {
        "art_c": (
            _Ref("art_c", "verification_contract.yaml", "verification_contract"),
            _CONTRACT_YAML.encode(),
        )
    }
    executor = _make_executor(store)
    cycle = _make_cycle(execution_overrides={"contract_ref": "art_c"})

    contract = await executor._load_contract_for_run(cycle, _make_run())

    assert contract is not None
    assert contract.skeleton.expander == "fullstack_fastapi_react"
    assert contract.covered_fill_paths() == _CONTRACT.covered_fill_paths()


async def test_load_contract_accepts_single_element_list_ref():
    store = {
        "art_c": (
            _Ref("art_c", "verification_contract.yaml", "verification_contract"),
            _CONTRACT_YAML.encode(),
        )
    }
    executor = _make_executor(store)
    cycle = _make_cycle(execution_overrides={"contract_ref": ["art_c"]})
    assert await executor._load_contract_for_run(cycle, _make_run()) is not None


async def test_load_contract_none_when_no_ref():
    executor = _make_executor({})
    assert await executor._load_contract_for_run(_make_cycle(), _make_run()) is None


async def test_load_contract_none_when_unparseable_but_stays_bind_mode():
    # a seeded-but-broken contract loads to None, but bind mode is still on so the
    # net records a rejection rather than silently reverting to author mode (§10).
    store = {
        "art_c": (
            _Ref("art_c", "verification_contract.yaml", "verification_contract"),
            b"::: not yaml :::",
        )
    }
    executor = _make_executor(store)
    cycle = _make_cycle(execution_overrides={"contract_ref": "art_c"})
    assert await executor._load_contract_for_run(cycle, _make_run()) is None
    assert DispatchedFlowExecutor._is_bind_mode(cycle) is True


# --------------------------------------------------------------------------- #
# _validate_contract_binding (hash-binding, §10 = FAIL on mismatch)
# --------------------------------------------------------------------------- #


def test_contract_binding_ok_when_manifest_hash_matches():
    assert DispatchedFlowExecutor._validate_contract_binding(_CONTRACT, _MANIFEST_YAML) == []


def test_contract_binding_rejects_hash_mismatch():
    tampered = VerificationContract.from_dict(
        {
            **_CONTRACT.to_dict(),
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "f" * 64,
            },
        }
    )
    errors = DispatchedFlowExecutor._validate_contract_binding(tampered, _MANIFEST_YAML)
    assert len(errors) == 1
    assert "different skeleton" in errors[0]


def test_contract_binding_noop_on_unparseable_manifest():
    # the manifest's own parse rejection is recorded elsewhere; no duplicate here
    assert DispatchedFlowExecutor._validate_contract_binding(_CONTRACT, "::: not yaml :::") == []


# --------------------------------------------------------------------------- #
# net-b: _reject_invalid_plan_before_workload_gate in bind mode
# --------------------------------------------------------------------------- #


def _bind_store(plan_yaml: str = _BIND_PLAN_YAML, contract_yaml: str = _CONTRACT_YAML) -> dict:
    return {
        "art_plan": (
            _Ref("art_plan", "implementation_plan.yaml", "control_implementation_plan"),
            plan_yaml.encode(),
        ),
        "art_iface": (
            _Ref("art_iface", "interface_manifest.yaml", "interface_manifest"),
            _MANIFEST_YAML.encode(),
        ),
        "art_c": (
            _Ref("art_c", "verification_contract.yaml", "verification_contract"),
            contract_yaml.encode(),
        ),
    }


async def test_net_b_bind_mode_valid_plan_passes():
    executor = _make_executor(_bind_store())
    cycle = _make_cycle(execution_overrides={"contract_ref": "art_c"})
    run = _make_run(["art_plan", "art_iface"])

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    assert errors == []


async def test_net_b_rejects_when_contract_ref_unparseable():
    executor = _make_executor(_bind_store(contract_yaml="::: not yaml :::"))
    cycle = _make_cycle(execution_overrides={"contract_ref": "art_c"})
    run = _make_run(["art_plan", "art_iface"])

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    assert any("contract_ref is seeded but the contract is" in e for e in errors)


async def test_net_b_rejects_missing_coverage():
    # the plan drops one required ref -> silent descoping -> rejection
    thin_plan = _BIND_PLAN_YAML.replace(f"[{', '.join(_ROUTES_REFS)}]", f"[{_ROUTES_REFS[0]}]")
    executor = _make_executor(_bind_store(plan_yaml=thin_plan))
    cycle = _make_cycle(execution_overrides={"contract_ref": "art_c"})
    run = _make_run(["art_plan", "art_iface"])

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    assert any("verification_contract:" in e and "does not bind its criteria" in e for e in errors)


async def test_net_b_rejects_authored_criterion_on_covered_file():
    authored_plan = _BIND_PLAN_YAML.replace(
        "acceptance_criteria: []",
        "acceptance_criteria:\n      - {check: import_present, file: backend/routes.py, module: .errors, symbol: ApiError}",
    )
    executor = _make_executor(_bind_store(plan_yaml=authored_plan))
    cycle = _make_cycle(execution_overrides={"contract_ref": "art_c"})
    run = _make_run(["art_plan", "art_iface"])

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    assert any("authored typed criterion" in e and "backend/routes.py" in e for e in errors)


async def test_net_b_rejects_hash_mismatch():
    tampered = VerificationContract.from_dict(
        {
            **_CONTRACT.to_dict(),
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "f" * 64,
            },
        }
    )
    import yaml

    executor = _make_executor(_bind_store(contract_yaml=yaml.safe_dump(tampered.to_dict())))
    cycle = _make_cycle(execution_overrides={"contract_ref": "art_c"})
    run = _make_run(["art_plan", "art_iface"])

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    assert any("different skeleton" in e for e in errors)


async def test_net_b_author_mode_ignores_contract_binding():
    # no contract_ref -> author mode -> the bind-mode branch is a no-op (byte-identical).
    # the plan here carries criteria_refs but author mode never validates them.
    executor = _make_executor(_bind_store())
    cycle = _make_cycle(execution_overrides={})  # no contract_ref
    run = _make_run(["art_plan", "art_iface"])

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    # only the interface-manifest net runs (manifest is valid) -> no bind errors
    assert not any("verification_contract" in e for e in errors)


# --------------------------------------------------------------------------- #
# #496: bind mode falls back to the operator-seeded manifest
# --------------------------------------------------------------------------- #

# Parses and lints clean but hashes differently — the re-derivation-drift shape
# shakedown cyc_59bfbd3f4a2a produced live (plausible rename, broken hash).
_DRIFTED_MANIFEST_YAML = _MANIFEST_YAML.replace("name: Participant", "name: Attendee", 1)


async def test_net_b_seeded_manifest_satisfies_when_framing_emits_none():
    # bug caught: fallback not wired — bind mode without a framing-emitted manifest
    # would reject (#494) even though the canonical manifest is seeded on the very
    # rail (plan_artifact_refs) the implementation run scaffolds from.
    executor = _make_executor(_bind_store())
    cycle = _make_cycle(
        execution_overrides={"contract_ref": "art_c", "plan_artifact_refs": ["art_iface"]}
    )
    run = _make_run(["art_plan"])  # framing emitted the plan only, no manifest

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    assert errors == []


async def test_net_b_seeded_manifest_is_hash_checked():
    # bug caught: fallback skipping validation — a seeded manifest the contract was
    # NOT authored against must still trip the §10 stale-binding rejection.
    import yaml

    tampered = VerificationContract.from_dict(
        {
            **_CONTRACT.to_dict(),
            "skeleton": {
                "expander": "fullstack_fastapi_react",
                "interface_manifest_hash": "f" * 64,
            },
        }
    )
    executor = _make_executor(_bind_store(contract_yaml=yaml.safe_dump(tampered.to_dict())))
    cycle = _make_cycle(
        execution_overrides={"contract_ref": "art_c", "plan_artifact_refs": ["art_iface"]}
    )
    run = _make_run(["art_plan"])

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    assert any("different skeleton" in e for e in errors)


async def test_net_b_drifted_framing_manifest_rejects_despite_matching_seed():
    # bug caught: precedence inversion — preferring the seed would silently mask a
    # framing-emitted manifest that drifted from the contract (drift must still reject).
    store = _bind_store()
    store["art_iface_drift"] = (
        _Ref("art_iface_drift", "interface_manifest.yaml", "interface_manifest"),
        _DRIFTED_MANIFEST_YAML.encode(),
    )
    executor = _make_executor(store)
    cycle = _make_cycle(
        execution_overrides={"contract_ref": "art_c", "plan_artifact_refs": ["art_iface"]}
    )
    run = _make_run(["art_plan", "art_iface_drift"])  # framing emitted a drifted manifest

    errors = await executor._reject_invalid_plan_before_workload_gate(run, cycle, "plan-review")

    assert any("different skeleton" in e for e in errors)
