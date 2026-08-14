"""Gate 2 end-to-end: the scaffold really executes against the walking skeleton.

The unit corpus proves the classifier against measured report shapes; this proves the
whole gate against a real Node toolchain — npm install, vitest collection, shell
execution against the stubs. Requires npm (the agent-container toolchain); skipped where
Node is absent. First measured 2026-08-14 in node:20-alpine on the reference scaffold:
9 tests collected (8 shells + harness), harness passed, 8 shells failed as the expected
stub assertion wall, verdict valid.
"""

from __future__ import annotations

import shutil

import pytest

from squadops.capabilities.handlers.scaffold_execution import run_skeleton_execution_gate
from squadops.capabilities.scaffold import expand
from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("npm") is None, reason="requires the Node toolchain"),
]

_TIMEOUT = 420


@pytest.fixture(scope="module")
def reference():
    manifest = manifest_for_stack("nextjs_ts")
    tree = expand(manifest)
    return tree, emit_verification_scaffold(manifest, expanded=tree)


async def test_the_reference_scaffold_executes_cleanly_against_the_skeleton(reference):
    """Gate 2's positive exit: every shell collects and executes; the only failures are
    the expected stub assertion wall (SIP-0098 §7)."""
    tree, emission = reference
    verdict = await run_skeleton_execution_gate(
        tree, list(emission.files), timeout_seconds=_TIMEOUT
    )
    assert verdict.executed, verdict.error
    assert verdict.scaffold_valid, verdict.mechanical_failures
    assert len(verdict.collected_files) == len(emission.files)
    assert verdict.assertion_failures == len(emission.files)
    assert verdict.missing_files == ()


async def test_a_garbage_fill_degrades_one_file_and_the_rest_still_execute(reference):
    """Gate 3's blast-radius exit, executed for real: a containment-clean but
    syntactically broken fill merges into its slot, that ONE file dies at collection,
    and every other shell still executes its expected stub assertion."""
    from squadops.capabilities.verification_scaffold_fill import merge_fills, parse_fill_emission

    tree, emission = reference
    merged = merge_fills(
        list(emission.files),
        emission.manifest,
        parse_fill_emission(
            "```fill:slot-vc-probe-api-runs\n))) this is not TypeScript {{{\n```\n"
        ),
    )
    files = [{"name": f.path, "content": f.content} for f in merged.files]
    verdict = await run_skeleton_execution_gate(tree, files, timeout_seconds=_TIMEOUT)
    assert verdict.executed, verdict.error
    assert not verdict.scaffold_valid
    assert all(
        "vc-probe-api-runs.scaffold.test.ts" in failure for failure in verdict.mechanical_failures
    ), verdict.mechanical_failures
    # the other seven shells collected and executed to their expected stub failures
    assert verdict.assertion_failures == 7


async def test_an_injected_runtime_defect_is_caught_as_mechanical(reference):
    """The dynamic decisive case: statically well-formed (imports resolve, handlers
    exported, statuses declared) but runtime-broken — a defect only execution can see."""
    tree, emission = reference
    files = [
        (
            {
                "name": f["name"],
                "content": f["content"].replace("new Request(", "new Requests(", 1),
            }
            if f["name"] == "__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts"
            else dict(f)
        )
        for f in emission.files
    ]
    verdict = await run_skeleton_execution_gate(tree, files, timeout_seconds=_TIMEOUT)
    assert verdict.executed, verdict.error
    assert not verdict.scaffold_valid
    assert any(
        "vc-probe-api-runs.scaffold.test.ts" in failure and "Requests" in failure
        for failure in verdict.mechanical_failures
    )
