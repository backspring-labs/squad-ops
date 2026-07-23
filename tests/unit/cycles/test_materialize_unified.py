"""SIP-0100 Task 2.2 — the single unified workspace materializer."""

from __future__ import annotations

from pathlib import Path

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.bound_scaffold_record import build_bound_record
from squadops.cycles.patch_verification import materialize
from squadops.cycles.write_authorization import (
    WorkspaceOwnership,
    WriteAuthorization,
    WriteGrant,
)

_MANIFEST = Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"


def _qa_authorization() -> WriteAuthorization:
    rec = build_bound_record(
        InterfaceManifest.from_yaml(_MANIFEST.read_text()),
        run_id="r",
        attempt_id="a",
        created_at="t",
    )
    own = WorkspaceOwnership.from_record(rec)
    return WriteAuthorization(own, WriteGrant.for_qa("eve", own))


def test_materialize_accepts_both_artifact_shapes(tmp_path):
    """The two materializers used {name} vs {path} (0.1); the unified one accepts either."""
    r = materialize(
        [{"name": "a.txt", "content": "A"}, {"path": "b.txt", "content": "B"}], tmp_path
    )
    assert r.authorized and set(r.written) == {"a.txt", "b.txt"}
    assert (tmp_path / "a.txt").read_text() == "A"
    assert (tmp_path / "b.txt").read_text() == "B"


def test_no_authorization_writes_everything_todays_behavior(tmp_path):
    r = materialize([{"path": "backend/main.py", "content": "x"}], tmp_path)
    assert r.authorized and r.written == ("backend/main.py",)
    assert (tmp_path / "backend" / "main.py").exists()


def test_authorized_qa_file_is_written(tmp_path):
    r = materialize(
        [{"path": "backend/tests/t.py", "content": "def test_x(): pass\n"}],
        tmp_path,
        authorization=_qa_authorization(),
    )
    assert r.authorized and (tmp_path / "backend" / "tests" / "t.py").exists()


def test_frozen_in_response_rejects_whole_response_writes_nothing(tmp_path):
    """pf-26: a repair emitting the frozen main.py alongside a valid test file — authorize BEFORE
    write, response-atomic: NOTHING is written (not even the valid file), reason recorded."""
    r = materialize(
        [
            {"path": "backend/tests/t.py", "content": "ok"},
            {"path": "backend/main.py", "content": "TAMPERED = 1"},
        ],
        tmp_path,
        authorization=_qa_authorization(),
    )
    assert not r.authorized
    assert not r.written
    assert not (tmp_path / "backend" / "tests" / "t.py").exists()  # valid file NOT written either
    assert not (tmp_path / "backend" / "main.py").exists()
    assert ("backend/main.py", "frozen_path_emission") in r.rejected


def test_path_safety_skips_absolute_and_escape(tmp_path):
    r = materialize(
        [{"name": "/etc/x", "content": "x"}, {"name": "ok.txt", "content": "y"}], tmp_path
    )
    assert r.written == ("ok.txt",)
    assert (tmp_path / "ok.txt").exists()


# --------------------------------------------------------------------------- #
# SIP-0100 Task 2.4 (D4) — post-write frozen-integrity verify + restore
# --------------------------------------------------------------------------- #


def _bound_record():
    return build_bound_record(
        InterfaceManifest.from_yaml(_MANIFEST.read_text()),
        run_id="r",
        attempt_id="a",
        created_at="t",
    )


def test_verify_frozen_integrity_clean_then_detects_tamper_then_restores(tmp_path):
    from squadops.cycles.patch_verification import (
        restore_frozen_files,
        verify_frozen_integrity,
    )

    record = _bound_record()
    materialize([{"name": fa.path, "content": fa.content} for fa in record.frozen], tmp_path)

    # Freshly materialized from the record → intact.
    assert verify_frozen_integrity(tmp_path, record) == ()

    # Tamper a frozen file (the pf-26 clobber) → detected as a fault.
    (tmp_path / "backend" / "main.py").write_text("TAMPERED = 1\n")
    faults = verify_frozen_integrity(tmp_path, record)
    assert "backend/main.py" in faults

    # Restore from the bound record (D2 authority) → intact again.
    restored = restore_frozen_files(tmp_path, record)
    assert "backend/main.py" in restored
    assert verify_frozen_integrity(tmp_path, record) == ()


def test_verify_frozen_integrity_flags_a_missing_frozen_file(tmp_path):
    from squadops.cycles.patch_verification import verify_frozen_integrity

    record = _bound_record()
    materialize([{"name": fa.path, "content": fa.content} for fa in record.frozen], tmp_path)
    (tmp_path / "backend" / "main.py").unlink()
    assert "backend/main.py" in verify_frozen_integrity(tmp_path, record)
