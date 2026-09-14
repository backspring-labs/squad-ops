"""SIP-0107 §38 step 5 — structural addressing for JavaScript and JSX, on tree-sitter.

Each test names what it catches: an entity range that drops ``export`` or splits a line, a
tolerant parse addressed as if it were clean, a redeclaration picked between, or a byte offset
used where a character offset belongs.
"""

from __future__ import annotations

import pytest

from squadops.cycles.structural_jsx import (
    jsx_entities,
    jsx_syntax_error,
    resolve_jsx_entity,
)

pytestmark = [pytest.mark.domain_orchestration]

_VIEW = "frontend/src/views/RunsListView.jsx"
_SOURCE = (
    "import { useEffect, useState } from 'react'\n"
    "import { apiFetch } from '../api.js'\n"
    "\n"
    "const API_BASE = '/api'\n"
    "\n"
    "const formatCount = (run) => {\n"
    "  return run?.participants?.length ?? 0\n"
    "}\n"
    "\n"
    "export default function RunsListView() {\n"
    "  const [runs, setRuns] = useState([])\n"
    "  useEffect(() => { apiFetch('/runs').then(setRuns) }, [])\n"
    '  return <ul data-testid="runs-list">{runs.map((r) => <li key={r.id}>{r.title}</li>)}</ul>\n'
    "}\n"
)


def _text(selector: str, source: str = _SOURCE, path: str = _VIEW) -> str:
    (span,) = resolve_jsx_entity(path, source, selector)
    return source[span[0] : span[1]]


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        (
            "imports",
            "import { useEffect, useState } from 'react'\nimport { apiFetch } from '../api.js'\n",
        ),
        ("import:../api.js", "import { apiFetch } from '../api.js'\n"),
        ("const:API_BASE", "const API_BASE = '/api'\n"),
        (
            "const:formatCount",
            "const formatCount = (run) => {\n  return run?.participants?.length ?? 0\n}\n",
        ),
        ("const:formatCount#body", "  return run?.participants?.length ?? 0\n"),
        ("function:RunsListView", _SOURCE[_SOURCE.index("export default") :]),
        (
            "function:RunsListView#body",
            _SOURCE[_SOURCE.index("  const [runs") : _SOURCE.rindex("}\n")],
        ),
    ],
)
def test_a_selector_names_the_whole_lines_of_its_entity_in_modern_jsx(selector, expected):
    """Bug caught: ``export default`` left outside the function's range, a body range that takes
    a brace line, or modern syntax (``?.``, ``??``, JSX) read as a parse failure."""
    assert _text(selector) == expected


def test_offsets_are_characters_where_a_line_holds_multibyte_text():
    """Bug caught: tree-sitter's byte columns used as string offsets — every range after a
    non-ASCII character would be shifted and a replacement would splice into the wrong bytes."""
    source = "// Läufe — alle Einträge\n" + _SOURCE

    assert _text("const:formatCount#body", source) == "  return run?.participants?.length ?? 0\n"


def test_what_cannot_be_cleanly_addressed_resolves_to_nothing():
    """Fail-closed (§43.2): a tolerant parse of broken JSX is not addressed; a redeclaration
    names two; a statement sharing its line owns no lines; a one-line body has none; and the
    TypeScript files step 6 owns are not read by this grammar."""
    broken = "export default function A() {\n  return <div>\n}\n"
    assert jsx_entities(broken) is None
    assert resolve_jsx_entity(_VIEW, broken, "function:A") is None

    redeclared = "function f() {\n  return 1\n}\n\nfunction f() {\n  return 2\n}\n"
    assert len(resolve_jsx_entity(_VIEW, redeclared, "function:f")) == 2

    shared = "const a = 1; const b = 2\nfunction g() { return 1 }\n"
    assert resolve_jsx_entity(_VIEW, shared, "const:a") == []
    assert resolve_jsx_entity(_VIEW, shared, "function:g#body") == []
    assert resolve_jsx_entity(_VIEW, shared, "function:g") == [(25, len(shared))]

    assert resolve_jsx_entity("app/page.tsx", _SOURCE, "function:RunsListView") is None


@pytest.mark.parametrize(
    ("path", "source", "expected"),
    [
        (_VIEW, _SOURCE, None),
        (_VIEW, "export default function A() {\n  return <div>\n}\n", "line "),
        ("frontend/src/api.js", "export const x = (\n", "line "),
        ("app/page.tsx", "not javascript at all (", None),
    ],
    ids=["clean", "unclosed JSX", "unclosed paren", "a grammar this is not"],
)
def test_the_syntax_check_refuses_only_what_the_grammar_reads_and_rejects(path, source, expected):
    """§18. Bug caught: an error-tolerant tree accepted as valid, so a candidate with a broken
    tag reaches verification — or a TypeScript file refused by the wrong grammar."""
    error = jsx_syntax_error(path, source)

    if expected is None:
        assert error is None
    else:
        assert error is not None and error.startswith(expected)


def test_the_real_react_view_scaffold_addresses_its_component_and_body():
    """On the FastAPI+React scaffold's ``RunsListView.jsx`` — the file 1.7.5 React roll 3
    re-emitted whole on every round (§1.2)."""
    from squadops.capabilities.scaffold import expand
    from tests.unit.capabilities._stack_fixtures import manifest_for_stack

    files = {f["name"]: f["content"] for f in expand(manifest_for_stack("fullstack_fastapi_react"))}
    view = files[_VIEW]

    assert jsx_syntax_error(_VIEW, view) is None
    assert _text("function:RunsListView", view).startswith("export default function RunsListView")
    assert 'data-testid="runs-list"' in _text("function:RunsListView#body", view)
