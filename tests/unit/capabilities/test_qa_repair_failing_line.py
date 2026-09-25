"""The qa repair brief shows the line each failing case failed on (1.8.2 plan §3.2 item 6).

Scoped from the retest readout (item 1) on 1.8.1's corpus. Two scoped qa repairs edited lines
near the failing one and failed again on it: a suite failing at 217 was edited at 211, and one
failing at 130 was edited at 125–127. Two fixed the failing line and failed on the next line of
the same case. vitest's case ``line`` is where the test is DECLARED, so the brief pointed at the
``it(`` line and never showed the assertion. The brief now carries the failing line, from the
failure's own frames, and the lines around it as the repair will edit them.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.impl.repair_handlers import (
    QATestRepairHandler,
    failing_line_excerpts,
)
from squadops.capabilities.handlers.test_runner import (
    RunTestsResult,
    failed_tests_pass_row,
    failing_cases,
    parse_vitest_failure_rows,
)
from squadops.prompts.renderer import RequestTemplateRenderer

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_SUITE = "frontend/src/__tests__/run_views.test.jsx"
_SUITE_TEXT = "\n".join(
    [f"// line {n}" for n in range(1, 205)]
    + ["  it('submits the join form', async () => {"]  # 205: where vitest says the test is
    + [f"    // step {n}" for n in range(206, 217)]
    + ["    expect(apiFetch).toHaveBeenCalledWith('/runs/1/join')"]  # 217: where it failed
    + [f"    // after {n}" for n in range(218, 231)]
)


def _vitest_report() -> dict:
    """The JSON report shape vitest writes: ``location`` is the test's declaration, the
    failure's own stack names the assertion's line."""
    return {
        "testResults": [
            {
                "name": f"/tmp/qa_node_x/{_SUITE}",
                "status": "failed",
                "assertionResults": [
                    {
                        "title": "submits the join form",
                        "status": "failed",
                        "location": {"line": 205, "column": 3},
                        "failureMessages": [
                            "AssertionError: expected apiFetch to be called with '/runs/1/join'\n"
                            f"    at /tmp/qa_node_x/{_SUITE}:217:22\n"
                            "    at file:///tmp/qa_node_x/node_modules/vitest/dist/x.js:1:1"
                        ],
                    }
                ],
            }
        ]
    }


def _evidence() -> dict:
    rows = parse_vitest_failure_rows(_vitest_report(), "/tmp/qa_node_x", [_SUITE])
    row = failed_tests_pass_row(
        RunTestsResult(executed=True, exit_code=1, runner="vitest", test_failures=tuple(rows))
    )
    return {"validation_result": {"passed": False, "checks": [row]}}


def _context():
    llm = AsyncMock()
    llm.chat_stream_with_usage.return_value = MagicMock(
        content="no fences", prompt_tokens=1, completion_tokens=1, reasoning_tokens=None
    )
    llm.default_model = "m"
    ports = MagicMock()
    ports.llm = llm
    ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ports.llm_observability = None
    ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    ctx = MagicMock()
    ctx.ports = ports
    ctx.role_id = "qa"
    ctx.task_id = "repair-run_ab12cd34-00-qa.test_repair"
    ctx.correlation_context = None
    return ctx


async def test_the_brief_shows_the_line_the_case_failed_on_not_where_it_is_declared():
    """Wiring, entered at ``handle`` through the runner's own row builder and the real
    renderer and templates. Bug this catches: the brief pointing the repair at line 205 (the
    ``it(`` line) with the failing assertion at 217 nowhere in view — the 1.8.1 shape where
    the repair edited near the failure and failed again on it."""
    ctx = _context()
    await QATestRepairHandler().handle(
        ctx,
        {
            "prd": "Runs",
            "failed_task_type": "qa.test",
            "failure_evidence": _evidence(),
            "expected_artifacts": [_SUITE],
            "acceptance_workspace_files": {_SUITE: _SUITE_TEXT},
        },
    )
    prompt = ctx.ports.llm.chat_stream_with_usage.await_args_list[0].args[0][-1].content

    assert f"`{_SUITE}:217` › submits the join form" in prompt
    assert "→  217 |     expect(apiFetch).toHaveBeenCalledWith('/runs/1/join')" in prompt
    assert f"`{_SUITE}:205`" not in prompt


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        # vitest: the declaration line, and the failure's innermost frame in its own file
        (
            {
                "file": "a.test.jsx",
                "title": "t",
                "line": 205,
                "frames": [
                    {"file": "a.test.jsx", "line": 210},
                    {"file": "src/View.jsx", "line": 3},
                    {"file": "a.test.jsx", "line": 217},
                ],
            },
            217,
        ),
        # an app frame last: the case's own innermost frame, never the app's
        (
            {
                "file": "a.test.jsx",
                "title": "t",
                "line": 205,
                "frames": [
                    {"file": "a.test.jsx", "line": 130},
                    {"file": "src/View.jsx", "line": 103},
                ],
            },
            130,
        ),
        # no frames (a suite-level failure, or an older row): the runner's own line
        ({"file": "a.test.jsx", "title": "t", "line": 12}, 12),
    ],
)
def test_the_failing_line_is_the_cases_innermost_frame_in_its_own_file(row, expected):
    (case,) = failing_cases([row])
    assert case["failing_line"] == expected


def test_an_excerpt_is_shown_only_for_a_file_and_line_in_hand():
    """Bug this catches: an excerpt of the wrong file, or one past the end of the suite."""
    cases = [
        {"file": "a.test.jsx", "title": "t", "line": 1, "failing_line": 3},
        {"file": "missing.test.jsx", "title": "u", "line": 1, "failing_line": 2},
        {"file": "a.test.jsx", "title": "v", "line": 1, "failing_line": 99},
    ]
    out = failing_line_excerpts(cases, {"a.test.jsx": "one\ntwo\nthree\nfour"})

    assert (
        out
        == "`a.test.jsx:3` › t\n```\n     1 | one\n     2 | two\n→    3 | three\n     4 | four\n```"
    )
