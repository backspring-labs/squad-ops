"""Fill-only develop instruction wiring (SIP-0099 phase 99.3 part 2).

On a scaffoldable stack the executor seeds a walking skeleton into develop's workspace
(part 1), so the dev is told to FILL the fixed slots rather than rewire. Data-driven,
dev-only, content in a managed asset — mirrors 99.2's scaffold_section.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.dev_capabilities import get_capability
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


class TestPerStackAppendix:
    """SIP-0104 window roll 1 (cyc_04d36309d793, 2026-08-15): one shared asset served
    both stacks, so a `nextjs_ts` author was instructed to fill `backend/routes.py` and
    `frontend/src/views/*.jsx` — neither of which exists here — and told that the client
    seam "prefixes `/api`", which stack #2's seam does not. It wrote `api('/runs')`
    against a helper that fetches verbatim, and EVERY UI call 404'd in a deliverable that
    passed 36/36 checks, all 5 probes, the frontend build, and the boot audit.
    """

    async def test_each_stack_gets_its_own_asset(self):
        renderer = AsyncMock()
        renderer.render.return_value = MagicMock(content="X")

        await _handler("nextjs_ts")._fill_only_section(renderer)
        assert (
            renderer.render.await_args.args[0]
            == "request.development_develop_fill_only_appendix_nextjs_ts"
        )

        renderer.render.reset_mock()
        await _handler("fullstack_fastapi_react")._fill_only_section(renderer)
        assert (
            renderer.render.await_args.args[0] == "request.development_develop_fill_only_appendix"
        )

    async def test_the_nextjs_author_is_told_this_stacks_layout_and_seam(self):
        """A live render: the facts must survive the template, and the two failure modes
        roll 1 shipped must both be addressed — the file layout and the prefix."""
        from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
        from squadops.prompts.renderer import RequestTemplateRenderer

        templates = _APPENDIX.parent
        renderer = RequestTemplateRenderer(
            FilesystemPromptAssetAdapter(
                fragments_path=templates.parent / "fragments", templates_path=templates
            )
        )

        out = await _handler("nextjs_ts")._fill_only_section(renderer)

        # this stack's real layout
        assert "app/**/route.ts" in out
        assert "app/**/page.tsx" in out
        # ...and NOT the other stack's, which is what roll 1's author was handed
        assert "backend/routes.py" not in out
        assert "frontend/src/views" not in out
        assert "apiFetch" not in out
        # the seam semantic that broke the UI, stated with the correct and wrong forms
        assert "adds no prefix" in out
        assert "api<Run[]>('/api/runs')" in out
        assert "await api('/runs')" in out  # the WRONG example, named as wrong

    async def test_a_stack_with_no_declared_asset_gets_no_appendix(self):
        """Wrong guidance is worse than none (#818): an unregistered stack must not
        inherit another stack's conventions — which is exactly this defect."""
        from unittest.mock import patch

        renderer = AsyncMock()
        handler = _handler("fullstack_fastapi_react")
        capability = get_capability("fullstack_fastapi_react")
        with patch(
            "squadops.capabilities.dev_capabilities.get_capability",
            return_value=replace(capability, fill_only_template=""),
        ):
            assert await handler._fill_only_section(renderer) == ""
        renderer.render.assert_not_awaited()
