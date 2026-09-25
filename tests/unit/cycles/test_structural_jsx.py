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
    names two; a statement sharing its line owns no lines; a one-line body has none; and a file
    no grammar here reads is not read."""
    broken = "export default function A() {\n  return <div>\n}\n"
    assert jsx_entities(broken) is None
    assert resolve_jsx_entity(_VIEW, broken, "function:A") is None

    redeclared = "function f() {\n  return 1\n}\n\nfunction f() {\n  return 2\n}\n"
    assert len(resolve_jsx_entity(_VIEW, redeclared, "function:f")) == 2

    shared = "const a = 1; const b = 2\nfunction g() { return 1 }\n"
    assert resolve_jsx_entity(_VIEW, shared, "const:a") == []
    assert resolve_jsx_entity(_VIEW, shared, "function:g#body") == []
    assert resolve_jsx_entity(_VIEW, shared, "function:g") == [(25, len(shared))]

    assert resolve_jsx_entity("app/styles.css", _SOURCE, "function:RunsListView") is None


@pytest.mark.parametrize(
    ("path", "source", "expected"),
    [
        (_VIEW, _SOURCE, None),
        (_VIEW, "export default function A() {\n  return <div>\n}\n", "line "),
        ("frontend/src/api.js", "export const x = (\n", "line "),
        ("app/page.tsx", "export default function P() {\n  return <div>\n}\n", "line "),
        ("lib/store.ts", "export function f(x: number {\n", "line "),
        ("README.md", "not javascript at all (", None),
    ],
    ids=["clean", "unclosed JSX", "unclosed paren", "broken TSX", "broken TS", "no grammar"],
)
def test_the_syntax_check_refuses_only_what_the_grammar_reads_and_rejects(path, source, expected):
    """§18. Bug caught: an error-tolerant tree accepted as valid, so a candidate with a broken
    tag or a broken type reaches verification — or a file refused by a grammar it is not."""
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


# --- SIP-0107 step 6: TypeScript, TSX and the Next.js stack ----------------------------------

_STORE_TS = (
    "'use strict'\n"
    "import { randomUUID } from 'crypto'\n"
    "\n"
    "export interface Run {\n"
    "  id: string\n"
    "}\n"
    "export type Table = 'runs'\n"
    "export enum Status {\n"
    "  Open,\n"
    "}\n"
    "\n"
    "export async function POST(request: Request): Promise<Response> {\n"
    "  try {\n"
    "    return Response.json({ id: randomUUID() })\n"
    "  } catch (err) {\n"
    "    return errorResponse(err)\n"
    "  }\n"
    "}\n"
    "\n"
    "export function find(id: string): Run | undefined {\n"
    "  const run = undefined\n"
    "  try {\n"
    "    return run\n"
    "  } finally {\n"
    "    void id\n"
    "  }\n"
    "}\n"
)


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ("imports", "import { randomUUID } from 'crypto'\n"),
        ("interface:Run", "export interface Run {\n  id: string\n}\n"),
        ("type:Table", "export type Table = 'runs'\n"),
        ("enum:Status", "export enum Status {\n  Open,\n}\n"),
        ("function:POST#try", "    return Response.json({ id: randomUUID() })\n"),
    ],
)
def test_typescript_names_its_own_declarations_and_a_handlers_try_block(selector, expected):
    """Bug caught: a directive prologue hiding the import section, a TypeScript declaration kind
    unaddressable, or a handler's fill range taking the scaffold-owned ``catch`` envelope."""
    assert _text(selector, _STORE_TS, "lib/store.ts") == expected


def test_try_is_addressable_only_when_the_body_is_one_try_statement():
    """Bug caught: ``#try`` offered for a body with more than the try — replacing it would
    silently leave the statements before it in place under the model's belief it had the body."""
    assert resolve_jsx_entity("lib/store.ts", _STORE_TS, "function:find#try") == []
    assert resolve_jsx_entity("lib/store.ts", _STORE_TS, "function:find#body")


