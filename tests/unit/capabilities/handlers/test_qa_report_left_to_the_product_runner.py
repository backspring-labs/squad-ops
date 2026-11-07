"""What ``test_report.md`` says of a suite the qa image can't run (#2949).

What bugs would these catch?
- **A hand-off read as a failure:** the report said "tests not run" with exit code -1 and an error
  section, seconds before the product's runner passed the task. The owner read it as a failure.
- **A real non-run hidden by the fix:** a suite with no test files, or any other runner's non-run,
  keeps the error and the exit code.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.cycle.qa_test import _test_report_lines
from squadops.capabilities.handlers.test_runner import LEFT_TO_THE_PRODUCT_RUNNER, run_suite
from squadops.stacks.development_profiles import TEST_FRAMEWORK_PRODUCT_RUNNER

pytestmark = [pytest.mark.domain_capabilities]

_SOURCE = [{"name": "src/a.js", "content": "export const a = 1;\n"}]
_TEST = [{"name": "test/a.test.js", "content": "// a test\n"}]


async def test_a_suite_left_to_the_product_runner_reports_the_hand_off_and_no_failure():
    """Entered at ``run_suite``, the dispatch the handler calls."""
    result = await run_suite(TEST_FRAMEWORK_PRODUCT_RUNNER, _SOURCE, _TEST)

    report = "".join(_test_report_lines(result))

    assert f"**Result:** {LEFT_TO_THE_PRODUCT_RUNNER}" in report
    assert "not run" not in report
    assert "Exit code" not in report
    assert "## Error" not in report


async def test_a_product_with_no_test_files_still_reports_its_failure():
    result = await run_suite(TEST_FRAMEWORK_PRODUCT_RUNNER, _SOURCE, [])

    report = "".join(_test_report_lines(result))

    assert "**Result:** tests not run: no test files provided" in report
    assert "**Exit code:** -1" in report
    assert "## Error\n\nno test files provided" in report
