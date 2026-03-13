"""Per-cycle prompt asset cache with seal semantics (SIP-0084 Phase 4).

Enforces cycle-level asset immutability: all governed assets are resolved
eagerly at cycle startup, then the cache is sealed. No further resolution
occurs for the remainder of the cycle.

Later label promotions or asset changes in the registry only affect
subsequent cycles. Mid-cycle refresh is explicitly prohibited.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from squadops.prompts.asset_models import ResolvedAsset
from squadops.prompts.exceptions import PromptAssetNotFoundError

logger = logging.getLogger(__name__)


class CyclePromptCache:
    """Per-cycle cache for resolved prompt assets. Immutable once sealed.

    Usage::

        cache = CyclePromptCache()

        # Eagerly resolve all assets at cycle startup
        asset = await cache.resolve_and_store(
            "request.cycle_task_base",
            resolver=lambda: source.resolve_request_template(tid, env),
        )

        # Seal after startup resolution — no further resolution allowed
        cache.seal()

        # After seal, only cached lookups succeed
        asset = cache.get("request.cycle_task_base")  # OK
        await cache.resolve_and_store(...)  # raises RuntimeError
    """

    def __init__(self) -> None:
        self._assets: dict[str, ResolvedAsset] = {}
        self._sealed: bool = False

    @property
    def is_sealed(self) -> bool:
        """Whether the cache has been sealed."""
        return self._sealed

    @property
    def asset_count(self) -> int:
        """Number of cached assets."""
        return len(self._assets)

    def seal(self) -> None:
        """Seal the cache — no further resolution allowed.

        Once sealed, only ``get()`` succeeds for already-cached assets.
        Any attempt to resolve new assets raises ``RuntimeError``.
        """
        self._sealed = True
        logger.info(
            "cycle_prompt_cache_sealed",
            extra={"asset_count": len(self._assets)},
        )

    async def resolve_and_store(
        self,
        asset_id: str,
        resolver: Callable[[], Awaitable[ResolvedAsset]],
    ) -> ResolvedAsset:
        """Resolve an asset and store it in the cache.

        If the asset is already cached, returns the cached version.
        If the cache is sealed, raises RuntimeError.

        Args:
            asset_id: Unique asset identifier (e.g., template_id:environment)
            resolver: Async callable that resolves the asset from the source

        Returns:
            The resolved asset

        Raises:
            RuntimeError: If the cache is sealed
            PromptAssetNotFoundError: If the resolver cannot find the asset
        """
        if asset_id in self._assets:
            return self._assets[asset_id]

        if self._sealed:
            raise RuntimeError(
                f"Cycle prompt cache is sealed; cannot resolve new asset {asset_id!r}. "
                "All assets must be resolved before sealing."
            )

        asset = await resolver()
        self._assets[asset_id] = asset
        return asset

    def get(self, asset_id: str) -> ResolvedAsset:
        """Get a cached asset by ID.

        Args:
            asset_id: Asset identifier

        Returns:
            The cached asset

        Raises:
            PromptAssetNotFoundError: If asset is not in cache
        """
        if asset_id not in self._assets:
            raise PromptAssetNotFoundError(
                asset_id,
                environment="(cached)",
            )
        return self._assets[asset_id]

    def contains(self, asset_id: str) -> bool:
        """Check if an asset is cached."""
        return asset_id in self._assets

    def get_version_snapshot(self) -> dict[str, str]:
        """Return a snapshot of all cached asset versions for provenance.

        Returns:
            Dict mapping asset_id → version string
        """
        return {aid: asset.version for aid, asset in self._assets.items()}

    def clear(self) -> None:
        """Clear the cache and unseal (for testing or between cycles)."""
        self._assets.clear()
        self._sealed = False
