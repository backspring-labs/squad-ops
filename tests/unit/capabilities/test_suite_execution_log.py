"""qa.test records what the runner did (#935).

Bug this guards: whether the suite actually RAN was recoverable only from an artifact a
human had to open. `tests_pass` is exit-code driven, so "did not execute" and "executed
and passed" sit one keystroke apart in the record and neither left a log line. When a
window roll needs triage the first question is what the runner did, and the answer should
not require archaeology.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pytest

from squadops.capabilities.handlers.cycle.qa_test import QATestHandler

pytestmark = [pytest.mark.domain_capabilities]


@dataclass
class _Capability:
    test_framework: str = "vitest"
    test_timeout_seconds: int = 60


@dataclass
class _Result:
    executed: bool = True
    exit_code: int = 0
    tests_passed: bool = True
    test_file_count: int = 6
    source_file_count: int = 12
    summary: str = "6 files, 17 tests"
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    uncollected_test_files: tuple[str, ...] = field(default=())


async def _run(monkeypatch, result: _Result):
    async def _fake(*_a, **_kw):
        return result

    monkeypatch.setattr("squadops.capabilities.handlers.test_runner.run_build_validation", _fake)
    return await QATestHandler._run_test_suite(_Capability(), {"a.ts": "x"}, [])


async def test_a_passing_run_is_recorded_with_its_counts(monkeypatch, caplog):
    with caplog.at_level(logging.INFO, logger="squadops.capabilities.handlers.cycle.qa_test"):
        await _run(monkeypatch, _Result())
    line = next(m for m in caplog.messages if "suite:" in m)
    assert "executed=True" in line
    assert "exit_code=0" in line
    assert "test_files=6" in line
    assert "framework=vitest" in line


async def test_a_suite_that_never_executed_is_distinguishable_from_one_that_passed(
    monkeypatch, caplog
):
    """The whole point. Exit code 0 with executed=False is not a green suite, and the
    stored record could not tell the two apart."""
    never_ran = _Result(executed=False, exit_code=0, tests_passed=False, error="npm not found")
    with caplog.at_level(logging.INFO, logger="squadops.capabilities.handlers.cycle.qa_test"):
        await _run(monkeypatch, never_ran)
    line = next(m for m in caplog.messages if "suite:" in m)
    assert "executed=False" in line
    assert "npm not found" in line


async def test_uncollected_files_are_named_beside_the_counts(monkeypatch, caplog):
    """A file the runner never collected verifies nothing while the collected ones read
    green — SIP-0104 roll 1 shipped exactly that, and a count of test FILES cannot
    distinguish it."""
    result = _Result(uncollected_test_files=("__tests__/scaffold/vc-probe-api-runs.test.ts",))
    with caplog.at_level(logging.INFO, logger="squadops.capabilities.handlers.cycle.qa_test"):
        await _run(monkeypatch, result)
    line = next(m for m in caplog.messages if "suite:" in m)
    assert "vc-probe-api-runs.test.ts" in line
    assert "test_files=6" in line  # the count still reads green beside it


async def test_the_report_artifact_is_unchanged(monkeypatch):
    """Instrument only — the artifact a human opens must not move."""
    _result, report = await _run(monkeypatch, _Result())
    assert report["name"] == "test_report.md"
    assert "**Exit code:** 0" in report["content"]
