"""Tests for contract_gate.py emit mode (SIP-0098 98.5 contract seeding).

The emitted file is the artifact operators ingest and seed as ``contract_ref`` —
wrong bytes here mean every bind-mode cycle binds against a contract the CI gate
never validated, so the tests pin byte-identity with the canonical emitter and
the no-file-on-failure guarantee.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold_contract import emit_contract_yaml

pytestmark = [pytest.mark.domain_capabilities]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GATE = _REPO_ROOT / "scripts" / "dev" / "contract_gate.py"
_CANONICAL_MANIFEST = _REPO_ROOT / "examples" / "03_group_run" / "interface_manifest.yaml"


def _run_emit(manifest: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_GATE), "emit", "--manifest", str(manifest), "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )


class TestEmitMode:
    def test_emitted_file_is_byte_identical_to_canonical_emission(self, tmp_path):
        # The seeded artifact must be exactly what the CI gate validated —
        # a divergent writer would seed an unvalidated contract.
        out = tmp_path / "verification_contract.yaml"
        proc = _run_emit(_CANONICAL_MANIFEST, out)
        assert proc.returncode == 0, proc.stdout + proc.stderr

        manifest = InterfaceManifest.from_yaml(_CANONICAL_MANIFEST.read_text(encoding="utf-8"))
        assert out.read_text(encoding="utf-8") == emit_contract_yaml(manifest)

    def test_reported_hash_matches_file_bytes(self, tmp_path):
        # The printed content_hash is what the yield baseline freezes; if it
        # doesn't match the ingested bytes, the baseline measures nothing.
        out = tmp_path / "verification_contract.yaml"
        proc = _run_emit(_CANONICAL_MANIFEST, out)
        assert proc.returncode == 0, proc.stdout + proc.stderr

        actual = hashlib.sha256(out.read_bytes()).hexdigest()
        assert actual in proc.stdout

    def test_unreadable_manifest_writes_nothing(self, tmp_path):
        # A garbage manifest must not leave a seedable file behind.
        bad = tmp_path / "broken.yaml"
        bad.write_text("kind: [unclosed", encoding="utf-8")
        out = tmp_path / "verification_contract.yaml"
        proc = _run_emit(bad, out)
        assert proc.returncode != 0
        assert not out.exists()
