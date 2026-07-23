"""SIP-0100 Phase 4 (4.1–4.3) — deterministic replay & path/atomicity matrix.

Adds the cases not already covered by ``test_write_authorization.py`` (authz matrix),
``test_materialize_unified.py`` (materialize/atomicity + integrity), and
``test_acceptance_checks.py`` (harness_boundary). Everything here is deterministic —
no live cycle.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.bound_scaffold_record import (
    BoundScaffoldRecord,
    FrozenArtifact,
    build_bound_record,
)
from squadops.cycles.patch_verification import materialize, restore_frozen_files
from squadops.cycles.write_authorization import (
    AuthzDecision,
    WorkspaceOwnership,
    WriteAuthorization,
    WriteGrant,
    normalize_ws_path,
)

_MANIFEST = Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"


def _record() -> BoundScaffoldRecord:
    return build_bound_record(
        InterfaceManifest.from_yaml(_MANIFEST.read_text()),
        run_id="r",
        attempt_id="a",
        created_at="t",
    )


def _ownership() -> WorkspaceOwnership:
    return WorkspaceOwnership.from_record(_record())


def _env(task_type: str = "development.develop") -> SimpleNamespace:
    return SimpleNamespace(task_id="task-1", task_type=task_type)


def _frozen_content(rec: BoundScaffoldRecord, norm: str) -> str:
    return next(fa.content for fa in rec.frozen if normalize_ws_path(fa.path) == norm)


def _enforce(artifacts, rec, env):
    return DispatchedFlowExecutor._enforce_frozen_ownership(object(), artifacts, rec, env)


# --------------------------------------------------------------------------- #
# 4.1 — path / atomicity matrix (the cases not already covered)
# --------------------------------------------------------------------------- #


def test_frozen_only_response_is_rejected_wholesale():
    """A response containing ONLY a frozen path (no valid sibling) is still rejected."""
    own = _ownership()
    authz = WriteAuthorization(own, WriteGrant.for_qa("eve", own))
    r = authz.authorize_response(["backend/main.py"])
    assert not r.allowed
    assert ("backend/main.py", AuthzDecision.FORBIDDEN_FROZEN) in r.violations


def test_dotdot_reentry_alias_of_frozen_is_forbidden():
    """``backend/../backend/main.py`` normalizes onto the frozen file (D7) — forbidden."""
    own = _ownership()
    authz = WriteAuthorization(own, WriteGrant.for_qa("eve", own))
    assert authz.authorize("backend/../backend/main.py") == AuthzDecision.FORBIDDEN_FROZEN


def test_byte_identical_frozen_emission_is_still_an_attempted_violation():
    """The subtle D7/atomicity case: emitting a frozen path with content BYTE-IDENTICAL to the
    scaffold is still an *attempted emission* (the producer tried to own a frozen path) — recorded,
    distinct from not emitting it at all (which yields no evidence, see the 3.1 clean-response test).
    Restore is a content no-op here, but the attempt is not free."""
    rec = _record()
    scaffold_main = _frozen_content(rec, "backend/main.py")
    enforced, evidence = _enforce(
        [{"name": "backend/main.py", "content": scaffold_main}], rec, _env()
    )
    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.violation_code == "frozen_path_emission"
    assert ev.expected_sha256 == ev.attempted_sha256  # byte-identical, yet still recorded
    assert enforced[0]["content"] == scaffold_main  # restore == no-op content-wise


def test_symlink_escaping_the_workspace_is_not_written(tmp_path):
    """D7: a pre-existing symlink that resolves OUTSIDE the workspace is not written through
    (``resolve()`` + ``relative_to``). (A symlink onto a frozen path *inside* the workspace is out
    of the reachable model — the scaffold flow never creates symlinks, and authorization is keyed on
    the emitted name.)"""
    outside = tmp_path / "outside"
    outside.mkdir()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "escape").symlink_to(outside / "secret.txt")
    r = materialize([{"name": "escape", "content": "pwned"}], ws)
    assert r.written == ()  # resolved outside → skipped
    assert not (outside / "secret.txt").exists()


# --------------------------------------------------------------------------- #
# 4.2 — pf-26 replay
# --------------------------------------------------------------------------- #


def test_pf26_replay_qa_cannot_mutate_main_py():
    """The pf-26 pattern: a QA correction emitting the frozen ``backend/main.py`` alongside its
    corrected test suite CANNOT mutate main.py. main.py is restored to the scaffold (which imports
    the router); the corrected suite survives. (The suite reaching execution through the ``client``
    fixture is the harness_boundary check, covered in test_acceptance_checks.py.)"""
    rec = _record()
    enforced, evidence = _enforce(
        [
            {
                "name": "backend/tests/test_runs.py",
                "content": "def test_create(client):\n    ...\n",
            },
            {"name": "backend/main.py", "content": "app = ClobberApp()  # pf-26\n"},
        ],
        rec,
        _env("qa.test"),
    )
    by = {a["name"]: a["content"] for a in enforced}
    assert "from .routes import router" in by["backend/main.py"]  # clobber gone, scaffold restored
    assert "backend/tests/test_runs.py" in by  # corrected suite kept
    assert [e.violation_code for e in evidence] == ["frozen_path_emission"]
    assert evidence[0].disposition == "restored"


# --------------------------------------------------------------------------- #
# 4.3 — expander-change replay (restoration uses the persisted bound bytes, D2)
# --------------------------------------------------------------------------- #


def _pinned_record(main_content: str) -> BoundScaffoldRecord:
    """A bound record whose frozen main.py is a sentinel decoupled from the live expander."""
    return BoundScaffoldRecord(
        run_id="r",
        attempt_id="a",
        stack="fullstack_fastapi_react",
        manifest_hash="mh",
        contract_hash="ch",
        expander_id="pinned-v1",
        created_at="t",
        frozen=(
            FrozenArtifact(
                path="backend/main.py",
                sha256=hashlib.sha256(main_content.encode()).hexdigest(),
                content=main_content,
            ),
        ),
        fill_slots=("backend/routes.py",),
        qa_namespace=("backend/tests/",),
    )


def test_restore_uses_bound_bytes_not_the_live_expander():
    """4.3: restoration is authorized by the PERSISTED bound bytes (D2), never a re-expansion. A
    record pinned to sentinel bytes restores to THOSE bytes — proving the record, not whatever the
    current expander asset would emit, is the restore authority."""
    pinned = "# PINNED v1 — not what today's expander emits\napp = 1\n"
    rec = _pinned_record(pinned)
    enforced, evidence = _enforce(
        [{"name": "backend/main.py", "content": "TAMPER = 999\n"}], rec, _env()
    )
    assert enforced[0]["content"] == pinned
    assert evidence[0].expected_sha256 == hashlib.sha256(pinned.encode()).hexdigest()


def test_restore_frozen_files_rewrites_from_the_record_on_disk(tmp_path):
    """4.3: ``restore_frozen_files`` overwrites a live/expander-produced file on disk with the
    record's pinned bytes — same D2 authority, at the filesystem seam."""
    pinned = "PINNED_ON_DISK_V1\n"
    rec = _pinned_record(pinned)
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "main.py").write_text("LIVE_EXPANDER_OUTPUT_V2\n")
    restored = restore_frozen_files(tmp_path, rec)
    assert "backend/main.py" in restored
    assert (tmp_path / "backend" / "main.py").read_text() == pinned