class TestACorruptParseTreeIsNotReadFurther:
    """#1626: `tree_sitter_typescript` returned an `expression_statement` whose
    `start_point.row` was 69,421,703,888,908 in a 396-row file, and the qa agent SEGFAULTED
    dereferencing the tree around it — 37 restarts on one redelivered message, no record,
    and no termination (every rule assumes the handler returns).

    The real input does not reproduce outside the agent container on identical versions and
    architecture, which is itself evidence of memory-state-dependent corruption rather than
    a deterministic parse bug. So the guard is pinned on synthetic nodes: what must hold is
    that a row outside the content is never read, whatever produced it."""

    #: the value the binding actually returned, kept verbatim
    CORRUPT_ROW = 69421703888908

    @staticmethod
    def _node(start, end):
        class _P:
            def __init__(self, row, column):
                self.row, self.column = row, column

            def __iter__(self):
                return iter((self.row, self.column))

        class _N:
            start_point = _P(*start)
            end_point = _P(*end)

        return _N()

    def _lines(self):
        from squadops.cycles.structural_jsx import _Lines

        return _Lines("const a = 1\nconst b = 2\n")

    def test_the_row_the_binding_actually_returned_raises_rather_than_being_read(self):
        from squadops.cycles.structural_jsx import _CorruptParse

        lines = self._lines()
        with pytest.raises(_CorruptParse) as exc:
            lines.owns(self._node((self.CORRUPT_ROW, 0), (395, 2)))
        assert str(self.CORRUPT_ROW) in str(exc.value)

    def test_a_negative_row_raises_instead_of_silently_reading_the_wrong_line(self):
        """Python would index a negative row from the END and return a plausible answer
        about a line the node has nothing to do with — a wrong entity list, not a crash."""
        from squadops.cycles.structural_jsx import _CorruptParse

        with pytest.raises(_CorruptParse):
            self._lines().owns(self._node((-1, 0), (0, 2)))

    @pytest.mark.parametrize(
        ("first_row", "last_row", "why"),
        [
            (CORRUPT_ROW, 395, "oversized first row — the value the binding returned"),
            (0, CORRUPT_ROW, "oversized LAST row — fell through to a span to end-of-file"),
            (-1, 1, "negative first row"),
            (0, -1, "negative last row"),
            (1, 0, "reversed endpoints"),
        ],
    )
    def test_span_enforces_the_whole_invariant(self, first_row, last_row, why):
        """`0 <= first_row <= last_row < row_count`, not half of it.

        The first cut checked the first row and rejected a negative last row, but let an
        OVERSIZED last row through: the end-offset fallback then returned a span to
        end-of-file — a plausible answer derived from a corrupt tree, which is the exact
        failure this guard exists to refuse."""
        from squadops.cycles.structural_jsx import _CorruptParse

        with pytest.raises(_CorruptParse):
            self._lines().span(first_row, last_row)

    def test_span_still_answers_for_sound_rows(self):
        """The control: tightening the invariant must not refuse a legitimate span,
        including one that ends on the final row."""
        lines = self._lines()
        assert lines.span(0, 0)[0] == 0
        start, end = lines.span(0, len(lines.starts) - 1)
        assert start == 0 and end == len(lines.content)

    def test_jsx_entities_returns_None_rather_than_propagating(self, monkeypatch):
        """The contract callers already handle: `None` means the content does not parse
        cleanly. A corrupt tree is not a clean parse. Tested on the reading the parse worker
        runs (#1626 containment), since a patch in this process never reaches the worker."""
        import squadops.cycles.structural_jsx as m

        def _boom(content, path):
            raise m._CorruptParse("node row 69421703888908 is outside the 396-row content")

        monkeypatch.setattr(m, "_jsx_entities", _boom)
        assert m._jsx_entities_here("const a = 1\n", "x.ts") is None

    def test_a_sound_tree_still_yields_its_entities(self):
        """The control: the guard must not cost ordinary content its entities."""
        from squadops.cycles.structural_jsx import jsx_entities

        entities = jsx_entities("export function a() {\n  return 1\n}\n", "x.ts")
        assert entities, "a sound parse must still produce entities"
        assert any("a" in e.selector for e in entities)


def _die_like_1626() -> None:
    """What the qa agent did on deploy A (#1626): a native fault, no traceback."""
    import os
    import signal

    os.kill(os.getpid(), signal.SIGSEGV)


def _never_answer() -> None:
    import time

    time.sleep(3600)


class TestANativeFaultKillsTheWorkerNotTheAgent:
    """#1626 (1.8.2 item 3): tree-sitter is native code, and on one repair input it segfaulted
    the qa agent itself — no traceback, no result, a run left `running`. The parse now runs in
    a worker process: a fault there is a structural miss the repair path already handles."""

    def test_a_segfault_in_the_worker_answers_and_the_next_parse_gets_a_fresh_one(self):
        """Entered at the worker seam every structural read goes through, with the worker
        really killed by SIGSEGV. Bug this catches: the fault reaching the caller (the agent
        dies), or a dead worker left in place so every later parse fails too."""
        import squadops.cycles.structural_jsx as m

        assert m._in_worker(_die_like_1626) == (False, None)
        entities = m.jsx_entities("export function a() {\n  return 1\n}\n", "x.ts")
        assert entities and entities[0].selector == "function:a"

    def test_a_hung_worker_is_bounded_and_replaced(self, monkeypatch):
        import squadops.cycles.structural_jsx as m

        monkeypatch.setattr(m, "PARSE_TIMEOUT_SECONDS", 1.0)
        assert m._in_worker(_never_answer) == (False, None)
        assert m.jsx_syntax_error("a.ts", "const a = 1\n") is None

    @pytest.mark.parametrize(
        ("read", "expected"),
        [
            (lambda m: m.jsx_entities("const a = 1\n", "x.ts"), None),
            (lambda m: m.jsx_syntax_error("x.ts", "const a = 1\n"), "PARSER_DIED"),
        ],
    )
    def test_a_parse_the_worker_did_not_finish_fails_closed(self, monkeypatch, read, expected):
        """Bug this catches: a dead parse read as "parses" (the syntax check answering None
        lets unparseable content through) or as an empty entity list (a real answer)."""
        import squadops.cycles.structural_jsx as m

        monkeypatch.setattr(m, "_in_worker", lambda fn, *a: (False, None))
        assert read(m) == (m.PARSER_DIED if expected == "PARSER_DIED" else expected)
