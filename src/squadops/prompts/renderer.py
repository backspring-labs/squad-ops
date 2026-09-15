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
from typing import TYPE_CHECKING

from squadops.ports.prompts.asset_source import PromptAssetSourcePort
from squadops.prompts.asset_models import RenderedRequest, ResolvedAsset
from squadops.prompts.exceptions import TemplateMissingVariableError
from squadops.prompts.frontmatter import read_frontmatter

if TYPE_CHECKING:
    from squadops.prompts.cache import CyclePromptCache

logger = logging.getLogger(__name__)

# Pattern for {{variable}} placeholders in templates
_PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")
_BLANK_RUN_PATTERN = re.compile(r"\n{3,}")
#: A fenced block's opening line: up to three spaces of indent, then a run of three or more
#: backticks or tildes (CommonMark). The closing line is the same character, at least as long,
#: and nothing else.
_FENCE_OPEN_PATTERN = re.compile(r"^ {0,3}(?P<mark>`{3,}|~{3,})")


def collapse_blank_runs_outside_fences(text: str) -> str:
    """Runs of three or more newlines become two — the cleanup an empty optional leaves behind
    — everywhere except inside a fenced block, whose lines are verbatim.

    A file shown in a prompt rides inside a fence, and a model is asked to copy its lines
    exactly (SIP-0107 §9.2). Collapsing the blank lines of a Python file — two between every
    top-level definition — would show the model a file that is not the one its edits are
    matched against, and every anchor spanning that gap would be refused (#1576).
    """
    fenced = _fenced_line_indices(text.split("\n"))
    if not fenced:
        return _BLANK_RUN_PATTERN.sub("\n\n", text)

    def _collapse(match: re.Match[str]) -> str:
        first_blank_line = text.count("\n", 0, match.start()) + 1
        return match.group(0) if first_blank_line in fenced else "\n\n"

    return _BLANK_RUN_PATTERN.sub(_collapse, text)


def _fenced_line_indices(lines: list[str]) -> set[int]:
    """The indices of every line inside a fenced block — between its opening and closing
    lines, neither included. An unclosed fence runs to the end."""
    fenced: set[int] = set()
    mark: str | None = None
    for index, line in enumerate(lines):
        if mark is None:
            opened = _FENCE_OPEN_PATTERN.match(line)
            if opened:
                mark = opened.group("mark")
            continue
        stripped = line.strip()
        if stripped and set(stripped) == {mark[0]} and len(stripped) >= len(mark):
            mark = None
        else:
            fenced.add(index)
    return fenced


def _parse_template_contract(content: str) -> tuple[str, set[str], set[str]]:
    """Parse template frontmatter and extract contract.

    Returns:
        Tuple of (body_content, required_variables, optional_variables).
        If no frontmatter is present, all {{placeholders}} in the body
        are treated as optional.
    """
    header, body = read_frontmatter(content)
    required = set(header.get("required_variables", []))
    optional = set(header.get("optional_variables", []))

    return body, required, optional


class RequestTemplateRenderer:
    """Resolves governed request templates and renders with runtime variables.

    This component handles Stage 2 of the prompt pipeline: request template
    rendering. It does NOT participate in Stage 1 (system prompt assembly),
    which remains owned by the PromptAssembler.
    """

    def __init__(
        self,
        asset_source: PromptAssetSourcePort,
        cycle_cache: CyclePromptCache | None = None,
    ) -> None:
        self._source = asset_source
        self._cache: dict[str, ResolvedAsset] = {}
        self._cycle_cache = cycle_cache

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

        rendered = collapse_blank_runs_outside_fences(rendered)

        render_hash = RenderedRequest.compute_hash(rendered)

        return RenderedRequest(
            content=rendered,
            template_id=template_id,
            template_version=asset.version,
            render_hash=render_hash,
        )

    async def _resolve(self, template_id: str, environment: str) -> ResolvedAsset:
        """Resolve and cache a template asset.

        When a CyclePromptCache is available, delegates to it for cycle-level
        immutability (SIP-0084 §8). Otherwise falls back to the renderer's
        own per-instance cache.
        """
        cache_key = f"{template_id}:{environment}"

        # Cycle cache takes precedence for immutability guarantees
        if self._cycle_cache is not None:
            if self._cycle_cache.contains(cache_key):
                return self._cycle_cache.get(cache_key)
            return await self._cycle_cache.resolve_and_store(
                cache_key,
                resolver=lambda: self._source.resolve_request_template(template_id, environment),
            )

        # Fallback: renderer's own cache (no cycle immutability)
        if cache_key in self._cache:
            return self._cache[cache_key]

        asset = await self._source.resolve_request_template(template_id, environment)
        self._cache[cache_key] = asset
        return asset

    def clear_cache(self) -> None:
        """Clear the resolved asset cache (e.g., between cycle runs)."""
        self._cache.clear()
