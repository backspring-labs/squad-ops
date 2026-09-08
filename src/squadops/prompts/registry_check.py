"""The prompt registry must serve every asset the image ships — checked at agent boot (#352).

#327 restored *deploy = sync* for the compose pipeline only: ``rebuild_and_deploy.sh``
uploads the prompt assets to LangFuse as a deploy step, and the filesystem layer fails
hard on manifest drift (#351). The registry layer had no runtime guard at all — an agent
booting against a registry that lacks a template it will render fails at the first
cycle that renders it, as ``Prompt asset not found``, hours later. When the asset source
is the registry, boot verifies that every request template shipped in the image and
every system fragment this role assembles resolve there, and refuses to start otherwise,
naming what is missing. Deployment-independent: whichever pipeline forgot to sync, the
agent says so before it takes a task.
"""

from __future__ import annotations

import importlib.resources as resources
import logging
from collections.abc import Iterable

import yaml

from squadops.ports.prompts.asset_source import PromptAssetSourcePort
from squadops.prompts.exceptions import PromptRegistryUnavailableError

logger = logging.getLogger(__name__)


class PromptRegistryStaleError(PromptRegistryUnavailableError):
    """The registry does not serve an asset the image ships (#352)."""

    def __init__(self, provider: str, missing: list[str]) -> None:
        self.missing = list(missing)
        super().__init__(
            provider,
            f"{len(self.missing)} shipped prompt asset(s) do not resolve from the registry — "
            f"the registry is stale for this image (sync it, #327 / #352): "
            + ", ".join(self.missing),
        )


def shipped_request_template_ids() -> list[str]:
    """Every request template the image ships, by id (the file stem)."""
    root = resources.files("squadops.prompts").joinpath("request_templates")
    return sorted(p.name[: -len(".md")] for p in root.iterdir() if p.name.endswith(".md"))


def shipped_fragment_ids_for_role(role: str) -> list[str]:
    """The system fragments the manifest binds to ``role``, as the registry names them
    (``{fragment_id}--{role}``, the LangFuse adapter's naming)."""
    manifest = yaml.safe_load(
        resources.files("squadops.prompts").joinpath("fragments/manifest.yaml").read_text()
    )
    return sorted(
        f"{entry['fragment_id']}--{role}"
        for entry in manifest.get("fragments", [])
        if role in (entry.get("roles") or [])
    )


async def missing_registry_assets(
    source: PromptAssetSourcePort, asset_ids: Iterable[str]
) -> list[str]:
    """The ids the registry cannot serve, in order."""
    missing: list[str] = []
    for asset_id in asset_ids:
        if await source.get_asset_version(asset_id) is None:
            missing.append(asset_id)
    return missing


async def verify_registry_serves_shipped_assets(
    source: PromptAssetSourcePort, *, role: str, provider: str
) -> int:
    """Refuse to boot on a stale registry; return the number of assets verified."""
    asset_ids = shipped_request_template_ids() + shipped_fragment_ids_for_role(role)
    missing = await missing_registry_assets(source, asset_ids)
    if missing:
        raise PromptRegistryStaleError(provider, missing)
    logger.info(
        "prompt registry serves every shipped asset",
        extra={"provider": provider, "role": role, "assets": len(asset_ids)},
    )
    return len(asset_ids)
