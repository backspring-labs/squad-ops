"""
Langfuse-backed prompt asset adapter (SIP-0084).

Resolves governed prompt assets (system fragments and request templates)
from Langfuse's prompt management API. The langfuse SDK is lazily imported
— this module can be imported without the SDK; only construction triggers
the import.
"""

from __future__ import annotations

import logging
from typing import Any

from squadops.ports.prompts.asset_source import PromptAssetSourcePort
from squadops.prompts.asset_models import AssetVersionInfo, ResolvedAsset
from squadops.prompts.exceptions import (
    PromptAssetNotFoundError,
    PromptRegistryUnavailableError,
)

logger = logging.getLogger(__name__)


class LangfusePromptAssetAdapter(PromptAssetSourcePort):
    """Langfuse-backed governed prompt asset adapter.

    Uses Langfuse's prompt management API to resolve system fragments
    and request templates by identity and environment label.

    The langfuse SDK is lazily imported at construction time, following
    the same pattern as the LangFuse telemetry adapter (SIP-0061).
    """

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        host: str = "http://localhost:3001",
        **kwargs: Any,
    ) -> None:
        try:
            from langfuse import Langfuse
        except ImportError as exc:
            raise PromptRegistryUnavailableError(
                "langfuse",
                "langfuse SDK not installed — run: pip install langfuse",
            ) from exc

        try:
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
                **kwargs,
            )
        except Exception as exc:
            raise PromptRegistryUnavailableError(
                "langfuse",
                f"Failed to initialize Langfuse client: {exc}",
            ) from exc

    async def resolve_system_fragment(
        self, fragment_id: str, role: str | None = None, environment: str = "production"
    ) -> ResolvedAsset:
        name = f"{fragment_id}--{role}" if role else fragment_id
        return self._resolve(name, environment)

    async def resolve_request_template(
        self, template_id: str, environment: str = "production"
    ) -> ResolvedAsset:
        return self._resolve(template_id, environment)

    async def get_asset_version(self, asset_id: str) -> AssetVersionInfo | None:
        try:
            prompt = self._client.get_prompt(asset_id)
        except Exception:
            return None

        return AssetVersionInfo(
            asset_id=asset_id,
            version=str(prompt.version),
            environment=getattr(prompt, "label", "production") or "production",
        )

    def _resolve(self, name: str, environment: str) -> ResolvedAsset:
        """Resolve a prompt asset from Langfuse by name and label."""
        try:
            prompt = self._client.get_prompt(name, label=environment)
        except Exception as exc:
            error_str = str(exc).lower()
            if "not found" in error_str or "404" in error_str:
                raise PromptAssetNotFoundError(name, environment) from exc
            raise PromptRegistryUnavailableError(
                "langfuse", f"Failed to resolve '{name}': {exc}"
            ) from exc

        content = prompt.prompt if isinstance(prompt.prompt, str) else str(prompt.prompt)
        content_hash = ResolvedAsset.compute_hash(content)

        return ResolvedAsset(
            asset_id=name,
            content=content,
            version=str(prompt.version),
            environment=environment,
            content_hash=content_hash,
        )
