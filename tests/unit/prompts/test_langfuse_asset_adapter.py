"""
Unit tests for LangfusePromptAssetAdapter (SIP-0084).

Uses the fake SDK injection pattern (see MEMORY.md) to mock the langfuse
SDK without requiring it installed.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from typing import Any

import pytest

from squadops.prompts.asset_models import AssetVersionInfo, ResolvedAsset
from squadops.prompts.exceptions import (
    PromptAssetNotFoundError,
    PromptRegistryUnavailableError,
)


@dataclass
class FakePrompt:
    """Simulates a Langfuse prompt object."""

    prompt: str
    version: int
    label: str = "production"


@pytest.fixture(autouse=True)
def _inject_fake_langfuse():
    """Inject a fake langfuse module into sys.modules before each test."""
    fake_langfuse = types.ModuleType("langfuse")

    class FakeLangfuse:
        def __init__(self, **kwargs: Any):
            self._prompts: dict[str, dict[str, FakePrompt]] = {}
            self._kwargs = kwargs

        def register_prompt(self, name: str, prompt: FakePrompt):
            if name not in self._prompts:
                self._prompts[name] = {}
            self._prompts[name][prompt.label] = prompt

        def get_prompt(self, name: str, label: str = "production"):
            if name in self._prompts and label in self._prompts[name]:
                return self._prompts[name][label]
            raise Exception(f"Prompt not found: {name} (404)")

    fake_langfuse.Langfuse = FakeLangfuse
    sys.modules["langfuse"] = fake_langfuse

    # Clear adapter module from cache so it re-imports langfuse
    sys.modules.pop("adapters.prompts.langfuse_asset_adapter", None)

    yield

    # Cleanup
    sys.modules.pop("langfuse", None)
    sys.modules.pop("adapters.prompts.langfuse_asset_adapter", None)


def _make_adapter(**kwargs):
    """Create adapter after fake SDK injection."""
    from adapters.prompts.langfuse_asset_adapter import LangfusePromptAssetAdapter

    return LangfusePromptAssetAdapter(
        public_key="pk-test", secret_key="sk-test", host="http://localhost:3001", **kwargs
    )


def _get_client(adapter):
    """Access the internal Langfuse client for test setup."""
    return adapter._client


class TestConstruction:
    """Adapter construction and SDK availability."""

    def test_construction_with_fake_sdk(self):
        adapter = _make_adapter()
        assert adapter is not None

    def test_missing_sdk_raises_registry_unavailable(self):
        # Block the real langfuse import by injecting a module that raises ImportError
        fake_broken = types.ModuleType("langfuse")
        fake_broken.Langfuse = None  # type: ignore[attr-defined]

        # Simulate missing SDK: remove langfuse and adapter from cache,
        # then inject a broken module that makes the adapter's import fail
        sys.modules.pop("langfuse", None)
        sys.modules.pop("adapters.prompts.langfuse_asset_adapter", None)

        import builtins

        _real_import = builtins.__import__

        def _block_langfuse(name, *args, **kwargs):
            if name == "langfuse" or name.startswith("langfuse."):
                raise ImportError("Simulated: langfuse not installed")
            return _real_import(name, *args, **kwargs)

        builtins.__import__ = _block_langfuse
        try:
            with pytest.raises(PromptRegistryUnavailableError, match="not installed"):
                from adapters.prompts.langfuse_asset_adapter import LangfusePromptAssetAdapter

                LangfusePromptAssetAdapter(
                    public_key="pk", secret_key="sk", host="http://localhost:3001"
                )
        finally:
            builtins.__import__ = _real_import
            sys.modules.pop("adapters.prompts.langfuse_asset_adapter", None)


class TestResolveSystemFragment:
    """System fragment resolution via Langfuse."""

    async def test_resolve_fragment_without_role(self):
        adapter = _make_adapter()
        client = _get_client(adapter)
        client.register_prompt(
            "identity",
            FakePrompt(prompt="You are an AI agent.", version=3, label="production"),
        )

        result = await adapter.resolve_system_fragment("identity")
        assert isinstance(result, ResolvedAsset)
        assert result.content == "You are an AI agent."
        assert result.version == "3"
        assert result.content_hash == ResolvedAsset.compute_hash("You are an AI agent.")

    async def test_resolve_fragment_with_role(self):
        adapter = _make_adapter()
        client = _get_client(adapter)
        client.register_prompt(
            "identity--dev",
            FakePrompt(prompt="You are Neo.", version=1, label="production"),
        )

        result = await adapter.resolve_system_fragment("identity", role="dev")
        assert result.asset_id == "identity--dev"
        assert "Neo" in result.content

    async def test_missing_fragment_raises(self):
        adapter = _make_adapter()
        with pytest.raises(PromptAssetNotFoundError, match="nonexistent"):
            await adapter.resolve_system_fragment("nonexistent")


class TestResolveRequestTemplate:
    """Request template resolution via Langfuse."""

    async def test_resolve_template(self):
        adapter = _make_adapter()
        client = _get_client(adapter)
        client.register_prompt(
            "request.cycle_task_base",
            FakePrompt(prompt="## PRD\n\n{{prd}}", version=2, label="staging"),
        )

        result = await adapter.resolve_request_template(
            "request.cycle_task_base", environment="staging"
        )
        assert result.version == "2"
        assert "{{prd}}" in result.content
        assert result.environment == "staging"

    async def test_missing_template_raises(self):
        adapter = _make_adapter()
        with pytest.raises(PromptAssetNotFoundError):
            await adapter.resolve_request_template("request.nonexistent")


class TestGetAssetVersion:
    """Version metadata retrieval."""

    async def test_returns_version_info(self):
        adapter = _make_adapter()
        client = _get_client(adapter)
        client.register_prompt(
            "request.cycle_task_base",
            FakePrompt(prompt="content", version=5, label="production"),
        )

        info = await adapter.get_asset_version("request.cycle_task_base")
        assert isinstance(info, AssetVersionInfo)
        assert info.version == "5"

    async def test_returns_none_for_unknown(self):
        adapter = _make_adapter()
        info = await adapter.get_asset_version("unknown.asset")
        assert info is None
