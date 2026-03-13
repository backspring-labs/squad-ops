"""
Unit tests for PromptAssetSourcePort contract (SIP-0084).

Verifies that the port is a proper ABC and that its methods
enforce the expected signatures.
"""

import pytest

from squadops.ports.prompts.asset_source import PromptAssetSourcePort
from squadops.prompts.asset_models import AssetVersionInfo, ResolvedAsset


class TestPromptAssetSourcePortContract:
    """Port contract tests — cannot instantiate ABC directly."""

    def test_cannot_instantiate_abc(self):
        """ABC raises if not all methods implemented."""
        with pytest.raises(TypeError):
            PromptAssetSourcePort()

    def test_concrete_subclass_must_implement_all_methods(self):
        """Partial implementation still raises TypeError."""

        class Incomplete(PromptAssetSourcePort):
            async def resolve_system_fragment(self, fragment_id, role=None, environment="production"):
                pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_complete_subclass_instantiates(self):
        """Fully implemented subclass can be constructed."""

        class Complete(PromptAssetSourcePort):
            async def resolve_system_fragment(self, fragment_id, role=None, environment="production"):
                return ResolvedAsset(
                    asset_id=fragment_id,
                    content="test",
                    version="1",
                    environment=environment,
                    content_hash=ResolvedAsset.compute_hash("test"),
                )

            async def resolve_request_template(self, template_id, environment="production"):
                return ResolvedAsset(
                    asset_id=template_id,
                    content="test",
                    version="1",
                    environment=environment,
                    content_hash=ResolvedAsset.compute_hash("test"),
                )

            async def get_asset_version(self, asset_id):
                return None

        adapter = Complete()
        assert isinstance(adapter, PromptAssetSourcePort)

    async def test_resolve_system_fragment_returns_resolved_asset(self):
        """Verify return type contract."""

        class Stub(PromptAssetSourcePort):
            async def resolve_system_fragment(self, fragment_id, role=None, environment="production"):
                return ResolvedAsset(
                    asset_id=fragment_id,
                    content="content",
                    version="1",
                    environment=environment,
                    content_hash=ResolvedAsset.compute_hash("content"),
                )

            async def resolve_request_template(self, template_id, environment="production"):
                return ResolvedAsset(
                    asset_id=template_id, content="", version="1",
                    environment=environment, content_hash=ResolvedAsset.compute_hash(""),
                )

            async def get_asset_version(self, asset_id):
                return None

        result = await Stub().resolve_system_fragment("identity", role="dev")
        assert isinstance(result, ResolvedAsset)
        assert result.asset_id == "identity"

    async def test_resolve_request_template_returns_resolved_asset(self):
        """Verify return type contract for template resolution."""

        class Stub(PromptAssetSourcePort):
            async def resolve_system_fragment(self, fragment_id, role=None, environment="production"):
                return ResolvedAsset(
                    asset_id=fragment_id, content="", version="1",
                    environment=environment, content_hash=ResolvedAsset.compute_hash(""),
                )

            async def resolve_request_template(self, template_id, environment="production"):
                return ResolvedAsset(
                    asset_id=template_id,
                    content="template content",
                    version="2",
                    environment=environment,
                    content_hash=ResolvedAsset.compute_hash("template content"),
                )

            async def get_asset_version(self, asset_id):
                return AssetVersionInfo(
                    asset_id=asset_id, version="2", environment="production"
                )

        stub = Stub()
        result = await stub.resolve_request_template("request.cycle_task_base")
        assert result.asset_id == "request.cycle_task_base"
        assert result.version == "2"

        info = await stub.get_asset_version("request.cycle_task_base")
        assert isinstance(info, AssetVersionInfo)
        assert info.version == "2"
