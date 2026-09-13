"""
Filesystem-backed prompt asset adapter (SIP-0084).

Wraps the existing PromptRepository for system fragment retrieval and
reads request templates from a dedicated directory. This adapter is the
default — all deployments use it unless explicitly switched to Langfuse.
"""

from __future__ import annotations

import logging
from pathlib import Path

from squadops.ports.prompts.asset_source import PromptAssetSourcePort
from squadops.prompts.asset_models import AssetVersionInfo, ResolvedAsset
from squadops.prompts.exceptions import PromptAssetNotFoundError
from squadops.prompts.frontmatter import read_frontmatter

logger = logging.getLogger(__name__)


class FilesystemPromptAssetAdapter(PromptAssetSourcePort):
    """Filesystem-backed governed prompt asset adapter.

    System fragments are delegated to the existing PromptRepository.
    Request templates are read from ``{templates_path}/{template_id}.md``.
    """

    def __init__(
        self,
        fragments_path: Path,
        templates_path: Path,
    ) -> None:
        self._fragments_path = Path(fragments_path)
        self._templates_path = Path(templates_path)
        # Lazy-imported PromptRepository for fragment resolution
        self._repo: object | None = None

    def _get_repo(self):
        """Lazy-create a FileSystemPromptRepository for fragment retrieval."""
        if self._repo is None:
            from adapters.prompts.filesystem import FileSystemPromptRepository

            self._repo = FileSystemPromptRepository(base_path=self._fragments_path)
        return self._repo

    async def resolve_system_fragment(
        self, fragment_id: str, role: str | None = None, environment: str = "production"
    ) -> ResolvedAsset:
        repo = self._get_repo()
        try:
            fragment = repo.get_fragment(fragment_id, role)
        except Exception as exc:
            raise PromptAssetNotFoundError(fragment_id, environment) from exc

        return ResolvedAsset(
            asset_id=fragment_id,
            content=fragment.content,
            version=fragment.version,
            environment=environment,
            content_hash=fragment.sha256_hash,
        )

    async def resolve_request_template(
        self, template_id: str, environment: str = "production"
    ) -> ResolvedAsset:
        file_path = self._templates_path / f"{template_id}.md"
        if not file_path.exists():
            raise PromptAssetNotFoundError(template_id, environment)

        raw = file_path.read_text(encoding="utf-8")

        # Optional YAML frontmatter: the version, and the body after the block.
        header, body = read_frontmatter(raw)
        version = str(header.get("version", "1"))
        content = body.strip()

        content_hash = ResolvedAsset.compute_hash(content)

        return ResolvedAsset(
            asset_id=template_id,
            content=content,
            version=version,
            environment=environment,
            content_hash=content_hash,
        )

    async def get_asset_version(self, asset_id: str) -> AssetVersionInfo | None:
        # Check templates first, then fragments
        template_path = self._templates_path / f"{asset_id}.md"
        if template_path.exists():
            header, _ = read_frontmatter(template_path.read_text(encoding="utf-8"))
            version = str(header.get("version", "1"))
            return AssetVersionInfo(
                asset_id=asset_id,
                version=version,
                environment="production",
            )

        # Try fragment via repository
        repo = self._get_repo()
        if repo.fragment_exists(asset_id):
            fragment = repo.get_fragment(asset_id)
            return AssetVersionInfo(
                asset_id=asset_id,
                version=fragment.version,
                environment="production",
            )

        return None
