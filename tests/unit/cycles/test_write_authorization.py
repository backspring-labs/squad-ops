"""SIP-0100 Task 2.1 — WorkspaceOwnership / WriteGrant / WriteAuthorization."""

from __future__ import annotations

from pathlib import Path

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.bound_scaffold_record import build_bound_record
from squadops.cycles.write_authorization import (
    AuthzDecision,
    WorkspaceOwnership,
    WriteAuthorization,
    WriteGrant,
    normalize_ws_path,
)

_MANIFEST = Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"


def _ownership() -> WorkspaceOwnership:
    rec = build_bound_record(
        InterfaceManifest.from_yaml(_MANIFEST.read_text()),
        run_id="r",
        attempt_id="a",
        created_at="t",
    )
    return WorkspaceOwnership.from_record(rec)


def test_normalize_ws_path():
    assert normalize_ws_path("./backend/main.py") == "backend/main.py"
    assert normalize_ws_path("backend//main.py") == "backend/main.py"
    assert normalize_ws_path("backend/x/../main.py") == "backend/main.py"
    assert normalize_ws_path("/etc/passwd") is None
    assert normalize_ws_path("../secret") is None
    assert normalize_ws_path("") is None


def test_frozen_emission_is_forbidden_even_via_alias():
    own = _ownership()
    assert "backend/main.py" in own.frozen_paths  # the pf-26 file is frozen
    authz = WriteAuthorization(own, WriteGrant.for_qa("eve", own))
    assert authz.authorize("backend/main.py") == AuthzDecision.FORBIDDEN_FROZEN
    assert authz.authorize("./backend/main.py") == AuthzDecision.FORBIDDEN_FROZEN
    assert authz.authorize("backend/sub/../main.py") == AuthzDecision.FORBIDDEN_FROZEN


def test_qa_grant_allows_namespace_forbids_dev_slot_and_undeclared():
    own = _ownership()
    authz = WriteAuthorization(own, WriteGrant.for_qa("eve", own))
    assert authz.authorize("backend/tests/test_runs.py") == AuthzDecision.ALLOWED
    assert authz.authorize("backend/routes.py") == AuthzDecision.FORBIDDEN_UNAUTHORIZED
    assert authz.authorize("random/thing.py") == AuthzDecision.FORBIDDEN_UNDECLARED


def test_dev_grant_allows_fill_slot_forbids_qa_file():
    own = _ownership()
    authz = WriteAuthorization(own, WriteGrant.for_dev_fill("neo", own))
    assert authz.authorize("backend/routes.py") == AuthzDecision.ALLOWED
    assert authz.authorize("backend/tests/test_x.py") == AuthzDecision.FORBIDDEN_UNAUTHORIZED


def test_response_atomic_all_allowed():
    own = _ownership()
    authz = WriteAuthorization(own, WriteGrant.for_qa("eve", own))
    r = authz.authorize_response(["backend/tests/a.py", "backend/tests/b.py"])
    assert r.allowed and not r.violations


def test_response_atomic_any_forbidden_rejects_whole_response():
    """pf-26 mixed emission: a valid test file + the frozen main.py rejects the whole response."""
    own = _ownership()
    authz = WriteAuthorization(own, WriteGrant.for_qa("eve", own))
    r = authz.authorize_response(["backend/tests/a.py", "backend/main.py"])
    assert not r.allowed
    assert ("backend/main.py", AuthzDecision.FORBIDDEN_FROZEN) in r.violations


def test_duplicate_normalized_paths_reject_response():
    own = _ownership()
    authz = WriteAuthorization(own, WriteGrant.for_qa("eve", own))
    r = authz.authorize_response(["backend/tests/a.py", "./backend/tests/a.py"])
    assert not r.allowed
