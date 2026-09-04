"""#667 — the qa DOM anchor contract on the repair path.

qa.test_repair re-authors the failed suite with none of the anchor inventory
the original qa.test dispatch carried (``_dom_anchor_section`` in the qa_test
handler) — the re-authored suite then asserts invented render details, the
fay-6/fay-12 churn class replayed through the repair path. This wires the SAME
appendix asset into the repair prompt, from the same threaded lines.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities.handlers.impl.repair_handlers import (
    DevelopmentCorrectionRepairHandler,
    QATestRepairHandler,
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

_LINES = [
    "`RunDetailView` (route `/runs/:id`): root container `run-detail`; "
    "anchors: `run-detail`, `participant-list`, `join-form`"
]


def _context(renderer):
    context = MagicMock()
    context.ports.request_renderer = renderer
    return context


async def test_qa_repair_renders_dom_anchor_from_threaded_lines():
    handler = QATestRepairHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="DOM ANCHOR BLOCK")
    inputs = {"dom_testid_surface": _LINES}

    out = await handler._render_dom_anchor_section(_context(renderer), inputs)

    assert out == "DOM ANCHOR BLOCK"
    (template_id, variables) = renderer.render.await_args.args
    assert template_id == "request.qa_test_dom_anchor_appendix"
    assert variables["testid_lines"].startswith("- `RunDetailView`")
    assert "`run-detail`" in variables["testid_lines"]


async def test_dev_repair_never_renders_dom_anchor():
    """Role gate: the dev repair gets its anchors through the fill-only
    appendix's testid slot — rendering the qa-directed block into a dev prompt
    would instruct the view author to QUERY anchors instead of attach them."""
    handler = DevelopmentCorrectionRepairHandler()
    renderer = AsyncMock()

    out = await handler._render_dom_anchor_section(
        _context(renderer), {"dom_testid_surface": _LINES}
    )

    assert out == ""
    renderer.render.assert_not_awaited()


async def test_no_lines_renders_empty():
    handler = QATestRepairHandler()
    renderer = AsyncMock()

    assert await handler._render_dom_anchor_section(_context(renderer), {}) == ""
    assert (
        await handler._render_dom_anchor_section(
            _context(renderer), {"dom_testid_surface": ["", "  "]}
        )
        == ""
    )
    renderer.render.assert_not_awaited()


async def test_handle_threads_dom_anchor_into_render_variables():
    """End-to-end wiring: handle() renders the section and threads it so the
    template variable is populated — the silent-no-op class where the section
    renders but never reaches the prompt."""
    handler = QATestRepairHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="DOM ANCHOR BLOCK")
    context = _context(renderer)
    inputs = {"dom_testid_surface": _LINES}

    dom_anchor = await handler._render_dom_anchor_section(context, inputs)
    threaded = {**inputs, "dom_anchor_section": dom_anchor}
    variables = handler._build_render_variables("prd", None, threaded)

    assert variables["dom_anchor_section"] == "DOM ANCHOR BLOCK"


def test_render_variables_default_dom_anchor_empty_when_absent():
    handler = QATestRepairHandler()
    variables = handler._build_render_variables("prd", None, {})
    assert variables["dom_anchor_section"] == ""


def test_repair_template_declares_and_uses_dom_anchor_section():
    text = _TEMPLATE.read_text(encoding="utf-8")
    assert "- dom_anchor_section" in text  # declared optional var
    assert "{{dom_anchor_section}}" in text  # placed in the body


_CLIENT_LINES = [
    "`apiFetch(path, options = {})` exported from `frontend/src/api.js` — prefixes `/api`",
]


async def test_qa_repair_renders_the_frozen_client_surface_from_threaded_lines():
    """#668: the re-authored suite mocks beneath the same client the original dispatch
    was shown; a repair blind to its surface re-invents it (fay-14's class)."""
    handler = QATestRepairHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="CLIENT BLOCK")

    out = await handler._render_client_surface_section(
        _context(renderer), {"frozen_client_surface": _CLIENT_LINES}
    )

    assert out == "CLIENT BLOCK"
    (template_id, variables) = renderer.render.await_args.args
    assert template_id == "request.qa_test_client_surface_appendix"
    assert variables["client_lines"] == "- " + _CLIENT_LINES[0]


async def test_dev_repair_never_renders_the_client_surface():
    handler = DevelopmentCorrectionRepairHandler()
    renderer = AsyncMock()
    out = await handler._render_client_surface_section(
        _context(renderer), {"frozen_client_surface": _CLIENT_LINES}
    )
    assert out == ""
    renderer.render.assert_not_awaited()


def _roll_6_evidence():
    """1.6.6 React roll 6's final frontend report, through the runner's text parser and
    the shared row builder — the cases the brief must name."""
    from pathlib import Path

    from squadops.capabilities.handlers.test_runner import (
        RunTestsResult,
        failed_tests_pass_row,
        parse_vitest_failure_text,
    )

    replays = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"
    text = (replays / "1-6-6-react-roll-6-frontend-final-test_report.md").read_text()
    stdout = text.split("## stdout", 1)[1].split("```")[1]
    rows = parse_vitest_failure_text(stdout)
    row = failed_tests_pass_row(
        RunTestsResult(executed=True, exit_code=1, runner="vitest", test_failures=tuple(rows))
    )
    return {"validation_result": {"passed": False, "checks": [row]}}


async def test_qa_repair_renders_the_failing_cases_from_the_runners_rows():
    """#1123 (1): the brief names the cases that failed — roll 6's one of four — and
    nothing else; before this the repair re-authored the whole file with no list."""
    handler = QATestRepairHandler()
    renderer = AsyncMock()
    renderer.render.return_value = MagicMock(content="SCOPE BLOCK")

    out = await handler._render_failing_cases_section(
        _context(renderer), {"failure_evidence": _roll_6_evidence()}
    )

    assert out == "SCOPE BLOCK"
    (template_id, variables) = renderer.render.await_args.args
    assert template_id == "request.qa_test_repair_failing_cases_appendix"
    # #1289: a string. The renderer substitutes text and raises TypeError on an int —
    # which this test never saw, because it stubs the renderer. The real render is
    # exercised in `tests/unit/prompts/test_declared_template_variables_are_supplied.py`.
    assert variables["case_count"] == "1"
    assert variables["case_lines"] == (
        "- `src/__tests__/runs.test.jsx` › RunDetailView > renders participant names and "
        "submits join with expected payload — expected undefined to be defined"
    )


async def test_dev_repair_and_an_evidence_less_qa_repair_render_no_scope_block():
    renderer = AsyncMock()
    assert (
        await DevelopmentCorrectionRepairHandler()._render_failing_cases_section(
            _context(renderer), {"failure_evidence": _roll_6_evidence()}
        )
        == ""
    )
    assert (
        await QATestRepairHandler()._render_failing_cases_section(
            _context(renderer), {"failure_evidence": {"validation_result": {"checks": []}}}
        )
        == ""
    )
    renderer.render.assert_not_awaited()
