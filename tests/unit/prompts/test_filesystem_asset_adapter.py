"""
Unit tests for FilesystemPromptAssetAdapter (SIP-0084).

Tests use temporary directories with real files to verify filesystem
resolution, frontmatter parsing, and error handling.
"""

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.prompts.asset_models import AssetVersionInfo, ResolvedAsset
from squadops.prompts.exceptions import PromptAssetNotFoundError


@pytest.fixture()
def fragments_dir(tmp_path):
    """Create a minimal filesystem fragment structure with manifest."""
    base = tmp_path / "fragments"
    (base / "shared" / "identity").mkdir(parents=True)
    (base / "roles" / "dev").mkdir(parents=True)

    # Shared identity fragment
    (base / "shared" / "identity" / "identity.md").write_text(
        "---\nfragment_id: identity\nlayer: identity\nversion: '0.9.18'\nroles: ['*']\n---\n"
        "You are an AI agent.\n",
        encoding="utf-8",
    )

    # Role-specific identity
    (base / "roles" / "dev" / "identity.md").write_text(
        "---\nfragment_id: identity\nlayer: identity\nversion: '0.9.18'\nroles: ['dev']\n---\n"
        "You are Neo, a development agent.\n",
        encoding="utf-8",
    )

    # Manifest
    (base / "manifest.yaml").write_text(
        "version: '0.9.18'\n"
        "updated_at: '2026-01-01T00:00:00'\n"
        "manifest_hash: ''\n"
        "fragments:\n"
        "  - fragment_id: identity\n"
        "    path: shared/identity/identity.md\n"
        "    layer: identity\n"
        "    roles: ['*']\n"
        "    sha256: placeholder\n",
        encoding="utf-8",
    )
    return base


@pytest.fixture()
def templates_dir(tmp_path):
    """Create a minimal request templates directory."""
    base = tmp_path / "templates"
    base.mkdir()

    (base / "request.cycle_task_base.md").write_text(
        "---\n"
        "template_id: request.cycle_task_base\n"
        "version: '2'\n"
        "required_variables:\n"
        "  - prd\n"
        "  - prior_outputs\n"
        "  - role\n"
        "---\n"
        "## PRD\n\n{{prd}}\n\n## Prior Outputs\n\n{{prior_outputs}}\n\nRole: {{role}}\n",
        encoding="utf-8",
    )

    (base / "request.no_frontmatter.md").write_text(
        "Plain template without frontmatter.\n\n{{content}}\n",
        encoding="utf-8",
    )
    return base


@pytest.fixture()
def adapter(fragments_dir, templates_dir):
    return FilesystemPromptAssetAdapter(
        fragments_path=fragments_dir,
        templates_path=templates_dir,
    )


class TestResolveSystemFragment:
    """System fragment resolution via wrapped PromptRepository."""

    async def test_resolve_shared_fragment(self, adapter):
        result = await adapter.resolve_system_fragment("identity")
        assert isinstance(result, ResolvedAsset)
        assert "AI agent" in result.content
        assert result.asset_id == "identity"
        assert result.environment == "production"

    async def test_resolve_role_specific_fragment(self, adapter):
        result = await adapter.resolve_system_fragment("identity", role="dev")
        assert "Neo" in result.content

    async def test_missing_fragment_raises(self, adapter):
        with pytest.raises(PromptAssetNotFoundError) as exc_info:
            await adapter.resolve_system_fragment("nonexistent")
        assert "nonexistent" in str(exc_info.value)


class TestResolveRequestTemplate:
    """Request template resolution from filesystem."""

    async def test_resolve_template_with_frontmatter(self, adapter):
        result = await adapter.resolve_request_template("request.cycle_task_base")
        assert isinstance(result, ResolvedAsset)
        assert "{{prd}}" in result.content
        assert result.version == "2"
        assert result.content_hash == ResolvedAsset.compute_hash(result.content)

    async def test_resolve_template_without_frontmatter(self, adapter):
        result = await adapter.resolve_request_template("request.no_frontmatter")
        assert result.version == "1"  # default version
        assert "{{content}}" in result.content

    async def test_missing_template_raises(self, adapter):
        with pytest.raises(PromptAssetNotFoundError) as exc_info:
            await adapter.resolve_request_template("request.does_not_exist")
        assert "request.does_not_exist" in str(exc_info.value)

    async def test_content_hash_matches(self, adapter):
        result = await adapter.resolve_request_template("request.cycle_task_base")
        expected = ResolvedAsset.compute_hash(result.content)
        assert result.content_hash == expected


class TestGetAssetVersion:
    """Version metadata retrieval."""

    async def test_template_version(self, adapter):
        info = await adapter.get_asset_version("request.cycle_task_base")
        assert isinstance(info, AssetVersionInfo)
        assert info.version == "2"

    async def test_fragment_version(self, adapter):
        info = await adapter.get_asset_version("identity")
        assert isinstance(info, AssetVersionInfo)
        assert info.version == "0.9.18"

    async def test_unknown_asset_returns_none(self, adapter):
        info = await adapter.get_asset_version("nonexistent.asset")
        assert info is None
