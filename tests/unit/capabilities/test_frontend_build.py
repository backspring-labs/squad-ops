"""Tests for the frontend build-acceptance check (#276).

Bug this guards: a Vite frontend can pass vitest unit tests yet fail to build
(e.g. missing root ``index.html``), shipping a non-runnable deliverable green.
``run_frontend_build`` must FAIL when the build ran and errored, and must SKIP
(not fail) when it can't assess (no frontend, no package.json, no node).
"""

from __future__ import annotations

import asyncio

import pytest

import squadops.capabilities.handlers.test_runner as tr
from squadops.capabilities.dev_capabilities import (
    TEST_FRAMEWORK_BOTH,
    TEST_FRAMEWORK_PYTEST,
    TEST_FRAMEWORK_VITEST,
)
from squadops.capabilities.handlers.test_runner import (
    BuildCheckResult,
    RunTestsResult,
    run_build_validation,
    run_frontend_build,
)

pytestmark = [pytest.mark.domain_capabilities]

_PKG_WITH_BUILD = '{"name": "fe", "scripts": {"build": "vite build"}}'


class _FakeProc:
    def __init__(self, returncode: int):
        self.returncode = returncode

    async def communicate(self):
        return (b"", b"build output")

    def kill(self):
        pass

    async def wait(self):
        pass


def _fake_exec(returncodes: list[int]):
    """Return a create_subprocess_exec stand-in yielding the given exit codes."""
    it = iter(returncodes)

    async def _exec(*_args, **_kwargs):
        return _FakeProc(next(it))

    return _exec


# --- BuildCheckResult.failed semantics (skips are not failures) ---------------


@pytest.mark.parametrize(
    "ran,ok,expected_failed",
    [(True, False, True), (True, True, False), (False, False, False), (False, True, False)],
)
def test_failed_property(ran, ok, expected_failed):
    assert BuildCheckResult(ran=ran, ok=ok).failed is expected_failed


# --- Skip paths (no subprocess, deterministic) --------------------------------


async def test_skips_when_no_frontend_source():
    result = await run_frontend_build([{"path": "backend/main.py", "content": "x = 1"}])
    assert result.ran is False and result.failed is False


async def test_skips_when_no_package_json():
    result = await run_frontend_build(
        [{"path": "frontend/src/main.jsx", "content": "export default 1"}]
    )
    assert result.ran is False
    assert "package.json" in result.error


# --- Build outcome (mocked subprocess) ----------------------------------------


async def test_build_failure_is_a_failure(monkeypatch):
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", _fake_exec([0, 1])
    )  # install ok, build fails
    result = await run_frontend_build(
        [{"path": "frontend/package.json", "content": _PKG_WITH_BUILD}]
    )
    assert result.ran is True
    assert result.ok is False
    assert result.failed is True
    assert result.exit_code == 1


async def test_build_success(monkeypatch):
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", _fake_exec([0, 0])
    )  # install ok, build ok
    result = await run_frontend_build(
        [{"path": "frontend/package.json", "content": _PKG_WITH_BUILD}]
    )
    assert result.ran is True
    assert result.ok is True
    assert result.failed is False


async def test_install_failure_is_skip_not_failure(monkeypatch):
    """A broken toolchain (npm install fails) can't assess the build — that's a
    SKIP, not a deliverable failure (don't punish the app for our env)."""
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec([1]))  # install fails
    result = await run_frontend_build(
        [{"path": "frontend/package.json", "content": _PKG_WITH_BUILD}]
    )
    assert result.ran is False
    assert result.failed is False
    assert "install" in result.error


async def test_missing_node_is_skip_not_failure(monkeypatch):
    async def _raise(*_a, **_k):
        raise FileNotFoundError("npm")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _raise)
    result = await run_frontend_build(
        [{"path": "frontend/package.json", "content": _PKG_WITH_BUILD}]
    )
    assert result.ran is False
    assert result.failed is False


# --- run_build_validation: framework dispatch + blocking-build fold ------------
# The QA handler is framework-agnostic; this orchestration lives in test_runner.


async def test_build_validation_backend_only_skips_build(monkeypatch):
    """pytest/backend-only capabilities have no frontend — never invoke a build."""
    called = {"build": False}

    async def _generated(*_a, **_k):
        return RunTestsResult(executed=True, exit_code=0)

    async def _build(*_a, **_k):
        called["build"] = True
        return BuildCheckResult(ran=True, ok=False)

    monkeypatch.setattr(tr, "run_generated_tests", _generated)
    monkeypatch.setattr(tr, "run_frontend_build", _build)
    result = await run_build_validation(TEST_FRAMEWORK_PYTEST, [], [{"path": "t", "content": "x"}])
    assert result.exit_code == 0
    assert called["build"] is False


async def test_build_validation_build_failure_blocks_even_when_tests_pass(monkeypatch):
    """A frontend build failure is blocking even where fullstack tests passed (D13)."""

    async def _fullstack(*_a, **_k):
        return RunTestsResult(executed=True, exit_code=0)  # tests green

    async def _build(*_a, **_k):
        return BuildCheckResult(ran=True, ok=False, exit_code=2, error="vite build failed")

    monkeypatch.setattr(tr, "run_fullstack_tests", _fullstack)
    monkeypatch.setattr(tr, "run_frontend_build", _build)
    result = await run_build_validation(TEST_FRAMEWORK_BOTH, [], [{"path": "t", "content": "x"}])
    assert result.tests_passed is False
    assert result.exit_code == 2
    assert "vite build failed" in result.error


async def test_build_validation_build_skip_does_not_fail(monkeypatch):
    """A build skip (no node) must not turn a passing suite red."""

    async def _node(*_a, **_k):
        return RunTestsResult(executed=True, exit_code=0)

    async def _build(*_a, **_k):
        return BuildCheckResult(ran=False, error="npm not found")

    monkeypatch.setattr(tr, "run_node_tests", _node)
    monkeypatch.setattr(tr, "run_frontend_build", _build)
    result = await run_build_validation(TEST_FRAMEWORK_VITEST, [], [{"path": "t", "content": "x"}])
    assert result.tests_passed is True
