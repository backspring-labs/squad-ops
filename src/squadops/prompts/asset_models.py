"""
Domain models for governed prompt assets (SIP-0084).

These models represent resolved prompt assets from the registry — distinct from
the SIP-0057 assembly models (PromptFragment, AssembledPrompt) which remain
unchanged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ResolvedAsset:
    """A governed prompt asset resolved from the registry.

    Represents either a system prompt fragment or a request template
    after resolution from the configured asset source.
    """

    asset_id: str
    content: str
    version: str
    environment: str
    content_hash: str  # SHA256

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA256 hash of asset content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AssetVersionInfo:
    """Version metadata for a governed prompt asset."""

    asset_id: str
    version: str
    environment: str
    updated_at: datetime | None = None


@dataclass(frozen=True)
class RenderedRequest:
    """A fully rendered request with provenance.

    Produced by RequestTemplateRenderer after resolving a governed template
    and injecting runtime variables.
    """

    content: str
    template_id: str
    template_version: str
    render_hash: str  # SHA256 of final rendered content

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA256 hash of rendered content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
