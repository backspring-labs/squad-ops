"""
Request template renderer for Stage 2 of the prompt pipeline (SIP-0084).

Resolves governed request templates through the PromptAssetSourcePort
and renders them with runtime variables using simple {{variable}}
substitution. Enforces template contracts (required/optional variables)
at render time.

This component does NOT participate in Stage 1 (system prompt assembly),
which remains owned by the PromptAssembler (SIP-0057).
"""

from __future__ import annotations

import logging
import re

import yaml

from squadops.ports.prompts.asset_source import PromptAssetSourcePort
from squadops.prompts.asset_models import RenderedRequest, ResolvedAsset
from squadops.prompts.exceptions import TemplateMissingVariableError

logger = logging.getLogger(__name__)

# Pattern for {{variable}} placeholders in templates
_PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")

# Pattern for YAML frontmatter
_FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.MULTILINE | re.DOTALL,
)


def _parse_template_contract(content: str) -> tuple[str, set[str], set[str]]:
    """Parse template frontmatter and extract contract.

    Returns:
        Tuple of (body_content, required_variables, optional_variables).
        If no frontmatter is present, all {{placeholders}} in the body
        are treated as optional.
    """
    match = _FRONTMATTER_PATTERN.match(content)
    if not match:
        return content, set(), set()

    try:
        header = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        header = {}

    body = content[match.end():]
    required = set(header.get("required_variables", []))
    optional = set(header.get("optional_variables", []))

    return body, required, optional


class RequestTemplateRenderer:
    """Resolves governed request templates and renders with runtime variables.

    This component handles Stage 2 of the prompt pipeline: request template
    rendering. It does NOT participate in Stage 1 (system prompt assembly),
    which remains owned by the PromptAssembler.
    """

    def __init__(self, asset_source: PromptAssetSourcePort) -> None:
        self._source = asset_source
        self._cache: dict[str, ResolvedAsset] = {}

    async def render(
        self,
        template_id: str,
        variables: dict[str, str],
        environment: str = "production",
    ) -> RenderedRequest:
        """Resolve template, validate contract, inject runtime variables.

        Args:
            template_id: Template identity (e.g., "request.cycle_task_base")
            variables: Runtime variables to inject into placeholders
            environment: Environment label for asset resolution

        Returns:
            RenderedRequest with content, provenance, and render hash

        Raises:
            PromptAssetNotFoundError: If template cannot be resolved
            TemplateMissingVariableError: If a required variable is missing
        """
        asset = await self._resolve(template_id, environment)

        body, required, optional = _parse_template_contract(asset.content)
        declared = required | optional

        # Validate required variables
        for var in sorted(required):
            if var not in variables:
                raise TemplateMissingVariableError(template_id, var)

        # Warn on unknown variables (not declared in contract)
        if declared:
            for var in sorted(variables):
                if var not in declared:
                    logger.warning(
                        "Unknown variable '%s' passed to template '%s' — "
                        "not declared in required_variables or optional_variables",
                        var,
                        template_id,
                    )

        # Simple {{variable}} substitution
        def _replace(match: re.Match) -> str:
            name = match.group(1)
            return variables.get(name, "")

        rendered = _PLACEHOLDER_PATTERN.sub(_replace, body)

        # Collapse runs of 3+ blank lines to 2 (cleanup from empty optionals)
        rendered = re.sub(r"\n{3,}", "\n\n", rendered)

        render_hash = RenderedRequest.compute_hash(rendered)

        return RenderedRequest(
            content=rendered,
            template_id=template_id,
            template_version=asset.version,
            render_hash=render_hash,
        )

    async def _resolve(self, template_id: str, environment: str) -> ResolvedAsset:
        """Resolve and cache a template asset."""
        cache_key = f"{template_id}:{environment}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        asset = await self._source.resolve_request_template(template_id, environment)
        self._cache[cache_key] = asset
        return asset

    def clear_cache(self) -> None:
        """Clear the resolved asset cache (e.g., between cycle runs)."""
        self._cache.clear()
