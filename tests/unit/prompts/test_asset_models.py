"""
Unit tests for governed prompt asset models (SIP-0084).
"""

import pytest

from squadops.prompts.asset_models import AssetVersionInfo, RenderedRequest, ResolvedAsset


class TestResolvedAsset:
    """Tests for ResolvedAsset frozen dataclass."""

    def test_immutability(self):
        """Frozen dataclass rejects attribute modification."""
        asset = ResolvedAsset(
            asset_id="identity",
            content="You are an agent.",
            version="1",
            environment="production",
            content_hash=ResolvedAsset.compute_hash("You are an agent."),
        )
        with pytest.raises(AttributeError):
            asset.content = "Modified"

    def test_compute_hash_deterministic(self):
        """Same content always produces the same hash."""
        content = "Test content for hashing"
        assert ResolvedAsset.compute_hash(content) == ResolvedAsset.compute_hash(content)
        assert len(ResolvedAsset.compute_hash(content)) == 64

    def test_compute_hash_differs_for_different_content(self):
        """Different content produces different hashes."""
        assert ResolvedAsset.compute_hash("a") != ResolvedAsset.compute_hash("b")


class TestAssetVersionInfo:
    """Tests for AssetVersionInfo frozen dataclass."""

    def test_immutability(self):
        asset = AssetVersionInfo(asset_id="identity", version="3", environment="staging")
        with pytest.raises(AttributeError):
            asset.version = "4"

    def test_equality_with_same_values(self):
        """Two AssetVersionInfo with identical values are equal (frozen dataclass)."""
        a = AssetVersionInfo(asset_id="x", version="1", environment="production")
        b = AssetVersionInfo(asset_id="x", version="1", environment="production")
        assert a == b


class TestRenderedRequest:
    """Tests for RenderedRequest frozen dataclass."""

    def test_immutability(self):
        rr = RenderedRequest(
            content="rendered",
            template_id="request.cycle_task_base",
            template_version="2",
            render_hash=RenderedRequest.compute_hash("rendered"),
        )
        with pytest.raises(AttributeError):
            rr.content = "changed"

    def test_compute_hash_deterministic(self):
        assert RenderedRequest.compute_hash("x") == RenderedRequest.compute_hash("x")
        assert len(RenderedRequest.compute_hash("x")) == 64
