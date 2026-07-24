"""pf-31 Fix A — the authoritative Contract Expectations block on the repair path.

Guards the salience fix: typed criteria must render as an exact authoritative
block ABOVE prose, never as dict-repr soup inside the narrative bullets (how all
7 pf-31 repairs came to follow the prose's ``{run_id}`` over the contract's
``{id}`` and get rejected at patch verification).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.impl.repair_handlers import (
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
_APPENDIX = _TEMPLATE.parent / "request.cycle_repair_contract_expectations_appendix.md"

_TYPED = {
    "check": "endpoint_defined",
    "params": {
        "file": "backend/routes.py",
        "methods_paths": ["POST /runs", "GET /runs/{id}", "POST /runs/{id}/join"],
    },
    "id": "vc-routes-endpoints",
}
_PROSE = "GET /runs/{run_id} returns run detail"


def _context(renderer):
    context = MagicMock()
    context.ports.request_renderer = renderer
    return context


async def test_appendix_rendered_with_exact_paths():
    handler = DevelopmentCorrectionRepairHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="EXPECTATIONS BLOCK")
    inputs = {"acceptance_criteria": [_PROSE, _TYPED]}

    out = await handler._render_contract_expectations_section(_context(renderer), inputs)

    assert out == "EXPECTATIONS BLOCK"
    (template_id, variables) = renderer.render.await_args.args
    assert template_id == "request.cycle_repair_contract_expectations_appendix"
    # The literal contract spelling — the token pf-31 lost 7 repairs over.
    assert "`GET /runs/{id}`" in variables["expectations"]
    assert "{run_id}" not in variables["expectations"]


async def test_no_typed_criteria_renders_nothing():
    handler = DevelopmentCorrectionRepairHandler()
    renderer = AsyncMock()
    out = await handler._render_contract_expectations_section(
        _context(renderer), {"acceptance_criteria": [_PROSE]}
    )
    assert out == ""
    renderer.render.assert_not_awaited()


def test_render_variables_demote_typed_criteria_out_of_narrative():
    """Typed entries must not reach the narrative bullets as dict reprs."""
    handler = DevelopmentCorrectionRepairHandler()
    variables = handler._build_render_variables(
        "PRD", None, {"acceptance_criteria": [_PROSE, _TYPED]}
    )
    assert "methods_paths" not in variables["acceptance_criteria"]
    assert _PROSE in variables["acceptance_criteria"]


def test_fallback_prompt_places_expectations_above_narrative():
    """No-renderer path: the block still appears, above the demoted prose."""
    handler = DevelopmentCorrectionRepairHandler()
    prompt = handler._build_user_prompt(
        "PRD",
        None,
        {"acceptance_criteria": [_PROSE, _TYPED], "failed_task_type": "development.develop"},
    )
    block = prompt.index("Contract Expectations (authoritative")
    narrative = prompt.index("Acceptance Criteria (narrative)")
    assert block < narrative
    assert "`GET /runs/{id}`" in prompt


def test_templates_declare_and_use_the_variable():
    """The asset side of the seam: the repair template renders the block and the
    appendix asset owns the heading text (prompts-in-assets rule, #448)."""
    template = _TEMPLATE.read_text()
    assert "contract_expectations" in template
    assert "{{contract_expectations}}" in template
    appendix = _APPENDIX.read_text()
    assert "authoritative" in appendix
    assert "{{expectations}}" in appendix
