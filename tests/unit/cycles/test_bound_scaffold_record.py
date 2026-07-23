"""SIP-0100 Task 0.3 — bound scaffold ownership record (plan D2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord, build_bound_record

pytestmark = [pytest.mark.domain_cycles] if hasattr(pytest.mark, "domain_cycles") else []

_MANIFEST = Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"


def _manifest() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_MANIFEST.read_text())


def test_bound_record_round_trips():
    rec = build_bound_record(
        _manifest(), run_id="run_x", attempt_id="a0", created_at="2026-07-23T00:00:00Z"
    )
    assert BoundScaffoldRecord.from_dict(rec.to_dict()) == rec


def test_bound_record_carries_bytes_for_every_frozen_path():
    """D2: restoration/replay authority is the persisted bytes — every frozen path has them, and
    the frozen surface matches the contract derivation (frozen source, not fill slots)."""
    rec = build_bound_record(_manifest(), run_id="r", attempt_id="a", created_at="t")
    assert rec.frozen_paths()  # scaffold has frozen files
    for p in rec.frozen_paths():
        # bytes present for every frozen path — `is not None`, since a legit empty file
        # (e.g. backend/__init__.py) has "" bytes, which must still be pinned for restoration.
        assert rec.frozen_bytes(p) is not None

    # main.py (the pf-26 file) is frozen and its bytes are pinned.
    assert "backend/main.py" in rec.frozen_paths()
    assert "from .routes import router" in rec.frozen_bytes("backend/main.py")
    # A fill slot is NOT frozen; the QA namespace + conftest are recorded/frozen.
    assert "backend/routes.py" not in rec.frozen_paths()
    assert "conftest.py" in rec.frozen_paths()  # SIP-0100 Piece A harness, auto-frozen
    assert rec.qa_namespace == ("backend/tests/", "frontend/src/tests/")


def test_frozen_bytes_normalizes_path_and_misses_return_none():
    rec = build_bound_record(_manifest(), run_id="r", attempt_id="a", created_at="t")
    assert rec.frozen_bytes("./backend/main.py") == rec.frozen_bytes("backend/main.py")
    assert rec.frozen_bytes("does/not/exist.py") is None
