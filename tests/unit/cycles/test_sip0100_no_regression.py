"""SIP-0100 Phase 4.5 — legacy/unbound + no-regression guarantees.

The "suites green" clause (capability / verification-contract / build-convergence) is a
CI/regression gate, not asserted here. These tests pin the two binding-boundary properties
that aren't covered elsewhere: enforcement is all-or-nothing, and the current fail-open
behavior on a binding error (a documented D3 deviation).
"""

from __future__ import annotations

from pathlib import Path

import squadops.cycles.bound_scaffold_record as bsr
from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.capabilities.scaffold import InterfaceManifest

_MANIFEST = Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"


def _manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST.read_text())


def _unscaffoldable() -> InterfaceManifest:
    return InterfaceManifest.from_dict(
        {"version": 1, "kind": "interface_manifest", "project_id": "x", "stack": "cobol_cics"}
    )


def _scaffoldable_minimal() -> InterfaceManifest:
    return InterfaceManifest.from_dict(
        {
            "version": 1,
            "kind": "interface_manifest",
            "project_id": "x",
            "stack": "fullstack_fastapi_react",
        }
    )


def test_binding_is_all_or_nothing_never_partial():
    """Enforcement binds fully or not at all. A scaffoldable manifest yields a record whose frozen
    set covers every scaffold-frozen file across BOTH stacks (backend + frontend + harness); a
    non-scaffoldable stack yields None — never a partial record that would protect some frozen
    files but silently leave others writable."""
    rec = DispatchedFlowExecutor._build_bound_record_for_run(object(), _manifest(), "r")
    assert rec is not None
    frozen = set(rec.frozen_paths())
    for p in (
        "backend/main.py",
        "backend/models.py",
        "backend/errors.py",
        "conftest.py",
        "frontend/src/App.jsx",
        "frontend/src/main.jsx",
    ):
        assert p in frozen, f"{p} missing from the frozen set — enforcement would be partial"
    # A fill slot is NOT frozen (it's the writable surface) — completeness cuts both ways.
    assert "backend/routes.py" not in frozen

    # Unbound stack → no record at all (not a partial one).
    assert (
        DispatchedFlowExecutor._build_bound_record_for_run(object(), _unscaffoldable(), "r") is None
    )


def test_unbound_manifest_disables_enforcement():
    """A None manifest (a genuinely unbound/legacy run) binds nothing — the executor guard then
    skips enforcement entirely, preserving pre-SIP behavior."""
    assert DispatchedFlowExecutor._build_bound_record_for_run(object(), None, "r") is None


def test_binding_error_fails_open_documented_d3_deviation(monkeypatch):
    """D3 deviation, pinned deliberately. D3 says a scaffold-bound flow whose binding fails must
    FAIL the run (fail-closed — enforcement can't be bypassed by broken wiring). The 2.4
    implementation chose fail-OPEN: a ``build_bound_record`` error disables enforcement (returns
    None) and the run continues, a conscious rollout-safety choice ("a build failure disables
    enforcement rather than failing the run"). This test locks the CURRENT behavior; hardening to
    fail-closed is a separate decision (see the plan §4.5 note)."""

    def _boom(*a, **k):
        raise RuntimeError("binding blew up")

    monkeypatch.setattr(bsr, "build_bound_record", _boom)
    # A scaffoldable stack (so binding IS attempted) whose build then raises → fail-open None.
    result = DispatchedFlowExecutor._build_bound_record_for_run(
        object(), _scaffoldable_minimal(), "r"
    )
    assert result is None  # fail-OPEN: enforcement disabled, run continues (NOT D3 fail-closed)
