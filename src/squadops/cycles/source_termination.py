"""Did this source file stop in the middle of something? (#1082)

A completion that runs out of budget mid-file is stored as if it were whole. The
bytes look like code, so nothing questions them until something downstream tries
to parse them — and by then the failure has been re-attributed to the consumer.
`cyc_87c12c7f199e` shipped a 407-byte route ending on ``throw new`` with three
unclosed braces; it surfaced as ``tests_pass`` failing two whole test files, one
of which merely imported the module.

**This module answers one narrow question and refuses the broader one.** It does
not ask whether the source is valid — only whether it *ends inside an unclosed
construct*, which is the specific shape truncation takes. A file with a genuine
syntax error that nonetheless closes everything it opened is somebody else's
problem; conflating the two would make this check the general syntax gate it is
not equipped to be, on languages it cannot parse.

**Zero false positives is the bar, and it is higher than catching truncations.**
A guard that rejects a healthy emission manufactures the defect it exists to
prevent — the `classify_fences` lesson (``handlers/emission_log.py``), where an
instrument reported correctly-addressed fences as bare and the wrong diagnosis
was written down before the vault contradicted it. Every rule here is therefore
one-sided: an unmatched *closer* is never reported (that is a syntax error, not a
truncation), and anything the scanner cannot confidently interpret resolves to
"terminated".
"""

from __future__ import annotations

from dataclasses import dataclass

#: Extensions this module can scan. Python is handled by the interpreter's own
#: parser; the brace languages share one scanner.
PYTHON_EXTENSIONS = frozenset({".py"})
BRACE_EXTENSIONS = frozenset({".ts", ".tsx", ".js", ".jsx"})
SCANNABLE_EXTENSIONS = PYTHON_EXTENSIONS | BRACE_EXTENSIONS

_OPENERS = {"{": "}", "(": ")", "[": "]"}
_CLOSERS = {v: k for k, v in _OPENERS.items()}

#: In JSX, only ``{`` is a delimiter. Element TEXT is prose and may carry an
#: unmatched bracket — ``Participants ({' '}`` renders a literal "(" whose ")"
#: lives in a sibling ``{')'}`` expression, and no amount of counting makes those
#: balance. ``{`` stays safe because it is JSX's own expression delimiter and is
#: always matched. Scoped by extension rather than by sniffing for JSX, because
#: the language already draws this line: JSX is only legal in these files.
_JSX_EXTENSIONS = frozenset({".tsx", ".jsx"})

#: A ``/`` directly after one of these begins a regex literal, not a division.
#: The distinction matters because a regex may legally contain unbalanced
#: brackets (``/[{]/``) and counting those would be a false positive. Erring
#: toward "regex" is the safe direction: a mis-read regex swallows text up to the
#: next ``/`` and can only ever make the scanner report FEWER unclosed openers.
_REGEX_PRECEDERS = set("(,=:[!&|?{};+-*%^~<>") | {""}


@dataclass(frozen=True)
class Termination:
    """Whether a file ends cleanly, and what was left open if not."""

    terminated: bool
    #: Human-readable reason, empty when terminated.
    reason: str = ""
    #: The unclosed opener's 1-based line, when there is one.
    line: int | None = None


TERMINATED = Termination(terminated=True)


def _consume_trivia(source: str, i: int, prev_significant: str) -> tuple[int, int, str] | None:
    """Skip a comment or regex literal starting at ``i``.

    Returns ``(next_index, newlines, error)`` — ``error`` non-empty only for an
    unterminated block comment. ``None`` when ``i`` does not start trivia.
    """
    if source[i] != "/" or i + 1 >= len(source):
        return None
    nxt = source[i + 1]
    if nxt == "/":
        end = source.find("\n", i)
        return (len(source) if end == -1 else end, 0, "")
    if nxt == "*":
        end = source.find("*/", i + 2)
        if end == -1:
            return (len(source), 0, "unterminated block comment")
        return (end + 2, source.count("\n", i, end), "")
    # JSX punctuation, not regex. `<Route ... />` and `</div>` are far more
    # common in this corpus than a regex literal, and misreading one swallows
    # everything up to the next `/` — which in `path="/"` is inside a string,
    # unbalancing the rest of the file. Two false positives on complete JSX
    # (cyc_b7cf604aed46, cyc_02e9af402c82) came from exactly this.
    if nxt == ">" or prev_significant == "<":
        return None
    if prev_significant in _REGEX_PRECEDERS:
        consumed, _ = _skip_regex(source, i)
        # An unterminated regex is indistinguishable from a division the
        # heuristic misread, so treat it as ordinary text rather than guess.
        if consumed is not None:
            return (consumed, 0, "")
    return None


