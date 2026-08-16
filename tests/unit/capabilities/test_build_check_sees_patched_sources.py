"""The build checks must judge the deliverable the suite actually ran against.

On the retest path the two inputs come from different eras. ``source_files`` is read
from the FAILED task's envelope, so it is pre-repair; ``test_files`` carries the patched
artifacts, and after a development repair those are the repaired *application* files.

The suite ran against the repaired code — that is why ``tests_pass`` went green — while
``run_frontend_build`` compiled only the stale set. So a correction could regress the
build and no check could see it, which is close to the worst property a correction loop
can have: the verdict describes code that is no longer the deliverable.

Diagnostic ``cyc_831dfe6ac551`` (2026-08-16) is the instance. A repair rewrote
``app/runs/new/page.tsx`` into something that does not typecheck; the suite passed, the
frontend build passed, the cycle was accepted, and the delivered app did not compile.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.test_runner import _effective_sources

pytestmark = [pytest.mark.domain_capabilities]

_STALE = {"path": "app/runs/new/page.tsx", "content": "api('/api/runs')  // pre-repair"}
_PATCHED = {"path": "app/runs/new/page.tsx", "content": "api('/runs')  // repaired, broken"}
_OTHER_SOURCE = {"path": "lib/store.ts", "content": "export function reset() {}"}
_A_TEST = {"path": "__tests__/api.test.ts", "content": "it('works', () => {})"}


def test_a_patched_source_replaces_the_stale_one():
    """Bug caught: the build compiles pre-repair code and passes.

    This is the diagnostic's exact shape — the patch is the deliverable, and the check
    that decides whether the deliverable builds must compile the patch.
    """
    effective = _effective_sources([_STALE, _OTHER_SOURCE], [_PATCHED, _A_TEST])
    by_path = {rec["path"]: rec["content"] for rec in effective}

    assert by_path["app/runs/new/page.tsx"] == _PATCHED["content"]
    assert by_path["lib/store.ts"] == _OTHER_SOURCE["content"]


def test_a_test_file_does_not_enter_the_build_input():
    """The deliverable is not the suite.

    Widening the overlay to the full union would change *what the build compiles* —
    emitted tests would start being typechecked. That may well be desirable (#939) but
    it is a separate decision, and smuggling it in under a staleness fix would make any
    resulting breakage impossible to attribute.
    """
    effective = _effective_sources([_OTHER_SOURCE], [_A_TEST])

    assert [rec["path"] for rec in effective] == ["lib/store.ts"]


def test_source_order_is_preserved():
    """Materialization order decides last-wins on collision downstream; a fix that
    reshuffled the deliverable would be a silent behavioural change riding along."""
    sources = [
        {"path": "a.ts", "content": "1"},
        {"path": "b.ts", "content": "2"},
        {"path": "c.ts", "content": "3"},
    ]
    effective = _effective_sources(sources, [{"path": "b.ts", "content": "patched"}])

    assert [rec["path"] for rec in effective] == ["a.ts", "b.ts", "c.ts"]
    assert effective[1]["content"] == "patched"


def test_no_patches_leaves_the_sources_untouched():
    """The initial (non-retest) path passes real test files and nothing else, and must
    stay byte-identical — otherwise this fix changes every cycle, not just corrected
    ones."""
    sources = [_STALE, _OTHER_SOURCE]

    assert _effective_sources(sources, [_A_TEST]) == sources


async def test_the_build_checks_receive_the_effective_sources(monkeypatch):
    """Bug caught: the helper is correct and nothing calls it.

    A pure-function test passes when the call site still hands over `source_files` —
    which is precisely the defect. This asserts through `run_build_validation` itself.
    """
    from squadops.capabilities.handlers import test_runner as tr

    seen: dict[str, list[dict[str, str]]] = {}

    async def _fake_node_tests(source_files, test_files, timeout_seconds=60):
        seen["tests"] = list(source_files)
        return tr.RunTestsResult(executed=True, exit_code=0, stdout="", stderr="")

    async def _fake_frontend_build(source_files, target_dir=None, timeout_seconds=120):
        seen["build"] = list(source_files)
        return tr.BuildCheckResult(ran=True, ok=True)

    monkeypatch.setattr(tr, "run_node_tests", _fake_node_tests)
    monkeypatch.setattr(tr, "run_frontend_build", _fake_frontend_build)

    await tr.run_build_validation("vitest", [_STALE, _OTHER_SOURCE], [_PATCHED, _A_TEST])

    built = {rec["path"]: rec["content"] for rec in seen["build"]}
    assert built["app/runs/new/page.tsx"] == _PATCHED["content"], (
        "the frontend build compiled the pre-repair page — the retest verdict would "
        "describe code that is no longer the deliverable"
    )


async def test_the_backend_import_check_also_receives_them(monkeypatch):
    """Bug caught: only the frontend path is fixed.

    The frontend assertion above passes while the backend check still receives
    `source_files` — a mutation that survived until this test existed. Stack #1 runs
    both checks, so a Python repair would have kept the same stale verdict.
    """
    from squadops.capabilities.handlers import test_runner as tr

    stale_py = {"path": "backend/routes.py", "content": "# pre-repair"}
    patched_py = {"path": "backend/routes.py", "content": "# repaired"}
    seen: dict[str, list[dict[str, str]]] = {}

    async def _fake_generated_tests(source_files, test_files, timeout_seconds=60):
        return tr.RunTestsResult(executed=True, exit_code=0, stdout="", stderr="")

    async def _fake_backend_check(source_files, timeout_seconds=120):
        seen["backend"] = list(source_files)
        return tr.BuildCheckResult(ran=True, ok=True)

    monkeypatch.setattr(tr, "run_generated_tests", _fake_generated_tests)
    monkeypatch.setattr(tr, "run_backend_import_check", _fake_backend_check)

    await tr.run_build_validation("pytest", [stale_py], [patched_py])

    checked = {rec["path"]: rec["content"] for rec in seen["backend"]}
    assert checked["backend/routes.py"] == patched_py["content"], (
        "the backend import check ran against pre-repair source"
    )
