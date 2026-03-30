"""
Unit tests for prompt asset source factory (SIP-0084).

Verifies provider selection, default paths, and the no-silent-fallback rule.
"""

import builtins
import sys

import pytest

from adapters.prompts.factory import create_prompt_asset_source
from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.ports.prompts.asset_source import PromptAssetSourcePort


class TestCreatePromptAssetSource:
    """Factory selection tests."""

    def test_filesystem_is_default(self, tmp_path):
        adapter = create_prompt_asset_source(
            provider="filesystem",
            fragments_path=tmp_path,
            templates_path=tmp_path,
        )
        assert isinstance(adapter, FilesystemPromptAssetAdapter)
        assert isinstance(adapter, PromptAssetSourcePort)

    def test_default_provider_is_filesystem(self):
        """Omitting provider defaults to filesystem."""
        adapter = create_prompt_asset_source()
        assert isinstance(adapter, FilesystemPromptAssetAdapter)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown prompt asset source provider"):
            create_prompt_asset_source(provider="s3")

    def test_langfuse_provider_requires_sdk(self):
        """Langfuse provider raises if SDK not available."""
        from squadops.prompts.exceptions import PromptDomainError

        # Block langfuse import to simulate missing SDK
        _real_import = builtins.__import__

        def _block_langfuse(name, *args, **kwargs):
            if name == "langfuse" or name.startswith("langfuse."):
                raise ImportError("Simulated: langfuse not installed")
            return _real_import(name, *args, **kwargs)

        sys.modules.pop("langfuse", None)
        sys.modules.pop("adapters.prompts.langfuse_asset_adapter", None)
        builtins.__import__ = _block_langfuse
        try:
            with pytest.raises((PromptDomainError, ImportError)):
                create_prompt_asset_source(
                    provider="langfuse",
                    public_key="pk-test",
                    secret_key="sk-test",
                )
        finally:
            builtins.__import__ = _real_import
            sys.modules.pop("adapters.prompts.langfuse_asset_adapter", None)