def _scan_braces(source: str, tracked: str = "{([") -> Termination:
    """Walk a brace-language source tracking comments, strings and nesting.

    Deliberately not a tokenizer. It knows just enough to avoid counting
    delimiters that live inside comments, strings, template literals or regex
    literals — the four places where a brace does not mean nesting.

    ``tracked`` narrows which openers count; JSX files pass ``"{"`` alone.
    """
    stack: list[tuple[str, int]] = []
    i, line, n = 0, 1, len(source)
    prev_significant = ""

    while i < n:
        ch = source[i]

        if ch == "\n":
            line, i = line + 1, i + 1
            continue

        # Comments, regex and string/template literals are all "text that is not
        # code": one branch for the whole category keeps the loop about nesting.
        skippable = _consume_trivia(source, i, prev_significant) or _consume_literal(
            source, i, ch, stack, line
        )
        if skippable is not None:
            i, newlines, error = skippable
            if error:
                return Termination(False, error, line)
            line, prev_significant = line + newlines, ch
            continue

        if ch in _OPENERS and ch in tracked:
            stack.append((ch, line))
        elif ch in _CLOSERS and _CLOSERS[ch] in tracked:
            closed = _close(source, i, ch, stack, line)
            if closed is None:
                return Termination(False, "unterminated template literal", line)
            resumed, newlines = closed
            if resumed is not None:
                line, i = line + newlines, resumed
                continue

        if not ch.isspace():
            prev_significant = ch
        i += 1

    if stack:
        opener, opened_at = stack[0]
        what = "template literal" if opener == "`" else f"{opener!r}"
        return Termination(False, f"unclosed {what} opened at line {opened_at}", opened_at)
    return TERMINATED


def _consume_literal(
    source: str, i: int, ch: str, stack: list[tuple[str, int]], line: int
) -> tuple[int, int, str] | None:
    """Skip a quoted string or template literal starting at ``i``.

    Returns ``(next_index, newlines, error)``, or ``None`` when ``ch`` does not
    open a literal. Both literal kinds are handled here so the main loop keeps
    one branch for "text that is not code" rather than one per quote character.
    """
    if ch in "'\"":
        end, newlines = _skip_quoted(source, i, ch)
        if end is None:
            return (len(source), newlines, f"unterminated {ch!r} string")
        return (end, newlines, "")
    if ch == "`":
        outcome = _enter_template(source, i, stack, line)
        if outcome is None:
            return (len(source), 0, "unterminated template literal")
        end, newlines = outcome
        return (end, newlines, "")
    return None


def _enter_template(
    source: str, i: int, stack: list[tuple[str, int]], line: int
) -> tuple[int, int] | None:
    """Scan from an opening backtick, pushing a marker if it hits ``${``."""
    result = _resume_template(source, i + 1)
    if result is None:
        return None
    end, newlines, interpolated = result
    if interpolated:
        # The interpolation body is ordinary code and may open braces of its
        # own, so it goes back through the main loop behind a `\`` marker.
        stack.append(("`", line))
    return end, newlines


def _close(
    source: str, i: int, ch: str, stack: list[tuple[str, int]], line: int
) -> tuple[int | None, int] | None:
    """Handle a closing delimiter. ``(None, 0)`` when the caller should advance
    normally, ``(index, newlines)`` when template scanning resumed, ``None`` on
    an unterminated template."""
    if stack and stack[-1][0] == _CLOSERS[ch]:
        stack.pop()
        return None, 0
    if stack and stack[-1][0] == "`" and ch == "}":
        stack.pop()  # closing `${...}` returns to template context
        result = _resume_template(source, i + 1)
        if result is None:
            return None
        end, newlines, interpolated = result
        if interpolated:
            stack.append(("`", line))
        return end, newlines
    # An unmatched closer is a syntax error, not a truncation. One-sided by
    # design: this module never reports it.
    return None, 0


