"""SIP-0107 §38 step 6 — the structural path on the Next.js stack's own fixtures.

§39.7: the mechanism works across slot granularities. The FastAPI+React route module is revised
by function body (``test_structural_revision``); a Next.js route handler's fill is its ``try``
block, and a revision of it must leave the scaffold-owned signature and ``catch`` envelope — and
every sibling handler — byte-identical by construction. The same criteria as the first stack:
preservation by reconstruction (§39.2), a candidate that parses (§18), and nothing to restore.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.anchored_edits import apply_anchored_edits, parse_anchored_edits
from squadops.capabilities.scaffold import expand
from squadops.cycles.structural_resolution import syntax_error
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_ROUTE = "app/api/runs/route.ts"
_PAGE = "app/page.tsx"


@pytest.fixture(scope="module")
def scaffold():
    return {f["name"]: f["content"] for f in expand(manifest_for_stack("nextjs_ts"))}


def _apply(scaffold, path, block):
    return apply_anchored_edits(
        parse_anchored_edits(f"```edit:{path}\n{block}```\n"),
        {path: scaffold[path]},
        writable=[path],
        producer="development.correction_repair",
        task_id="t",
    )


def test_a_handlers_try_block_revision_leaves_the_envelope_and_its_siblings_untouched(scaffold):
    """Bug caught: the fill reaching past the ``try`` block — the signature, the ``catch``
    returning ``errorResponse``, or the sibling ``GET`` handler changed by a ``POST`` fill."""
    seed = scaffold[_ROUTE]
    fill = (
        "    const body = await request.json()\n"
        "    return Response.json(store.insert('runs', body), { status: 201 })\n"
    )

    application = _apply(
        scaffold, _ROUTE, f"<<<<<<< REPLACE function:POST#try\n{fill}>>>>>>> END\n"
    )

    assert application.accepted, application.refusal_lines()
    candidate = application.outcome.changed_files()[_ROUTE]
    assert application.outcome.preservation.holds
    assert syntax_error(_ROUTE, candidate) is None
    post = candidate[candidate.index("export async function POST") :]
    assert post.startswith(
        "export async function POST(request: Request) {\n  try {\n"
        + fill
        + "  } catch (err) {\n    return errorResponse(err)\n  }\n}\n"
    )
    get_seed = seed[
        seed.index("export async function GET") : seed.index("export async function POST")
    ]
    assert get_seed in candidate


def test_a_page_component_body_revision_parses_as_tsx(scaffold):
    body = '  return <main data-testid="runs-list">{runs?.length ?? 0}</main>\n'

    application = _apply(
        scaffold, _PAGE, f"<<<<<<< REPLACE function:RunsListView#body\n{body}>>>>>>> END\n"
    )

    assert application.accepted, application.refusal_lines()
    candidate = application.outcome.changed_files()[_PAGE]
    assert syntax_error(_PAGE, candidate) is None
    assert application.outcome.preservation.holds


def test_a_fill_that_breaks_the_typescript_is_refused_before_verification(scaffold):
    """§18 on the second stack's grammar. Bug caught: a TS candidate with an unclosed brace
    accepted because the syntax check only knew Python and JavaScript."""
    application = _apply(
        scaffold,
        _ROUTE,
        "<<<<<<< REPLACE function:POST#try\n    return Response.json({ id: 1 )\n>>>>>>> END\n",
    )

    assert not application.accepted
    assert any("invalid_syntax" in line for line in application.refusal_lines())
