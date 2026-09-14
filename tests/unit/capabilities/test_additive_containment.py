"""#1022: containment rules for author-written additive suites — the gate's rules.

Every V7 counted red was additive-suite-side while all nine delivered applications of
the arc passed independent boot audits — the apps were fine, the tests were not. Each
test names the bug the rule catches, and the over-rejection cases matter as much: a rule
that fires on legitimate suites costs an authoring retry on every roll.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.additive_containment import (
    RULE_LIVE_SERVER_FETCH,
    RULE_NO_APPLICATION_INVOCATION,
    assess_additive_suite,
    containment_findings,
)
from squadops.capabilities.scaffold import app_invocation_for

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"
NEXTJS = app_invocation_for("nextjs_ts")
REACT = app_invocation_for("fullstack_fastapi_react")


def _f(name: str, content: str) -> dict:
    return {"name": name, "content": content}


def _rules(path: str, content: str, invocation=NEXTJS) -> list[str]:
    return [f.rule for f in containment_findings(path, content, invocation)]


_GOOD = """
import { describe, expect, it } from 'vitest'
import * as route from '@/app/api/runs/route'
describe('runs', () => { it('lists', async () => { expect((await route.GET(new Request('http://test/api/runs'))).status).toBe(200) }) })
"""


def test_a_legitimate_suite_produces_no_findings():
    """The control that decides whether anyone trusts the rest. A suite that calls the
    handler directly and imports the route is exactly what the scaffold shells do.
    The handler call passes an absolute URL to ``new Request(...)``, which is correct
    and must NOT read as a live fetch."""
    assert _rules("__tests__/runs.test.ts", _GOOD) == []


@pytest.mark.parametrize(
    "body",
    [
        "const r = await fetch('http://localhost:3000/api/runs')",
        'const r = await fetch("https://127.0.0.1:3000/api/runs")',
        "import request from 'supertest'\nimport * as route from '@/app/api/runs/route'",
        "const r = await axios.get('http://localhost:3000/api/runs')",
    ],
)
def test_a_live_server_call_is_flagged(body):
    """C3 (`cyc_6495d9870587`): the additive suite fetched a server that never exists
    under vitest — three qa repairs, no convergence, AFTER #877's prompt guidance
    shipped. Guidance did not contain it; the gate names it."""
    content = "import * as route from '@/app/api/runs/route'\n" + body
    assert _rules("__tests__/x.test.ts", content) == [RULE_LIVE_SERVER_FETCH]


def test_a_suite_invoking_nothing_of_the_application_is_flagged():
    """The self-mocking precondition (#915): a file that stubs `global.fetch` and
    imports no route can only assert against its own stub. V7 attempt-2 roll 1 banked
    exactly that file, and nothing flagged it in-cycle."""
    content = "vi.spyOn(global, 'fetch').mockResolvedValueOnce({} as any)\nit('x', () => {})"
    findings = containment_findings("__tests__/x.test.ts", content, NEXTJS)
    assert [f.rule for f in findings] == [RULE_NO_APPLICATION_INVOCATION]
    # The author is told what THIS stack counts, in words, not shown a regex.
    assert "app/api/**/route" in findings[0].detail


def test_reaching_the_app_only_through_its_browser_client_is_not_invoking_it():
    """The C3/C4 shape after #1052's reporting window: both suites imported `@/lib/api`,
    the browser client, and nothing else — under vitest that reaches no server. A
    first-party import is not the same as invoking the application; the stack's own
    definition (`AppInvocation.invocation_import`) decides, and it says a route module."""
    content = "import { listRuns } from '@/lib/api'\nit('x', async () => { await listRuns() })"
    assert _rules("__tests__/x.test.ts", content) == [RULE_NO_APPLICATION_INVOCATION]


@pytest.mark.parametrize(
    ("path", "load", "invocation"),
    [
        (
            "__tests__/runs-ui.test.ts",
            "const joinRoute = await import('@/app/api/runs/[run_id]/join/route')",
            NEXTJS,
        ),
        (
            "__tests__/runs.test.ts",
            "const { POST } = (await import(`@/app/api/runs/route`))",
            NEXTJS,
        ),
        (
            "frontend/src/__tests__/x.test.jsx",
            "const { default: RunsListView } = await import('../views/RunsListView')",
            REACT,
        ),
    ],
)
def test_a_module_loaded_by_dynamic_import_invokes_the_application(path, load, invocation):
    """#1533: 1.8.0 deploy A's Next.js checkpoint (``cyc_79f70a0bbac1``) was rejected on a
    suite that loaded the join handler with ``await import(...)`` and called it with a
    ``new Request(...)`` — the in-process model exactly — because the stack's pattern
    accepted only an import statement or a ``require``. The load is stack-neutral
    (``JS_MODULE_LOAD``); which module counts stays each stack's."""
    content = f"import {{ expect, it }} from 'vitest'\nit('x', async () => {{\n  {load}\n}})\n"
    assert _rules(path, content, invocation) == []


async def test_the_qa_handlers_containment_row_passes_a_dynamically_loaded_route_suite():
    """Wiring (#1533, anti-pattern 6a): the verdict tonight's suite got came from the qa
    handler's typed-acceptance seam, which injects ``additive_containment`` per suite with
    the stack from the cycle's config — so the test enters there, not at the rule."""
    from squadops.capabilities.handlers.cycle.qa_test import QATestHandler

    suite = (
        "import { expect, it } from 'vitest'\n"
        "it('rejects a duplicate join', async () => {\n"
        "  const joinRoute = await import('@/app/api/runs/[run_id]/join/route')\n"
        "  const res = await joinRoute.POST(new Request('http://test/api/runs/r/join', "
        "{ method: 'POST', body: JSON.stringify({ name: 'dave' }) }), "
        "{ params: { run_id: 'r' } })\n"
        "  expect(res.status).toBe(409)\n"
        "})\n"
    )
    checks: list[dict] = []
    await QATestHandler()._evaluate_typed_acceptance(
        {"acceptance_criteria": [], "resolved_config": {"build_profile": "nextjs_ts"}},
        [{"name": "__tests__/runs-ui.test.ts", "type": "test", "content": suite}],
        checks,
        [],
        {},
    )
    rows = [c for c in checks if c["check"] == "acceptance:additive_containment"]
    assert [(r["params"]["file"], r["status"]) for r in rows] == [
        ("__tests__/runs-ui.test.ts", "passed")
    ]


@pytest.mark.parametrize(
    "not_a_load",
    [
        "vi.mock('@/app/api/runs/route')",
        "const actual = await vi.importActual('@/app/api/runs/route')",
        "vi.mock('@/app/api/runs/route', () => import('./fake-route'))",
    ],
)
def test_naming_a_route_module_without_loading_it_is_still_not_invoking_it(not_a_load):
    """The over-acceptance guard for #1533: widening the load forms must not let a mock
    of the route, or a mock factory that loads something else, read as invoking the app."""
    content = f"import {{ it }} from 'vitest'\n{not_a_load}\nit('x', () => {{}})\n"
    assert RULE_NO_APPLICATION_INVOCATION in _rules("__tests__/x.test.ts", content)


def test_a_url_in_prose_or_a_fixture_is_not_an_execution_model_violation():
    """The finding must mean something: matching any URL anywhere would fire on a
    comment or a seeded fixture value."""
    content = (
        "import * as route from '@/app/api/runs/route'\n"
        "// see http://localhost:3000/api/runs for the shape\n"
        "const seeded = { link: 'https://example.com/x' }\n"
        "it('x', () => { expect(seeded.link).toBeTruthy() })"
    )
    assert _rules("__tests__/x.test.ts", content) == []


def test_the_react_stack_judges_by_its_own_definition():
    """Stack awareness (#1126, #1131): on the React stack "invokes the application" is
    rendering the real App or a view — an `app/api` import means nothing there, and a
    view render must not be flagged by a rule written for Next.js."""
    renders_view = (
        "import { render, screen } from '@testing-library/react'\n"
        "import { MemoryRouter } from 'react-router-dom'\n"
        "import RunDetailView from '../views/RunDetailView'\n"
        "it('x', () => { render(<MemoryRouter><RunDetailView /></MemoryRouter>) })"
    )
    assert _rules("frontend/src/__tests__/x.test.jsx", renders_view, REACT) == []
    assert _rules("frontend/src/__tests__/x.test.jsx", "it('x', () => {})", REACT) == [
        RULE_NO_APPLICATION_INVOCATION
    ]


@pytest.mark.parametrize("name", ["lib/store.ts", "app/page.tsx", "README.md", "vitest.config.ts"])
def test_non_suite_files_are_not_judged(name):
    """A source file importing nothing, or naming a URL, is somebody else's concern —
    which files are suites is the stack's declaration (`is_suite`)."""
    assert assess_additive_suite([_f(name, "const u = 'http://localhost:3000'")], NEXTJS) == []


def test_an_unknown_stack_judges_nothing():
    """No declaration, no verdict: the caller records not-inspected rather than clean
    (#986). Silently passing would read as a contained suite."""
    assert assess_additive_suite([_f("__tests__/x.test.ts", "it('x', () => {})")], None) == []


def test_findings_are_ordered_so_two_runs_are_comparable():
    files = [
        _f("__tests__/b.test.ts", "it('x',()=>{})"),
        _f("__tests__/a.test.ts", "it('x',()=>{})"),
    ]
    assert [f.path for f in assess_additive_suite(files, NEXTJS)] == [
        "__tests__/a.test.ts",
        "__tests__/b.test.ts",
    ]


class TestReplays:
    """The stored suites the gate is built from. Rejected: the C3/C4 corpus reds and
    V7 slot 3's first repair. Controls: the V7 slot-2 and slot-3 greens, the accepted
    1.6.6 and 1.7.0 rolls' suites on both stacks — a rule that fires on any of these
    would have cost a green roll an authoring retry."""

    @pytest.mark.parametrize(
        "name",
        [
            "v7-c3-repair-00-api-runs.test.ts",
            "v7-c4-repair-00-runs.test.ts",
            "v7-slot-3-repair-00-runs.test.ts",
        ],
    )
    def test_the_corpus_reds_are_rejected_for_invoking_nothing(self, name):
        content = (_REPLAYS / name).read_text(encoding="utf-8")
        assert _rules(name, content) == [RULE_NO_APPLICATION_INVOCATION]

    @pytest.mark.parametrize(
        ("name", "invocation"),
        [
            ("v7-slot-2-green-runs.test.ts", NEXTJS),
            ("v7-slot-3-green-runs.test.ts", NEXTJS),
            ("1-6-6-nextjs-roll-1-runs.test.ts", NEXTJS),
            ("1-7-0-nextjs-roll-6-runs.test.ts", NEXTJS),
            ("1-7-0-roll-6-green.scaffold.test.ts", NEXTJS),
            ("1-6-6-react-roll-1-frontend-harness.test.jsx", REACT),
            ("1-6-6-react-roll-6-frontend-suite.test.jsx", REACT),
        ],
    )
    def test_the_accepted_rolls_suites_pass(self, name, invocation):
        content = (_REPLAYS / name).read_text(encoding="utf-8")
        assert _rules(name, content, invocation) == []
