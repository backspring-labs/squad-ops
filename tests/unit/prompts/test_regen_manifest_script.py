"""Tests for regen_fragment_manifest.py's anchored write path (#451).

The bug this catches: the write path replaced the stored hash value with a
bare global ``str.replace`` across the whole manifest. A degenerate stored
value (a placeholder like ``'0'``) matched every zero character in the file —
version, timestamp, and every other fragment's hash were destroyed (observed
live 2026-07-15 while registering ``task_type.qa.test``).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_capabilities]

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "regen_fragment_manifest.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("regen_fragment_manifest", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["regen_fragment_manifest"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A two-fragment sandbox: one current entry, one placeholder-hash entry."""
    frag_dir = tmp_path / "fragments"
    (frag_dir / "shared" / "task_type").mkdir(parents=True)

    good = frag_dir / "shared" / "task_type" / "task_type.good.md"
    good.write_text("---\nfragment_id: task_type.good\n---\nGood content here.\n")
    new = frag_dir / "shared" / "task_type" / "task_type.new.md"
    new.write_text("---\nfragment_id: task_type.new\n---\nNew content here.\n")

    mod = _load_script()
    from adapters.prompts.filesystem import FileSystemPromptRepository

    good_hash = FileSystemPromptRepository.hash_fragment_file(good)

    manifest = frag_dir / "manifest.yaml"
    manifest.write_text(
        "version: 0.9.99\n"
        "updated_at: '2026-07-15T00:00:00.000000Z'\n"
        "fragments:\n"
        "- fragment_id: task_type.good\n"
        "  path: shared/task_type/task_type.good.md\n"
        "  layer: task_type\n"
        "  roles:\n"
        "  - qa\n"
        f"  sha256: {good_hash}\n"
        "- fragment_id: task_type.new\n"
        "  path: shared/task_type/task_type.new.md\n"
        "  layer: task_type\n"
        "  roles:\n"
        "  - qa\n"
        "  sha256: '0'\n"  # the degenerate placeholder that triggered #451
        "manifest_hash: placeholder\n"
    )

    monkeypatch.setattr(mod, "FRAGMENTS_DIR", frag_dir)
    monkeypatch.setattr(mod, "MANIFEST_PATH", manifest)
    return mod, manifest, good_hash


class TestAnchoredWrite:
    def test_placeholder_hash_does_not_corrupt_other_entries(self, sandbox):
        mod, manifest, good_hash = sandbox
        rc = mod.write()
        assert rc == 0
        raw = manifest.read_text()
        # The pre-#451 bug: every '0' in the file became the new 64-char hash.
        assert "version: 0.9.99" in raw  # version intact
        assert "'2026-07-15T00:00:00.000000Z'" in raw  # timestamp intact
        assert f"sha256: {good_hash}" in raw  # sibling hash intact
        assert "sha256: '0'" not in raw  # placeholder actually updated

    def test_write_is_idempotent(self, sandbox):
        mod, manifest, _ = sandbox
        assert mod.write() == 0
        first = manifest.read_text()
        assert mod.write() == 0
        assert manifest.read_text() == first

    def test_check_passes_after_write(self, sandbox):
        mod, _, _ = sandbox
        assert mod.write() == 0
        assert mod.check() == 0


def test_a_stored_hash_that_prefixes_another_entrys_updates_only_its_own_entry(
    tmp_path, monkeypatch
):
    """#1639. Bug this catches: the rewrite matched ``sha256: <stored>`` as text, so a
    placeholder ``'0'`` hit an EARLIER entry whose hash starts with ``0`` and rewrote that one,
    leaving the file inconsistent while ``manifest_hash`` matched it. The qa and generalist
    identity entries were in exactly this order when the generalist fragment was registered."""
    frag_dir = tmp_path / "fragments"
    (frag_dir / "roles").mkdir(parents=True)
    early = frag_dir / "roles" / "qa.md"
    early.write_text("---\nfragment_id: identity\n---\nQA.\n")
    late = frag_dir / "roles" / "generalist.md"
    late.write_text("---\nfragment_id: identity\n---\nGeneralist.\n")
    mod = _load_script()
    from adapters.prompts.filesystem import FileSystemPromptRepository

    early_hash = FileSystemPromptRepository.hash_fragment_file(early)
    # The earlier entry's stored hash is current and begins with the placeholder's digit.
    early_stored = "0" + early_hash[1:]
    manifest = frag_dir / "manifest.yaml"
    manifest.write_text(
        "version: 0.9.99\n"
        "fragments:\n"
        "- fragment_id: identity\n"
        "  path: roles/qa.md\n"
        "  layer: identity\n"
        "  roles:\n"
        "  - qa\n"
        f"  sha256: {early_stored}\n"
        "- fragment_id: identity\n"
        "  path: roles/generalist.md\n"
        "  layer: identity\n"
        "  roles:\n"
        "  - generalist\n"
        "  sha256: '0'\n"
        "manifest_hash: placeholder\n"
    )
    monkeypatch.setattr(mod, "FRAGMENTS_DIR", frag_dir)
    monkeypatch.setattr(mod, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(
        FileSystemPromptRepository,
        "hash_fragment_file",
        staticmethod(lambda p: early_stored if p.name == "qa.md" else "f" * 64),
    )

    assert mod.write() == 0

    raw = manifest.read_text()
    assert f"sha256: {early_stored}\n" in raw
    assert f"sha256: {'f' * 64}\n" in raw
    assert "sha256: '0'" not in raw
    assert mod.check() == 0


def test_an_entry_with_no_sha256_line_is_refused():
    """Bug this catches: a drifted entry the rewrite cannot place reported as updated."""
    mod = _load_script()
    raw = "fragments:\n- fragment_id: x\n  path: a.md\n  layer: identity\n"
    assert mod._rewrite_entry_hash(raw, "a.md", "f" * 64) is None
    assert mod._rewrite_entry_hash(raw, "b.md", "f" * 64) is None
