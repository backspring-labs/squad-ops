"""Tests for the frontend build-acceptance check (#276).

Bug this guards: a Vite frontend can pass vitest unit tests yet fail to build
(e.g. missing root ``index.html``), shipping a non-runnable deliverable green.
``run_frontend_build`` must FAIL when the build ran and errored, and must SKIP
(not fail) when it can't assess (no frontend, no package.json, no node).
"""

from __future__ import annotations

import asyncio

import pytest

from squadops.capabilities.handlers.test_runner import (
    BuildCheckResult,
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
