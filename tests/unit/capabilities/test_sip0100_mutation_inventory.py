"""SIP-0100 Task 0.1 — workspace mutation-path inventory (characterization).

Pins the finding documented in ``docs/plans/SIP-0100-phase-0-mutation-path-inventory.md``:
there are TWO independent workspace materializers, and the qa.test one bypasses
``materialize_artifacts``. These tests capture the *pre-enforcement* behavior so Phase 2
(authorize -> materialize -> verify) has a precise baseline to flip, and act as a
completeness ledger so a newly-added third materializer is noticed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from squadops.capabilities.handlers.test_runner import _materialize_files
from squadops.cycles.patch_verification import materialize_artifacts

pytestmark = [pytest.mark.domain_capabilities]

# A scaffold-frozen path (SIP-0099/0100): fill/repair producers must never rewrite it.
_FROZEN_PATH = "backend/main.py"


def test_test_runner_materializer_writes_a_frozen_path_unguarded():
    """BYPASS baseline: the qa.test workspace materializer (``_materialize_files``) writes
    a frozen path with no ownership check today — this is the pf-26 path (pytest collection
    ran the tampered file). Phase 2 must make this rejected."""
    with tempfile.TemporaryDirectory() as ws:
        _materialize_files(ws, [{"path": _FROZEN_PATH, "content": "TAMPERED = 1\n"}])
        written = Path(ws) / _FROZEN_PATH
        assert written.read_text() == "TAMPERED = 1\n"  # unguarded today


def test_patch_verification_materializer_writes_a_frozen_path_unguarded():
    """BYPASS baseline (other seam): ``materialize_artifacts`` likewise writes a frozen path
    unguarded today. Both materializers must gain the same authorization in Phase 2 — hence the
    inventory's 'unify' recommendation."""
    with tempfile.TemporaryDirectory() as ws:
        materialize_artifacts([{"name": _FROZEN_PATH, "content": "TAMPERED = 1\n"}], Path(ws))
        written = Path(ws) / _FROZEN_PATH
        assert written.read_text() == "TAMPERED = 1\n"  # unguarded today


def test_the_two_known_workspace_materializers_are_callable():
    """Completeness ledger: these are the ONLY two workspace materializers Phase 2 must cover
    (per the 0.1 inventory). They even take different artifact shapes ({'path'} vs {'name'}),
    which is why Phase 2 unifies them behind one authorization-aware seam. If a third workspace
    materializer is introduced, update the inventory doc AND this ledger so it is not left
    unenforced."""
    assert callable(_materialize_files)  # {'path', 'content'} — qa.test pytest/frontend workspace
    assert callable(materialize_artifacts)  # {'name', 'content'} — typed-acc / patch-verify workspace