def _skip_quoted(source: str, start: int, quote: str) -> tuple[int | None, int]:
    """Index just past a single- or double-quoted string, and newlines crossed."""
    i, newlines, n = start + 1, 0, len(source)
    while i < n:
        ch = source[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return i + 1, newlines
        if ch == "\n":
            # An unescaped newline ends these strings in JS/TS. Treat it as the
            # string ending rather than as truncation: a multi-line quoted string
            # is a syntax error, and syntax errors are not this module's claim.
            return i, newlines
        i += 1
    return None, newlines


def _skip_regex(source: str, start: int) -> tuple[int | None, int]:
    """Index just past a regex literal's closing ``/``, and newlines crossed."""
    i, n = start + 1, len(source)
    in_class = False
    while i < n:
        ch = source[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "\n":
            return None, 0
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        elif ch == "/" and not in_class:
            i += 1
            while i < n and source[i].isalpha():  # flags
                i += 1
            return i, 0
        i += 1
    return None, 0


def _resume_template(source: str, start: int) -> tuple[int, int, bool] | None:
    """Scan template text until its closing backtick or an interpolation.

    Returns ``(index, newlines, interpolated)`` — ``interpolated`` True when the
    scan stopped at a ``${``, whose body the caller feeds back to the main loop.
    """
    i, newlines, n = start, 0, len(source)
    while i < n:
        ch = source[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "\n":
            newlines += 1
        elif ch == "`":
            return i + 1, newlines, False
        elif ch == "$" and i + 1 < n and source[i + 1] == "{":
            return i + 2, newlines, True
        i += 1
    return None


def _scan_python(source: str) -> Termination:
    """Ask CPython, and report only the EOF-shaped failures.

    ``compile`` is exact where the brace scanner is heuristic, so Python gets the
    real answer. The filter is what keeps the claim narrow: a ``SyntaxError``
    that is not about running out of input is an ordinary syntax defect, and
    reporting it here would quietly turn this into the general syntax gate.
    """
    try:
        compile(source, "<emission>", "exec")
    except SyntaxError as exc:
        message = str(exc.msg or "")
        lowered = message.lower()
        if "unexpected eof" in lowered or "was never closed" in lowered:
            return Termination(False, message, exc.lineno)
        # Not every truncation says EOF. A file ending on ``if req:`` reports
        # "expected an indented block" — an unclosed construct by any reading —
        # but the same message appears mid-file for an ordinary indentation bug,
        # so position decides: at the last code line the file ran out, above it
        # the source is complete and merely wrong.
        #
        # Position ALONE is not enough, and an earlier draft that used it alone
        # was wrong: it flagged every single-line file with any syntax error,
        # since line 1 is trivially the last line. The message must independently
        # say something was left open.
        if "expected an indented block" in lowered and _at_end(exc.lineno, source):
            return Termination(False, message, exc.lineno)
        return TERMINATED
    except ValueError:
        # Source with NUL bytes and similar; not a truncation claim.
        return TERMINATED
    return TERMINATED


def _at_end(lineno: int | None, source: str) -> bool:
    """Is ``lineno`` the last line of ``source`` that carries anything?"""
    if lineno is None:
        return False
    lines = source.splitlines()
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].strip():
            return lineno >= idx + 1
    return False


def check_termination(source: str, extension: str) -> Termination:
    """Does ``source`` end inside an unclosed construct?

    Unscannable extensions resolve to terminated — silence, not a guess. Prose in
    particular is out of scope: markdown has no delimiter invariant, and
    "ends mid-sentence" is a heuristic with real false positives on documents
    that legitimately end in a list item or a fenced block.
    """
    ext = extension.lower()
    if ext in PYTHON_EXTENSIONS:
        return _scan_python(source)
    if ext in BRACE_EXTENSIONS:
        return _scan_braces(source, "{" if ext in _JSX_EXTENSIONS else "{([")
    return TERMINATED
