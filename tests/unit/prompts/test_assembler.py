"""
Unit tests for PromptAssembler domain service.

Tests verify assembly logic using mock repositories,
ensuring isolated domain logic without filesystem access.
"""

import pytest
from unittest.mock import Mock, MagicMock

from squadops.prompts.assembler import PromptAssembler
from squadops.prompts.models import PromptFragment, PromptManifest, ManifestFragment
from squadops.prompts.exceptions import (
    MandatoryLayerMissingError,
    HashMismatchError,
)
from squadops.ports.prompts.repository import PromptRepository


def create_mock_fragment(
    fragment_id: str,
    layer: str,
    content: str,
    roles: tuple[str, ...] = ("*",),
) -> PromptFragment:
    """Helper to create a valid fragment with computed hash."""
    sha256 = PromptFragment.compute_hash(content)
    return PromptFragment(
        fragment_id=fragment_id,
        layer=layer,
        content=content,
        sha256_hash=sha256,
        roles=roles,
        version="0.8.5",
    )


def create_mock_repository(fragments: dict[str, PromptFragment]) -> PromptRepository:
    """Create a mock repository with given fragments."""
    repo = Mock(spec=PromptRepository)

    def get_fragment(fragment_id: str, role: str | None = None) -> PromptFragment:
        # Try role-specific first
        role_key = f"{fragment_id}:{role}" if role else None
        if role_key and role_key in fragments:
            return fragments[role_key]
        # Fall back to shared
        if fragment_id in fragments:
            return fragments[fragment_id]
        raise KeyError(f"Fragment not found: {fragment_id}")

    def fragment_exists(fragment_id: str, role: str | None = None) -> bool:
        role_key = f"{fragment_id}:{role}" if role else None
        return (role_key and role_key in fragments) or fragment_id in fragments

    repo.get_fragment.side_effect = get_fragment
    repo.fragment_exists.side_effect = fragment_exists
    repo.get_manifest.return_value = PromptManifest(
        version="0.8.5",
        updated_at="2026-01-24T00:00:00Z",
        fragments=(),
        manifest_hash="test",
    )

    return repo


class TestPromptAssembler:
    """Tests for PromptAssembler domain service."""

    def test_assemble_basic_layers(self):
        """Should assemble identity and constraints layers."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "I am an agent."),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Be safe."
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result = assembler.assemble(role="dev", hook="agent_start")

        assert "I am an agent." in result.content
        assert "Be safe." in result.content
        assert result.role == "dev"
        assert result.hook == "agent_start"
        assert len(result.fragment_hashes) == 2

    def test_assemble_deterministic_output(self):
        """Same inputs should produce identical assembly hash."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "Identity text"),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints text"
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result1 = assembler.assemble(role="dev", hook="agent_start")
        result2 = assembler.assemble(role="dev", hook="agent_start")

        assert result1.assembly_hash == result2.assembly_hash
        assert result1.fragment_hashes == result2.fragment_hashes

    def test_assemble_with_lifecycle_layer(self):
        """Should include lifecycle layer when available."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "Identity"),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
            "lifecycle.agent_start": create_mock_fragment(
                "lifecycle.agent_start", "lifecycle", "Starting up..."
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result = assembler.assemble(role="dev", hook="agent_start")

        assert "Starting up..." in result.content
        assert len(result.fragment_hashes) == 3

    def test_assemble_with_task_type(self):
        """Should include task_type layer when provided."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "Identity"),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
            "task_type.code_generate": create_mock_fragment(
                "task_type.code_generate", "task_type", "Generate code..."
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result = assembler.assemble(
            role="dev", hook="task_execute", task_type="code_generate"
        )

        assert "Generate code..." in result.content

    def test_assemble_with_recovery(self):
        """Should include recovery layer when flag is True."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "Identity"),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
            "recovery": create_mock_fragment("recovery", "recovery", "Recovery mode active."),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result = assembler.assemble(role="dev", hook="task_execute", recovery=True)

        assert "Recovery mode active." in result.content

    def test_assemble_skips_recovery_when_false(self):
        """Should not include recovery layer when flag is False."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "Identity"),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
            "recovery": create_mock_fragment("recovery", "recovery", "Recovery mode active."),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result = assembler.assemble(role="dev", hook="task_execute", recovery=False)

        assert "Recovery mode active." not in result.content

    def test_role_specific_override(self):
        """Role-specific fragment should override shared fragment."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "Shared identity"),
            "identity:lead": create_mock_fragment(
                "identity", "identity", "Lead-specific identity", roles=("lead",)
            ),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result = assembler.assemble(role="lead", hook="agent_start")

        assert "Lead-specific identity" in result.content
        assert "Shared identity" not in result.content

    def test_missing_mandatory_layer_raises(self):
        """Missing mandatory layer should raise MandatoryLayerMissingError."""
        fragments = {
            # Missing identity layer
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        with pytest.raises(MandatoryLayerMissingError) as exc_info:
            assembler.assemble(role="dev", hook="agent_start")

        assert exc_info.value.layer == "identity"
        assert exc_info.value.role == "dev"

    def test_hash_mismatch_raises(self):
        """Fragment with wrong hash should raise HashMismatchError."""
        # Create fragment with incorrect hash
        bad_fragment = PromptFragment(
            fragment_id="identity",
            layer="identity",
            content="Identity content",
            sha256_hash="wrong_hash_value",
            roles=("*",),
            version="0.8.5",
        )

        fragments = {
            "identity": bad_fragment,
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        with pytest.raises(HashMismatchError) as exc_info:
            assembler.assemble(role="dev", hook="agent_start")

        assert exc_info.value.fragment_id == "identity"

    def test_layer_ordering(self):
        """Layers should be concatenated in correct order."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "[IDENTITY]"),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "[CONSTRAINTS]"
            ),
            "lifecycle.test": create_mock_fragment(
                "lifecycle.test", "lifecycle", "[LIFECYCLE]"
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result = assembler.assemble(role="dev", hook="test")

        # Verify order: identity -> constraints -> lifecycle
        identity_pos = result.content.find("[IDENTITY]")
        constraints_pos = result.content.find("[CONSTRAINTS]")
        lifecycle_pos = result.content.find("[LIFECYCLE]")

        assert identity_pos < constraints_pos < lifecycle_pos

    def test_get_system_prompt(self):
        """get_system_prompt should use agent_start hook."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "Identity"),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
            "lifecycle.agent_start": create_mock_fragment(
                "lifecycle.agent_start", "lifecycle", "Starting..."
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        result = assembler.get_system_prompt(role="lead")

        assert result.hook == "agent_start"
        assert "Starting..." in result.content

    def test_get_version(self):
        """get_version should return manifest version."""
        fragments = {
            "identity": create_mock_fragment("identity", "identity", "Identity"),
            "constraints.global": create_mock_fragment(
                "constraints.global", "constraints", "Constraints"
            ),
        }
        repo = create_mock_repository(fragments)
        assembler = PromptAssembler(repo)

        version = assembler.get_version()

        assert version == "0.8.5"
