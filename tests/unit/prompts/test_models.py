"""
Unit tests for prompt domain models.

Tests verify immutability, hash computation, and model behavior
without any filesystem or external dependencies.
"""

import pytest

from squadops.prompts.models import (
    AssembledPrompt,
    ManifestFragment,
    PromptFragment,
    PromptManifest,
)


class TestPromptFragment:
    """Tests for PromptFragment model."""

    def test_fragment_immutability(self):
        """Frozen dataclass should reject attribute modification."""
        fragment = PromptFragment(
            fragment_id="test.fragment",
            layer="identity",
            content="Test content",
            sha256_hash="abc123",
            roles=("*",),
            version="0.8.5",
        )

        with pytest.raises(AttributeError):
            fragment.content = "Modified content"

    def test_hash_computation(self):
        """Hash computation should be deterministic."""
        content = "Test content for hashing"
        hash1 = PromptFragment.compute_hash(content)
        hash2 = PromptFragment.compute_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_integrity_verification_passes(self):
        """Integrity check should pass when hash matches content."""
        content = "Test content"
        correct_hash = PromptFragment.compute_hash(content)

        fragment = PromptFragment(
            fragment_id="test",
            layer="identity",
            content=content,
            sha256_hash=correct_hash,
            roles=("*",),
            version="0.8.5",
        )

        assert fragment.verify_integrity() is True

    def test_integrity_verification_fails(self):
        """Integrity check should fail when hash mismatches."""
        fragment = PromptFragment(
            fragment_id="test",
            layer="identity",
            content="Test content",
            sha256_hash="wrong_hash",
            roles=("*",),
            version="0.8.5",
        )

        assert fragment.verify_integrity() is False

    def test_invalid_layer_rejected(self):
        """Invalid layer types should be rejected."""
        with pytest.raises(ValueError, match="Invalid layer"):
            PromptFragment(
                fragment_id="test",
                layer="invalid_layer",
                content="Test",
                sha256_hash="abc",
                roles=("*",),
                version="0.8.5",
            )

    def test_valid_layers_accepted(self):
        """All valid layer types should be accepted."""
        valid_layers = ["identity", "constraints", "lifecycle", "task_type", "recovery"]

        for layer in valid_layers:
            fragment = PromptFragment(
                fragment_id="test",
                layer=layer,
                content="Test",
                sha256_hash="abc",
                roles=("*",),
                version="0.8.5",
            )
            assert fragment.layer == layer


class TestAssembledPrompt:
    """Tests for AssembledPrompt model."""

    def test_assembled_prompt_immutability(self):
        """Frozen dataclass should reject attribute modification."""
        prompt = AssembledPrompt(
            content="Assembled content",
            fragment_hashes=("hash1", "hash2"),
            assembly_hash="final_hash",
            role="lead",
            hook="agent_start",
            version="0.8.5",
        )

        with pytest.raises(AttributeError):
            prompt.content = "Modified"

    def test_assembly_hash_computation(self):
        """Assembly hash should be deterministic."""
        content = "Assembled prompt content"
        hash1 = AssembledPrompt.compute_assembly_hash(content)
        hash2 = AssembledPrompt.compute_assembly_hash(content)

        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Different content should produce different hashes."""
        hash1 = AssembledPrompt.compute_assembly_hash("Content A")
        hash2 = AssembledPrompt.compute_assembly_hash("Content B")

        assert hash1 != hash2


class TestPromptManifest:
    """Tests for PromptManifest model."""

    def test_manifest_immutability(self):
        """Frozen dataclass should reject attribute modification."""
        manifest = PromptManifest(
            version="0.8.5",
            updated_at="2026-01-24T00:00:00Z",
            fragments=(),
            manifest_hash="abc123",
        )

        with pytest.raises(AttributeError):
            manifest.version = "0.9.0"

    def test_get_fragment_meta_found(self):
        """Should return fragment metadata when found."""
        frag = ManifestFragment(
            fragment_id="identity",
            path="shared/identity/identity.md",
            layer="identity",
            roles=("*",),
            sha256="abc123",
        )

        manifest = PromptManifest(
            version="0.8.5",
            updated_at="2026-01-24T00:00:00Z",
            fragments=(frag,),
            manifest_hash="def456",
        )

        result = manifest.get_fragment_meta("identity")
        assert result is not None
        assert result.fragment_id == "identity"

    def test_get_fragment_meta_not_found(self):
        """Should return None when fragment not found."""
        manifest = PromptManifest(
            version="0.8.5",
            updated_at="2026-01-24T00:00:00Z",
            fragments=(),
            manifest_hash="def456",
        )

        result = manifest.get_fragment_meta("nonexistent")
        assert result is None

    def test_get_fragments_by_layer(self):
        """Should filter fragments by layer."""
        frags = (
            ManifestFragment("id1", "p1", "identity", ("*",), "h1"),
            ManifestFragment("id2", "p2", "constraints", ("*",), "h2"),
            ManifestFragment("id3", "p3", "identity", ("*",), "h3"),
        )

        manifest = PromptManifest("0.8.5", "", frags, "")

        identity_frags = manifest.get_fragments_by_layer("identity")
        assert len(identity_frags) == 2
        assert all(f.layer == "identity" for f in identity_frags)

    def test_get_fragments_by_role(self):
        """Should filter fragments by role, including shared."""
        frags = (
            ManifestFragment("id1", "p1", "identity", ("*",), "h1"),  # shared
            ManifestFragment("id2", "p2", "identity", ("lead",), "h2"),  # lead only
            ManifestFragment("id3", "p3", "identity", ("dev",), "h3"),  # dev only
        )

        manifest = PromptManifest("0.8.5", "", frags, "")

        lead_frags = manifest.get_fragments_by_role("lead")
        assert len(lead_frags) == 2  # shared + lead-specific

    def test_manifest_hash_deterministic(self):
        """Manifest hash should be deterministic given same inputs."""
        frags = (
            ManifestFragment("id1", "p1", "identity", ("*",), "hash1"),
            ManifestFragment("id2", "p2", "constraints", ("*",), "hash2"),
        )

        hash1 = PromptManifest.compute_manifest_hash("0.8.5", frags)
        hash2 = PromptManifest.compute_manifest_hash("0.8.5", frags)

        assert hash1 == hash2
