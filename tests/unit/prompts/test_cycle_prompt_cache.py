"""Unit tests for CyclePromptCache (SIP-0084 Phase 4).

Tests seal semantics, resolve-and-store behavior, version snapshot,
and integration with RequestTemplateRenderer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from squadops.prompts.asset_models import ResolvedAsset
from squadops.prompts.cache import CyclePromptCache
from squadops.prompts.exceptions import PromptAssetNotFoundError
from squadops.prompts.renderer import RequestTemplateRenderer

pytestmark = [pytest.mark.domain_contracts]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_asset(asset_id: str = "test", version: str = "1") -> ResolvedAsset:
    content = f"---\ntemplate_id: {asset_id}\n---\nHello {{{{name}}}}"
    return ResolvedAsset(
        asset_id=asset_id,
        content=content,
        version=version,
        environment="production",
        content_hash=ResolvedAsset.compute_hash(content),
    )


def _make_resolver(asset: ResolvedAsset) -> AsyncMock:
    return AsyncMock(return_value=asset)


# ---------------------------------------------------------------------------
# Basic cache operations
# ---------------------------------------------------------------------------


class TestCacheOperations:
    async def test_resolve_and_store_caches_asset(self):
        cache = CyclePromptCache()
        asset = _make_asset("t1")
        resolver = _make_resolver(asset)

        result = await cache.resolve_and_store("t1", resolver)

        assert result is asset
        assert cache.contains("t1")
        assert cache.asset_count == 1

    async def test_second_resolve_returns_cached_without_calling_resolver(self):
        cache = CyclePromptCache()
        asset = _make_asset("t1")
        resolver = _make_resolver(asset)

        await cache.resolve_and_store("t1", resolver)
        result = await cache.resolve_and_store("t1", resolver)

        assert result is asset
        resolver.assert_awaited_once()  # Only called once

    async def test_get_returns_cached_asset(self):
        cache = CyclePromptCache()
        asset = _make_asset("t1")
        await cache.resolve_and_store("t1", _make_resolver(asset))

        assert cache.get("t1") is asset

    def test_get_raises_when_not_cached(self):
        cache = CyclePromptCache()
        with pytest.raises(PromptAssetNotFoundError, match="nonexistent"):
            cache.get("nonexistent")

    def test_contains_false_for_uncached(self):
        cache = CyclePromptCache()
        assert not cache.contains("missing")

    async def test_multiple_assets_stored_independently(self):
        cache = CyclePromptCache()
        a1 = _make_asset("t1", version="1")
        a2 = _make_asset("t2", version="2")

        await cache.resolve_and_store("t1", _make_resolver(a1))
        await cache.resolve_and_store("t2", _make_resolver(a2))

        assert cache.asset_count == 2
        assert cache.get("t1").version == "1"
        assert cache.get("t2").version == "2"


# ---------------------------------------------------------------------------
# Seal semantics
# ---------------------------------------------------------------------------


class TestSealSemantics:
    def test_not_sealed_by_default(self):
        cache = CyclePromptCache()
        assert not cache.is_sealed

    def test_seal_sets_flag(self):
        cache = CyclePromptCache()
        cache.seal()
        assert cache.is_sealed

    async def test_sealed_cache_rejects_new_resolve(self):
        cache = CyclePromptCache()
        cache.seal()

        with pytest.raises(RuntimeError, match="sealed"):
            await cache.resolve_and_store("new", _make_resolver(_make_asset()))

    async def test_sealed_cache_allows_get_for_existing(self):
        cache = CyclePromptCache()
        asset = _make_asset("t1")
        await cache.resolve_and_store("t1", _make_resolver(asset))
        cache.seal()

        assert cache.get("t1") is asset

    async def test_sealed_cache_returns_cached_on_resolve(self):
        """resolve_and_store returns cached asset even when sealed."""
        cache = CyclePromptCache()
        asset = _make_asset("t1")
        await cache.resolve_and_store("t1", _make_resolver(asset))
        cache.seal()

        # Should return cached, not raise
        result = await cache.resolve_and_store("t1", _make_resolver(_make_asset()))
        assert result is asset


# ---------------------------------------------------------------------------
# Version snapshot
# ---------------------------------------------------------------------------


class TestVersionSnapshot:
    async def test_snapshot_returns_asset_versions(self):
        cache = CyclePromptCache()
        await cache.resolve_and_store("t1", _make_resolver(_make_asset("t1", "v1")))
        await cache.resolve_and_store("t2", _make_resolver(_make_asset("t2", "v3")))

        snapshot = cache.get_version_snapshot()
        assert snapshot == {"t1": "v1", "t2": "v3"}

    def test_empty_snapshot(self):
        cache = CyclePromptCache()
        assert cache.get_version_snapshot() == {}


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


class TestClear:
    async def test_clear_removes_all_and_unseals(self):
        cache = CyclePromptCache()
        await cache.resolve_and_store("t1", _make_resolver(_make_asset()))
        cache.seal()

        cache.clear()

        assert cache.asset_count == 0
        assert not cache.is_sealed
        assert not cache.contains("t1")


# ---------------------------------------------------------------------------
# Renderer integration with CyclePromptCache
# ---------------------------------------------------------------------------


def _make_source(templates: dict[str, str]) -> AsyncMock:
    """Create a mock PromptAssetSourcePort."""
    source = AsyncMock()

    async def resolve_template(template_id, environment="production"):
        if template_id not in templates:
            raise PromptAssetNotFoundError(template_id, environment)
        content = templates[template_id]
        return ResolvedAsset(
            asset_id=template_id,
            content=content,
            version="1",
            environment=environment,
            content_hash=ResolvedAsset.compute_hash(content),
        )

    source.resolve_request_template = AsyncMock(side_effect=resolve_template)
    return source


_TEMPLATE = (
    "---\n"
    "template_id: request.test\n"
    "required_variables:\n"
    "  - name\n"
    "---\n"
    "Hello {{name}}!\n"
)


class TestRendererWithCycleCache:
    async def test_renderer_populates_cycle_cache(self):
        source = _make_source({"request.test": _TEMPLATE})
        cache = CyclePromptCache()
        renderer = RequestTemplateRenderer(source, cycle_cache=cache)

        await renderer.render("request.test", {"name": "World"})

        assert cache.contains("request.test:production")

    async def test_renderer_uses_cached_asset_after_seal(self):
        source = _make_source({"request.test": _TEMPLATE})
        cache = CyclePromptCache()
        renderer = RequestTemplateRenderer(source, cycle_cache=cache)

        # First render populates cache
        await renderer.render("request.test", {"name": "World"})
        cache.seal()

        # Second render uses cache — source not called again
        result = await renderer.render("request.test", {"name": "Again"})

        assert "Hello Again!" in result.content
        assert source.resolve_request_template.call_count == 1

    async def test_renderer_sealed_cache_rejects_unknown_template(self):
        source = _make_source({"request.test": _TEMPLATE})
        cache = CyclePromptCache()
        renderer = RequestTemplateRenderer(source, cycle_cache=cache)

        cache.seal()

        with pytest.raises(RuntimeError, match="sealed"):
            await renderer.render("request.unknown", {"name": "X"})

    async def test_cycle_immutability_same_version_throughout(self):
        """Verify same asset version is served even if source would return different."""
        source = _make_source({"request.test": _TEMPLATE})
        cache = CyclePromptCache()
        renderer = RequestTemplateRenderer(source, cycle_cache=cache)

        r1 = await renderer.render("request.test", {"name": "First"})
        cache.seal()

        # Even though we render again, same template version is used
        r2 = await renderer.render("request.test", {"name": "Second"})

        assert r1.template_version == r2.template_version
        assert source.resolve_request_template.call_count == 1

    async def test_no_cycle_cache_uses_renderer_own_cache(self):
        """When no cycle cache, renderer falls back to its own caching."""
        source = _make_source({"request.test": _TEMPLATE})
        renderer = RequestTemplateRenderer(source)  # No cycle_cache

        r1 = await renderer.render("request.test", {"name": "A"})
        r2 = await renderer.render("request.test", {"name": "B"})

        assert source.resolve_request_template.call_count == 1
        assert "Hello A!" in r1.content
        assert "Hello B!" in r2.content
