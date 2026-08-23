"""The truncation scanner (#1082).

Two obligations, and the second is the harder one: catch an emission that stopped
mid-construct, and never flag one that did not. The corpus sweep that gated this
shipping — 4,513 banked source artifacts, 8 flags, all 8 genuine truncations — is
the real acceptance evidence; these tests pin the shapes that sweep exercised so
a later change cannot quietly reintroduce a false positive.
"""

from __future__ import annotations

import pytest

from squadops.cycles.source_termination import check_termination

pytestmark = [pytest.mark.domain_contracts]


# The literal tail of cyc_87c12c7f199e's leave/route.ts, the motivating defect.
REAL_TRUNCATION = """\
import { NextRequest, NextResponse } from 'next/server';
import { ApiError, errorResponse } from '@/lib/errors';
import { find, insert, TABLES } from '@/lib/store';

export async function POST(
  request: NextRequest,
  { params }: { params: { run_id: string } }
) {
  try {
    const body = await request.json();
    const name: string = body.name;

    if (!name || !String(name).trim()) {
      throw new
"""


class TestCatchesTruncation:
    def test_the_motivating_defect(self):
        """407 bytes ending on `throw new`, three braces open. esbuild called it
        'Unexpected end of file'; the run called it a qa failure across two test
        files, one of which only imported the module."""
        result = check_termination(REAL_TRUNCATION, ".ts")
        assert not result.terminated
        assert result.line == 8  # the function body's brace, the outermost one open

    @pytest.mark.parametrize(
        "source,ext",
        [
            ("describe('x', () => {\n  it('y', async () => {\n    expect(res.status", ".ts"),
            ("const cfg = {\n  body: JSON.stringify({\n    title: 'Run B',", ".ts"),
            ("export function f(a: number) {\n  return [1, 2,", ".tsx"),
            ("def handler(req):\n    return {'a': 1,", ".py"),
            ("def handler(req):\n    if req:", ".py"),
        ],
        ids=["mid-expression", "nested-object", "open-array", "py-open-dict", "py-open-block"],
    )
    def test_shapes_the_corpus_produced(self, source, ext):
        assert not check_termination(source, ext).terminated

    def test_unterminated_template_literal(self):
        source = "const q = `SELECT * FROM ${table} WHERE id ="
        assert not check_termination(source, ".ts").terminated


