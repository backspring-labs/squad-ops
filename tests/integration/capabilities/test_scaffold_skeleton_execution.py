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
from squadops.capabilities.handlers.test_runner import run_build_validation, run_suite
from squadops.stacks.development_profiles import TEST_FRAMEWORK_VITEST
from squadops.stacks.scaffold import expand
from squadops.stacks.verification_scaffold_emission import emit_verification_scaffold
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


#: A suite that renders a scaffold page the way the qa role does on this stack: no JSX in the
#: suite (the runner collects `.test.ts` only), so the page is built with `createElement` and
#: rendered to a string. `app/page.tsx` is the manifest's root client route.
_PAGE_RENDER_SUITE = (
    "__tests__/page-render.test.ts",
    """import { describe, it, expect } from 'vitest'
import { createElement } from 'react'
import { renderToString } from 'react-dom/server'
import Page from '@/app/page'

describe('the root page', () => {
  it('renders', () => {
    expect(renderToString(createElement(Page))).toContain('<main')
  })
})
""",
)


def _as_runner_files(files):
    return [{"path": f["name"], "content": f["content"]} for f in files]


async def test_a_suite_that_renders_a_page_passes_under_the_seeded_config(reference):
    """#2394: through the call qa.test makes, a suite that renders a page runs to its
    assertion, and `next build` still accepts the config that made it possible."""
    tree, _ = reference
    path, content = _PAGE_RENDER_SUITE
    result = await run_build_validation(
        TEST_FRAMEWORK_VITEST,
        _as_runner_files(tree),
        [{"path": path, "content": content}],
        timeout_seconds=_TIMEOUT,
    )
    assert result.tests_passed, result.stdout + result.stderr
    assert path not in result.uncollected_test_files
    assert result.frontend_build is not None and result.frontend_build.ok, result.frontend_build


async def test_without_the_jsx_setting_the_same_suite_dies_inside_the_page(reference):
    """The control: with the seeded config's `esbuild.jsx` line removed, the suite above
    fails where the 2.3.1 Next.js roll did, so the test above is not passing by accident."""
    tree, _ = reference
    without = [
        (
            {**f, "content": f["content"].replace("  esbuild: { jsx: 'automatic' },\n", "")}
            if f["name"] == "vitest.config.ts"
            else f
        )
        for f in tree
    ]
    assert without != tree, "the seeded config no longer carries the line this control removes"
    path, content = _PAGE_RENDER_SUITE
    result = await run_suite(
        TEST_FRAMEWORK_VITEST,
        _as_runner_files(without),
        [{"path": path, "content": content}],
        timeout_seconds=_TIMEOUT,
    )
    assert result.executed, result.error
    assert result.exit_code != 0
    assert "React is not defined" in result.stdout + result.stderr


#: #2577: a route an increment adds, static beside the skeleton's ``[run_id]`` (which exports no
#: POST), and its criterion's test in each idiom. Invented, not any campaign's.
_ADDED_ROUTE = (
    "app/api/runs/import/route.ts",
    """export async function POST(request: Request) {
  return Response.json({ imported: (await request.json()).titles.length }, { status: 201 })
}
""",
)
_THROUGH_THE_CALLER = """import { describe, expect, it } from 'vitest'
import { callRoute } from '@/vitest.routes'

describe('T1: importing runs', () => {
  it('answers 201 with how many it imported', async () => {
    const res = await callRoute('POST', '/api/runs/import', {
      body: JSON.stringify({ titles: ['Hill repeats', 'Long slow'] }),
      headers: { 'content-type': 'application/json' },
    })
    expect(res.status).toBe(201)
    expect((await res.json()).imported).toBe(2)
  })
})
"""
_BY_IMPORTING_THE_MODULE = """import { describe, expect, it } from 'vitest'
import * as route from '@/app/api/runs/import/route'

describe('T1: importing runs', () => {
  it('answers 201 with how many it imported', async () => {
    const res = await route.POST(
      new Request('http://localhost/api/runs/import', {
        method: 'POST',
        body: JSON.stringify({ titles: ['Hill repeats', 'Long slow'] }),
      }),
    )
    expect(res.status).toBe(201)
  })
})
"""


@pytest.mark.parametrize(
    ("test_source", "reason"),
    [(_THROUGH_THE_CALLER, "discriminates"), (_BY_IMPORTING_THE_MODULE, "only_setup_failures")],
    ids=["through-the-route-caller", "importing-the-route-module"],
)
async def test_a_criterion_for_a_route_the_change_adds_discriminates_through_the_route_caller(
    reference, test_source, reason
):
    """#2577, through the increment evaluation itself (``evaluate_increment``, the runner the
    evaluation passes it). The 2.4 window's campaign 2 seed increment was rejected because its
    criterion test imported the route its change added: on the accepted tree the file failed at
    collection, ``only_setup_failures``, however correct the build. Bugs caught: a test through
    the scaffold's route caller still failing on the accepted tree before any assertion; or the
    caller missing from the criterion's bundle, so an accepted tree that predates it (this one
    is the skeleton without it) fails at collection again. The import idiom is the control."""
    from functools import partial

    from squadops.campaigns.acceptance_run import NewCriterion, evaluate_increment
    from squadops.campaigns.evaluator_trees import FileTree, TestSurface
    from squadops.stacks.stack_nextjs_ts import ROUTE_CALLER_PATH, STACK_NAME

    tree, _ = reference
    files = {f["name"]: f["content"].encode() for f in tree}
    accepted = FileTree.of({p: c for p, c in files.items() if p != ROUTE_CALLER_PATH})
    test_path = "__tests__/criteria/T1.test.ts"
    candidate = FileTree.of(
        {**files, _ADDED_ROUTE[0]: _ADDED_ROUTE[1].encode(), test_path: test_source.encode()}
    )

    evaluation = await evaluate_increment(
        increment_id="inc_import",
        accepted=accepted,
        candidate=candidate,
        surface=TestSurface.for_stack(STACK_NAME),
        new=[NewCriterion("T1", test_path)],
        frozen=[],
        declared_routes={},
        rendered={},
        unseeded=(),
        run=partial(run_suite, TEST_FRAMEWORK_VITEST, timeout_seconds=_TIMEOUT),
        invocation=(TEST_FRAMEWORK_VITEST,),
        retired=(),
    )

    [judged] = evaluation.discriminations
    assert judged.reason.value == reason
    assert judged.met is (reason == "discriminates")
