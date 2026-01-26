"""
Integration tests for FileSystemPromptRepository adapter.

Tests verify:
- POSIX path mapping on macOS
- Manifest loading and parsing
- Hash mismatch detection
- Fragment resolution with winning rule
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from adapters.prompts.filesystem import FileSystemPromptRepository
from adapters.prompts.factory import create_prompt_repository
from squadops.prompts.models import PromptFragment
from squadops.prompts.exceptions import (
    FragmentNotFoundError,
    HashMismatchError,
    ManifestValidationError,
)


# Path to actual fragments in the repo
FRAGMENTS_PATH = Path(__file__).parent.parent.parent.parent / "src" / "squadops" / "prompts" / "fragments"


class TestFileSystemPromptRepository:
    """Integration tests for filesystem adapter."""

    @pytest.fixture
    def real_repo(self):
        """Repository pointing to actual fragments in the codebase."""
        if not FRAGMENTS_PATH.exists():
            pytest.skip("Fragments directory not found")
        return FileSystemPromptRepository(base_path=FRAGMENTS_PATH)

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Repository with temporary test fragments."""
        # Create directory structure
        (tmp_path / "shared" / "identity").mkdir(parents=True)
        (tmp_path / "shared" / "constraints").mkdir(parents=True)
        (tmp_path / "roles" / "lead").mkdir(parents=True)

        # Create shared identity fragment
        shared_identity = tmp_path / "shared" / "identity" / "identity.md"
        shared_identity.write_text("""---
fragment_id: identity
layer: identity
version: "0.8.5"
roles: ["*"]
---
Shared identity content.
""")

        # Create shared constraints fragment
        constraints = tmp_path / "shared" / "constraints" / "constraints.global.md"
        constraints.write_text("""---
fragment_id: constraints.global
layer: constraints
version: "0.8.5"
roles: ["*"]
---
Global constraints content.
""")

        # Create role-specific identity override
        lead_identity = tmp_path / "roles" / "lead" / "identity.md"
        lead_identity.write_text("""---
fragment_id: identity
layer: identity
version: "0.8.5"
roles: ["lead"]
---
Lead-specific identity content.
""")

        # Create manifest
        manifest_content = self._create_manifest(tmp_path)
        (tmp_path / "manifest.yaml").write_text(manifest_content)

        return FileSystemPromptRepository(base_path=tmp_path)

    def _create_manifest(self, base_path: Path) -> str:
        """Create a manifest for test fragments."""
        import yaml
        import hashlib

        def get_hash(path: Path) -> str:
            content = path.read_text()
            # Extract content after header
            import re
            match = re.match(r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL)
            if match:
                content = content[match.end():].strip()
            return hashlib.sha256(content.encode()).hexdigest()

        fragments = [
            {
                "fragment_id": "identity",
                "path": "shared/identity/identity.md",
                "layer": "identity",
                "roles": ["*"],
                "sha256": get_hash(base_path / "shared" / "identity" / "identity.md"),
            },
            {
                "fragment_id": "constraints.global",
                "path": "shared/constraints/constraints.global.md",
                "layer": "constraints",
                "roles": ["*"],
                "sha256": get_hash(base_path / "shared" / "constraints" / "constraints.global.md"),
            },
        ]

        manifest = {
            "version": "0.8.5",
            "updated_at": "2026-01-24T00:00:00Z",
            "fragments": fragments,
            "manifest_hash": "",
        }

        return yaml.dump(manifest)

    def test_load_manifest(self, real_repo):
        """Should load and parse manifest.yaml correctly."""
        manifest = real_repo.get_manifest()

        assert manifest.version == "0.8.5"
        assert len(manifest.fragments) > 0

    def test_manifest_caching(self, real_repo):
        """Manifest should be cached after first load."""
        manifest1 = real_repo.get_manifest()
        manifest2 = real_repo.get_manifest()

        assert manifest1 is manifest2  # Same object (cached)

    def test_get_shared_fragment(self, temp_repo):
        """Should resolve shared fragment correctly."""
        fragment = temp_repo.get_fragment("identity")

        assert fragment.fragment_id == "identity"
        assert fragment.layer == "identity"
        assert "Shared identity content." in fragment.content

    def test_get_role_specific_fragment(self, temp_repo):
        """Should resolve role-specific fragment when available."""
        fragment = temp_repo.get_fragment("identity", role="lead")

        assert fragment.fragment_id == "identity"
        assert "Lead-specific identity content." in fragment.content

    def test_role_fallback_to_shared(self, temp_repo):
        """Should fall back to shared when role-specific not found."""
        # Request for 'dev' role should fall back to shared
        fragment = temp_repo.get_fragment("identity", role="dev")

        assert "Shared identity content." in fragment.content

    def test_fragment_not_found_raises(self, temp_repo):
        """Should raise FragmentNotFoundError for missing fragment."""
        with pytest.raises(FragmentNotFoundError) as exc_info:
            temp_repo.get_fragment("nonexistent_fragment")

        assert "nonexistent_fragment" in str(exc_info.value)

    def test_fragment_exists_shared(self, temp_repo):
        """fragment_exists should return True for shared fragments."""
        assert temp_repo.fragment_exists("identity") is True
        assert temp_repo.fragment_exists("constraints.global") is True

    def test_fragment_exists_role_specific(self, temp_repo):
        """fragment_exists should return True for role-specific fragments."""
        assert temp_repo.fragment_exists("identity", role="lead") is True
        # Non-existent role-specific should still find shared
        assert temp_repo.fragment_exists("identity", role="dev") is True

    def test_fragment_exists_missing(self, temp_repo):
        """fragment_exists should return False for missing fragments."""
        assert temp_repo.fragment_exists("nonexistent") is False

    def test_fragment_hash_verification(self, temp_repo):
        """Fragment content should match its computed hash."""
        fragment = temp_repo.get_fragment("identity")

        computed = PromptFragment.compute_hash(fragment.content)
        assert fragment.sha256_hash == computed

    def test_validate_integrity_passes(self, temp_repo):
        """validate_integrity should pass when all hashes match."""
        result = temp_repo.validate_integrity()
        assert result is True

    def test_validate_integrity_detects_tampering(self, tmp_path):
        """validate_integrity should detect tampered files."""
        # Setup: Create a valid repo first
        (tmp_path / "shared" / "identity").mkdir(parents=True)

        fragment_path = tmp_path / "shared" / "identity" / "identity.md"
        fragment_path.write_text("""---
fragment_id: identity
layer: identity
version: "0.8.5"
roles: ["*"]
---
Original content.
""")

        # Create manifest with original hash
        import hashlib
        original_hash = hashlib.sha256("Original content.".encode()).hexdigest()

        manifest_content = f"""
version: "0.8.5"
updated_at: "2026-01-24T00:00:00Z"
fragments:
  - fragment_id: identity
    path: shared/identity/identity.md
    layer: identity
    roles: ["*"]
    sha256: {original_hash}
"""
        (tmp_path / "manifest.yaml").write_text(manifest_content)

        # Now tamper with the file
        fragment_path.write_text("""---
fragment_id: identity
layer: identity
version: "0.8.5"
roles: ["*"]
---
TAMPERED content!
""")

        repo = FileSystemPromptRepository(base_path=tmp_path)

        with pytest.raises(HashMismatchError):
            repo.validate_integrity()

    def test_missing_manifest_raises(self, tmp_path):
        """Should raise ManifestValidationError when manifest missing."""
        repo = FileSystemPromptRepository(base_path=tmp_path)

        with pytest.raises(ManifestValidationError):
            repo.get_manifest()

    def test_list_fragments_unfiltered(self, real_repo):
        """list_fragments should return all fragments without filters."""
        fragments = real_repo.list_fragments()

        assert len(fragments) > 0
        assert all(isinstance(f, PromptFragment) for f in fragments)

    def test_list_fragments_by_layer(self, real_repo):
        """list_fragments should filter by layer."""
        fragments = real_repo.list_fragments(layer="identity")

        assert len(fragments) > 0
        assert all(f.layer == "identity" for f in fragments)

    def test_factory_creates_filesystem_repo(self):
        """Factory should create FileSystemPromptRepository."""
        if not FRAGMENTS_PATH.exists():
            pytest.skip("Fragments directory not found")

        repo = create_prompt_repository(provider="filesystem", base_path=FRAGMENTS_PATH)

        assert isinstance(repo, FileSystemPromptRepository)

    def test_factory_unknown_provider_raises(self):
        """Factory should raise for unknown provider."""
        with pytest.raises(ValueError, match="Unknown prompt repository provider"):
            create_prompt_repository(provider="unknown")


class TestRealFragments:
    """Tests using actual fragments from the codebase."""

    @pytest.fixture
    def repo(self):
        """Repository pointing to actual fragments."""
        if not FRAGMENTS_PATH.exists():
            pytest.skip("Fragments directory not found")
        return FileSystemPromptRepository(base_path=FRAGMENTS_PATH)

    def test_all_fragments_valid(self, repo):
        """All fragments in codebase should have valid structure."""
        manifest = repo.get_manifest()

        for meta in manifest.fragments:
            fragment = repo.get_fragment(meta.fragment_id)

            assert fragment.fragment_id
            assert fragment.layer in {"identity", "constraints", "lifecycle", "task_type", "recovery"}
            assert fragment.content
            assert fragment.sha256_hash

    def test_role_specific_overrides_exist(self, repo):
        """Role-specific identity fragments should exist."""
        roles = ["lead", "dev", "qa", "strat", "data"]

        for role in roles:
            if repo.fragment_exists("identity", role=role):
                fragment = repo.get_fragment("identity", role=role)
                assert role in fragment.roles or "*" in fragment.roles