class TestNeverFlagsHealthySource:
    @pytest.mark.parametrize(
        "source,ext",
        [
            # A regex holding an unbalanced brace — the classic scanner trap.
            ("const re = /[{]/;\nexport const ok = true;\n", ".ts"),
            ("const re = /}/g;\nexport const ok = true;\n", ".ts"),
            # Braces living inside strings and comments.
            ("const s = '{';\nconst t = \"}\";\n// { unclosed in a comment\n", ".ts"),
            ("/* { */\nexport const x = 1;\n", ".ts"),
            # Template literals, including nested interpolation.
            ("const a = `x${ y }z`;\nconst b = `${ `${inner}` }`;\n", ".ts"),
            # JSX, which is where `{` density is highest.
            (
                "export default function P() {\n"
                "  return <div className={cx('a')}>{items.map((i) => (\n"
                "    <span key={i.id}>{i.name}</span>\n"
                "  ))}</div>;\n}\n",
                ".tsx",
            ),
            # Division, which must not be read as a regex opener.
            ("const ratio = total / count / 2;\nexport const r = ratio;\n", ".ts"),
            # Escaped quotes.
            ("const s = 'it\\'s {';\nexport const t = s;\n", ".js"),
            # Python: f-strings, decorators, nested comprehensions.
            ("x = f'{a}{b}'\ny = [i for i in range(3) if i % 2]\n", ".py"),
        ],
        ids=[
            "regex-with-brace",
            "regex-with-close-brace",
            "braces-in-strings",
            "brace-in-block-comment",
            "nested-template",
            "jsx",
            "division-not-regex",
            "escaped-quote",
            "python-fstring",
        ],
    )
    def test_well_formed_source_is_never_flagged(self, source, ext):
        result = check_termination(source, ext)
        assert result.terminated, f"false positive: {result.reason}"

    @pytest.mark.parametrize(
        "source",
        [
            "substantial content here" * 10,  # one line, invalid, NOT truncated
            "this is not python at all\n",
            "def f(:\n    pass\n",
        ],
        ids=["single-line-prose", "prose", "bad-signature"],
    )
    def test_a_syntax_error_alone_is_never_a_truncation_claim(self, source):
        """Position alone was not enough, and an earlier draft got this wrong.

        Every single-line file with any syntax error has its error on the last
        line trivially, so a positional rule flagged all of them — caught by the
        existing output-validation suite, whose fixtures use prose as file
        content. The message must independently say something was left open.
        """
        assert check_termination(source, ".py").terminated

    def test_a_plain_syntax_error_is_not_a_truncation_claim(self):
        """The claim is 'ends mid-construct', not 'is valid'.

        This file is invalid Python and closes everything it opens. Reporting it
        would make this the general syntax gate, which it cannot be on the brace
        languages — and one defect would show up as two.
        """
        assert check_termination("def f(:\n    pass\n", ".py").terminated

    @pytest.mark.parametrize(
        "source",
        [
            # cyc_b7cf604aed46: `/>` read as a regex opener swallowed text to the
            # next `/`, which sat inside `path="/"`, unbalancing the whole file.
            'const x = <Route path="/" element={<div>Runs</div>} />;\n',
            # `</div>` — the closing-tag slash, same failure.
            "const x = <div>text</div>;\n",
        ],
        ids=["self-closing-tag", "closing-tag"],
    )
    def test_jsx_punctuation_is_not_a_regex_opener(self, source):
        assert check_termination(source, ".tsx").terminated

    def test_jsx_text_may_carry_an_unmatched_bracket(self):
        """cyc_02e9af402c82's shape, and the reason `(` is untracked in JSX.

        The literal "(" is element TEXT and its ")" lives in a sibling `{')'}`
        expression. Nothing makes those balance, so counting them at all produces
        a false positive on a complete, correct file.
        """
        source = (
            "export default function P() {\n"
            "  return (\n"
            "    <h2>\n"
            "      Participants ({' '}\n"
            "      <span>{n}</span>\n"
            "      {')'}\n"
            "    </h2>\n"
            "  );\n"
            "}\n"
        )
        assert check_termination(source, ".tsx").terminated

    def test_an_unmatched_closer_is_not_reported(self):
        """One-sided by design: extra closers are a syntax error, never a cut-off."""
        assert check_termination("export const x = 1;\n}\n", ".ts").terminated


class TestScope:
    def test_parens_are_tracked_outside_jsx_and_not_within(self):
        """The tradeoff, stated as a test so it cannot drift silently.

        Four of the corpus's eight truncations are `.ts` test files cut mid-call,
        which only an unclosed `(` reveals. JSX files give that up — element text
        may hold an unmatched bracket — and keep `{`, which is JSX's own
        expression delimiter and always balances.
        """
        # A cut with NO unclosed brace — only the open paren reveals it.
        cut = "const created = await createRun(\n  'Morning Loop',\n  '2026-09-02',"
        assert not check_termination(cut, ".ts").terminated
        assert check_termination(cut, ".tsx").terminated

    @pytest.mark.parametrize("ext", [".md", ".json", ".yaml", ".txt", ""])
    def test_unscannable_extensions_resolve_to_terminated(self, ext):
        """Prose is deliberately out of scope.

        The census's second instance is a qa_handoff.md that stopped mid-paragraph,
        and it stays uncaught: markdown has no delimiter invariant, and
        'ends mid-sentence' false-positives on documents that legitimately end in
        a list item or a fenced block. Silence beats a guess here.
        """
        assert check_termination("a paragraph that just stops mid", ext).terminated

    def test_empty_source_is_terminated(self):
        assert check_termination("", ".ts").terminated
