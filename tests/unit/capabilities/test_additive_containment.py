"""#1022: containment findings for author-written additive suites.

Every V7 counted red was additive-suite-side while all nine delivered applications of
the arc passed independent boot audits — the apps were fine, the tests were not. These
findings are banked, not enforced; each test names the bug the finding catches, and the
over-rejection cases matter as much, because a finding that fires on legitimate suites
is one nobody will act on.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.additive_containment import assess_additive_suite, is_additive_test


def _f(name: str, content: str) -> dict:
    return {"name": name, "content": content}


_GOOD = """
import { describe, expect, it } from 'vitest'
import * as route from '@/app/api/runs/route'
describe('runs', () => { it('lists', async () => { expect((await route.GET(new Request('http://test/api/runs'))).status).toBe(200) }) })
"""


def test_a_legitimate_suite_produces_no_findings():
    """The control, and the one that decides whether anyone trusts the rest. A suite
    that calls the handler directly and imports the route is exactly what the scaffold
    shells do — flagging it would make every roll noisy and the findings ignorable.

    Note the handler call passes an absolute URL to `new Request(...)`, which is correct
    and must NOT read as a live fetch.
    """
    assert assess_additive_suite([_f("__tests__/runs.test.ts", _GOOD)]) == []


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
    under vitest — three qa repairs, no convergence, and it happened AFTER #877's
    prompt guidance shipped. Guidance did not contain it; this names it."""
    content = "import * as route from '@/app/api/runs/route'\n" + body
    findings = assess_additive_suite([_f("__tests__/x.test.ts", content)])
    assert len(findings) == 1
    assert "fetches a live server" in findings[0]


def test_a_suite_importing_nothing_is_flagged():
    """The self-mocking precondition (#915): a file that stubs `global.fetch` and
    imports no route can only assert against its own stub. V7 attempt-2 roll 1 banked
    exactly that file, and nothing flagged it in-cycle."""
    content = "vi.spyOn(global, 'fetch').mockResolvedValueOnce({} as any)\nit('x', () => {})"
    findings = assess_additive_suite([_f("__tests__/x.test.ts", content)])
    assert len(findings) == 1
    assert "imports no application module" in findings[0]


@pytest.mark.parametrize(
    "spec", ["@/app/api/runs/route", "@/lib/store", "../app/api/runs/route", "./helpers"]
)
def test_any_first_party_import_satisfies_the_subject_requirement(spec):
    """Over-rejection guard. A relative helper import is still authorship reaching
    outside itself; demanding a specific module would flag suites that compose through
    a local fixture, which is normal and correct."""
    content = f"import x from '{spec}'\nit('x', () => {{}})"
    assert assess_additive_suite([_f("__tests__/x.test.ts", content)]) == []


def test_a_url_in_prose_or_a_fixture_is_not_an_execution_model_violation():
    """The finding must mean something. Matching any URL anywhere would fire on a
    comment or a seeded fixture value, and a finding that cries wolf is one the next
    author learns to skip."""
    content = (
        "import * as route from '@/app/api/runs/route'\n"
        "// see http://localhost:3000/api/runs for the shape\n"
        "const seeded = { link: 'https://example.com/x' }\n"
        "it('x', () => { expect(seeded.link).toBeTruthy() })"
    )
    assert assess_additive_suite([_f("__tests__/x.test.ts", content)]) == []


def test_scaffold_shells_are_not_judged_as_additive():
    """Shells are generated, gated, and spine-frozen. Judging them here would report
    the generator's own output as an authoring defect — and the spine legitimately
    constructs absolute-URL Requests."""
    assert is_additive_test("__tests__/scaffold/vc-probe-api-runs.scaffold.test.ts") is False
    assert (
        assess_additive_suite([_f("__tests__/scaffold/x.scaffold.test.ts", "fetch('http://x/')")])
        == []
    )


@pytest.mark.parametrize("name", ["lib/store.ts", "app/page.tsx", "README.md", "vitest.config.ts"])
def test_non_test_files_are_not_judged(name):
    """A source file importing nothing, or naming a URL, is somebody else's concern."""
    assert assess_additive_suite([_f(name, "const u = 'http://localhost:3000'")]) == []


def test_findings_are_ordered_so_two_runs_are_comparable():
    """Emission order is not stable; a diff between two rolls' findings has to be
    readable without sorting by hand."""
    files = [
        _f("__tests__/b.test.ts", "it('x',()=>{})"),
        _f("__tests__/a.test.ts", "it('x',()=>{})"),
    ]
    findings = assess_additive_suite(files)
    assert [f.split(":")[0] for f in findings] == ["__tests__/a.test.ts", "__tests__/b.test.ts"]
