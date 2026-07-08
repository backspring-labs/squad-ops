"""#327: FileSystemPromptRepository fails HARD on manifest_hash mismatch.

Bug class guarded: a deployed prompt set that doesn't match its pinned
manifest fingerprint used to produce one WARNING line at startup (evicted
from container logs within hours) and then run anyway — masked config
drift, the exact failure mode the hard rule about config-masking fallbacks
forbids. The loader must refuse to serve prompts from an unpinned set.
"""

from __future__ import annotations

import pytest

from adapters.prompts.filesystem import FileSystemPromptRepository
from squadops.prompts.exceptions import ManifestValidationError
from squadops.prompts.models import ManifestFragment, PromptManifest

_FRAGMENT = """---
fragment_id: identity.test
layer: identity
roles: ["*"]
---
Test fragment body.
"""


def _write_prompt_tree(base, *, manifest_hash: str | None):
    (base / "shared").mkdir(parents=True)
    frag_path = base / "shared" / "identity.test.md"
    frag_path.write_text(_FRAGMENT, encoding="utf-8")
    sha = FileSystemPromptRepository.hash_fragment_file(frag_path)

    if manifest_hash == "__valid__":
        fragments = (
            ManifestFragment(
                fragment_id="identity.test",
                path="shared/identity.test.md",
                layer="identity",
                roles=("*",),
                sha256=sha,
            ),
        )
        manifest_hash = PromptManifest.compute_manifest_hash("1.0.0", fragments)

    hash_line = f"manifest_hash: {manifest_hash}\n" if manifest_hash is not None else ""
    (base / "manifest.yaml").write_text(
        "version: 1.0.0\n"
        "updated_at: '2026-01-01'\n"
        f"{hash_line}"
        "fragments:\n"
        "  - fragment_id: identity.test\n"
        "    path: shared/identity.test.md\n"
        "    layer: identity\n"
        '    roles: ["*"]\n'
        f"    sha256: {sha}\n",
        encoding="utf-8",
    )
    return sha


class TestManifestHashHardFail:
    def test_stale_manifest_hash_raises_with_regen_pointer(self, tmp_path):
        """A pinned-but-wrong manifest_hash must raise ManifestValidationError
        (not warn-and-continue), and the message must tell the operator how
        to fix it."""
        # Letters keep YAML from parsing the scalar as an int (an all-digit
        # hash would load as a falsy 0 and skip verification entirely).
        _write_prompt_tree(tmp_path, manifest_hash="deadbeef" * 8)
        repo = FileSystemPromptRepository(base_path=tmp_path)

        with pytest.raises(ManifestValidationError) as exc_info:
            repo.get_manifest()

        msg = str(exc_info.value)
        assert "Manifest hash mismatch" in msg
        assert "regen_fragment_manifest.py --write" in msg

    def test_matching_manifest_hash_loads(self, tmp_path):
        """A correctly pinned manifest loads and serves fragments."""
        _write_prompt_tree(tmp_path, manifest_hash="__valid__")
        repo = FileSystemPromptRepository(base_path=tmp_path)

        fragment = repo.get_fragment("identity.test")
        assert fragment.content == "Test fragment body."

    def test_absent_manifest_hash_skips_verification(self, tmp_path):
        """No pinned hash → no verification (test fixtures and local trees
        that never pinned a fingerprint keep working)."""
        _write_prompt_tree(tmp_path, manifest_hash=None)
        repo = FileSystemPromptRepository(base_path=tmp_path)

        fragment = repo.get_fragment("identity.test")
        assert fragment.content == "Test fragment body."
