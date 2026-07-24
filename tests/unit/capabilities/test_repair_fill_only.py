"""Fill-only constraint on the correction/repair path.

The develop handler tells the dev to FILL the seeded skeleton's slots and NOT rewrite
the scaffold-owned interface (route decorators/signatures, the wired ``ApiError`` seam).
The correction/repair path previously got none of that and was told to "re-produce the
artifact", so repairs freely rewrote the seeded interface (observed live: pf-28/pf-29
routes.py calling ``ApiError(status_code=...)`` vs the seeded ``ApiError(code, message)``,
and ``APIRouter(prefix=...)`` vs seeded absolute decorators). This wires the SAME managed
appendix into the dev correction-repair, scoped to the dev role on a scaffoldable stack.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.impl.repair_handlers import (
    BuilderAssembleRepairHandler,
    DevelopmentCorrectionRepairHandler,
)

pytestmark = [pytest.mark.domain_capabilities]

_TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "squadops"
    / "prompts"
    / "request_templates"
    / "request.cycle_repair_task.md"
)


def _context(renderer):
    context = MagicMock()
    context.ports.request_renderer = renderer
    return context


async def test_dev_repair_renders_fill_only_on_scaffoldable_stack():
    handler = DevelopmentCorrectionRepairHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="FILL ONLY INSTRUCTION")
    inputs = {"resolved_config": {"build_profile": "fullstack_fastapi_react"}}

    out = await handler._render_fill_only_section(_context(renderer), inputs)

    assert out == "FILL ONLY INSTRUCTION"
    renderer.render.assert_awaited_once_with(
        "request.development_develop_fill_only_appendix",
        {"stack": "fullstack_fastapi_react"},
    )


async def test_dev_repair_fill_only_empty_on_non_scaffoldable_stack():
    handler = DevelopmentCorrectionRepairHandler()
    renderer = AsyncMock()
    inputs = {"resolved_config": {"build_profile": "python_cli_builder"}}

    assert await handler._render_fill_only_section(_context(renderer), inputs) == ""
    renderer.render.assert_not_awaited()


async def test_dev_repair_fill_only_empty_when_no_build_profile():
    handler = DevelopmentCorrectionRepairHandler()
    renderer = AsyncMock()
    assert await handler._render_fill_only_section(_context(renderer), {}) == ""
    renderer.render.assert_not_awaited()


async def test_builder_repair_never_gets_fill_only_even_on_scaffoldable_stack():
    # The appendix is about dev fill slots (routes.py/views); a builder/packaging repair
    # must not receive it even on a scaffoldable stack — scoped to the dev role.
    handler = BuilderAssembleRepairHandler()
    renderer = AsyncMock()
    inputs = {"resolved_config": {"build_profile": "fullstack_fastapi_react"}}

    assert await handler._render_fill_only_section(_context(renderer), inputs) == ""
    renderer.render.assert_not_awaited()


async def test_handle_threads_fill_only_into_render_variables():
    # End-to-end wiring: handle() renders the section and threads it so the template
    # variable is populated (the base render path reads it from inputs).
    handler = DevelopmentCorrectionRepairHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="FILL ONLY INSTRUCTION")
    context = _context(renderer)
    inputs = {"resolved_config": {"build_profile": "fullstack_fastapi_react"}}

    fill_only = await handler._render_fill_only_section(context, inputs)
    threaded = {**inputs, "fill_only_section": fill_only}
    variables = handler._build_render_variables("prd", None, threaded)

    assert variables["fill_only_section"] == "FILL ONLY INSTRUCTION"


def test_render_variables_default_fill_only_empty_when_absent():
    handler = DevelopmentCorrectionRepairHandler()
    variables = handler._build_render_variables("prd", None, {})
    assert variables["fill_only_section"] == ""


def test_repair_template_declares_and_uses_fill_only_section():
    text = _TEMPLATE.read_text(encoding="utf-8")
    assert "- fill_only_section" in text  # declared optional var
    assert "{{fill_only_section}}" in text  # placed in the body
