"""Fill-only develop instruction wiring (SIP-0099 phase 99.3 part 2).

On a scaffoldable stack the executor seeds a walking skeleton into develop's workspace
(part 1), so the dev is told to FILL the fixed slots rather than rewire. Data-driven,
dev-only, content in a managed asset — mirrors 99.2's scaffold_section.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler

pytestmark = [pytest.mark.domain_capabilities]

_APPENDIX = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "squadops"
    / "prompts"
    / "request_templates"
    / "request.development_develop_fill_only_appendix.md"
)


def _handler(build_profile: str) -> DevelopmentDevelopHandler:
    handler = DevelopmentDevelopHandler()
    handler._resolved_config = {"build_profile": build_profile}
    return handler


async def test_fill_only_section_rendered_on_scaffoldable_stack():
    handler = _handler("fullstack_fastapi_react")
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="FILL ONLY INSTRUCTION")

    out = await handler._fill_only_section(renderer)

    assert out == "FILL ONLY INSTRUCTION"
    renderer.render.assert_awaited_once_with(
        "request.development_develop_fill_only_appendix", {"stack": "fullstack_fastapi_react"}
    )


async def test_fill_only_section_empty_on_non_scaffoldable_stack():
    # a non-scaffolded build (no seeded skeleton) must never get fill-only guidance
    handler = _handler("python_cli_builder")
    renderer = AsyncMock()
    out = await handler._fill_only_section(renderer)
    assert out == ""
    renderer.render.assert_not_awaited()


async def test_fill_only_section_empty_when_no_build_profile():
    handler = _handler("")
    renderer = AsyncMock()
    assert await handler._fill_only_section(renderer) == ""
    renderer.render.assert_not_awaited()


def test_fill_only_appendix_asset_is_well_formed():
    text = _APPENDIX.read_text(encoding="utf-8")
    assert "template_id: request.development_develop_fill_only_appendix" in text
    assert "- stack" in text  # required var (template-contract test enforces >=1)
    assert "backend/routes.py" in text  # the fill slot
    assert "Do NOT" in text  # the frozen-surface discipline
    assert "{{stack}}" in text
