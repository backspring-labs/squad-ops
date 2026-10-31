"""Stack #2's slot-assertion reader: what a vitest fill asserts on (SIP-0104 §13f, #2664).

The slot-subject gate compares the subject of a failing slot assertion with what a revision
of that slot still asserts. The gate is stack-neutral; reading an assertion is not, so each
stack that emits shells registers a reader beside its emitter
(``verification_scaffold_emission.slot_assertion_reader``). This is the TypeScript one, for
the vitest shells ``stack_nextjs_ts_tests`` emits.

**What it reads** (the MacBook lane's G4, point 1). Each ``expect(<target>).<matcher>(…)`` in
a slot body, with ``<target>`` mapped to a surface and a field:

- ``body.<f>`` is field ``f`` of the response; ``body`` alone is the response as a whole;
- ``body.error.<f>`` is field ``f`` of the frozen error envelope; ``body.error`` the envelope;
- ``all(TABLES.<T>)[i].<f>`` is field ``f`` of store table ``T``; ``all(TABLES.<T>)``,
  ``all(TABLES.<T>).length``, ``all(TABLES.<T>)[i]`` and ``TABLES.<T>`` are the table whole.

Anything else has no subject (``None``). The gate records that as ``subject_unreadable`` and
never refuses on it, because it refuses only what it can show.

**What it normalises first**, so a rewrite in a different spelling reads as the same subject
and is not refused as a drop:

- optional chaining and non-null assertions (``body?.x``, ``row!.x``), ``as`` casts, quoted
  bracket access (``body['x']``), redundant parentheses and whitespace;
- ``typeof <t>`` and ``Array.isArray(<t>)``, read as a *shape* check of ``<t>``;
- the slot body's own aliases: ``const rows = all(TABLES.Run)`` makes ``rows[0].title`` the
  store's ``title``; ``const { a } = body`` and ``for (const p of body.items)`` likewise. A
  fill may not import, so its names are its own or the spine's (``body``).
"""

from __future__ import annotations

import re

from squadops.stacks.slot_subject import (
    AssertionSubject,
    MatcherClass,
    SlotAssertion,
    SubjectSurface,
)

_IDENT = r"[A-Za-z_$][\w$]*"
_EXPECT_RE = re.compile(r"(?<![\w.$])expect\s*\(")
_DECL_RE = re.compile(
    rf"\b(?:const|let|var)\s+(?P<name>{_IDENT})\s*(?::[^=\n]+)?=(?!=)\s*(?P<expr>[^\n;]+)"
)
_DESTRUCTURE_RE = re.compile(
    r"\b(?:const|let|var)\s*\{(?P<names>[^}]*)\}\s*(?::[^=\n]+)?=(?!=)\s*(?P<expr>[^\n;]+)"
)
_FOR_RE = re.compile(r"\bfor\s*\(")
_FOR_OF_RE = re.compile(rf"\s*(?:const|let|var)\s+(?P<name>{_IDENT})\s+of\s+(?P<expr>.+)", re.S)
_CHAIN_RE = re.compile(rf"\s*\.\s*(?P<word>{_IDENT})")
_HEAD_RE = re.compile(_IDENT)

#: Names an alias never shadows: the spine's response and the store's own symbols.
_RESERVED = frozenset({"body", "TABLES", "all", "expect"})

_STORE_RE = re.compile(r"all\(TABLES\.(?P<table>\w+)\)(?P<rest>.*)")
_INDEX_RE = re.compile(r"\[[^\]]+\]")
_INDEXED_FIELD_RE = re.compile(r"\[[^\]]+\]\.(?P<field>\w+)")
_TABLE_RE = re.compile(r"TABLES\.(?P<table>\w+)")
_ERROR_FIELD_RE = re.compile(r"body\.error\.(?P<field>\w+)")
_RESPONSE_FIELD_RE = re.compile(r"body\.(?P<field>\w+)")

_VALUE_MATCHERS = frozenset(
    {
        "toBe",
        "toEqual",
        "toStrictEqual",
        "toHaveLength",
        "toContain",
        "toContainEqual",
        "toMatch",
        "toBeCloseTo",
        "toBeGreaterThan",
        "toBeGreaterThanOrEqual",
        "toBeLessThan",
        "toBeLessThanOrEqual",
        "toBeNull",
        "toBeUndefined",
        "toBeNaN",
    }
)
_EXISTENCE_MATCHERS = frozenset({"toBeDefined", "toBeTruthy"})
#: Negated, these say only that the value is there.
_EXISTENCE_WHEN_NEGATED = frozenset({"toBeUndefined", "toBeNull", "toBeFalsy"})
_SHAPE_MATCHERS = frozenset({"toHaveProperty", "toBeInstanceOf", "toMatchObject", "toBeTypeOf"})


def _closing(text: str, open_index: int) -> int | None:
    """The index of the bracket closing the one at ``open_index``, quotes respected."""
    depth = 0
    quote = ""
    i = open_index
    while i < len(text):
        char = text[i]
        if quote:
            if char == "\\":
                i += 2
                continue
            if char == quote:
                quote = ""
        elif char in "'\"`":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _strip_comment(expr: str) -> str:
    return re.sub(r"\s//.*$", "", expr).strip()


def _normalise(target: str) -> tuple[str, bool]:
    """``(normalised target, read as a shape check)``."""
    t = " ".join(target.split())
    shape = False
    for _ in range(4):
        before = t
        t = re.sub(r"\s+as\s+[A-Za-z_$][\w$.<>\[\]|]*", "", t)
        t = t.replace("?.[", "[").replace("?.", ".").replace("!.", ".").replace("![", "[")
        t = re.sub(r"\[\s*(['\"])(\w+)\1\s*\]", r".\2", t)
        t = re.sub(r"\s*([.\[\]()])\s*", r"\1", t).rstrip("!").strip()
        while t.startswith("(") and _closing(t, 0) == len(t) - 1:
            t = t[1:-1].strip()
        if t.startswith(("typeof ", "typeof(")):
            t, shape = t[len("typeof") :].strip(), True
        wrapped = re.fullmatch(r"Array\.isArray\((?P<inner>.*)\)", t)
        if wrapped:
            t, shape = wrapped.group("inner").strip(), True
        if t == before:
            break
    return t, shape


def _resolve(target: str, aliases: dict[str, str]) -> str:
    """``target`` with the slot body's aliases substituted at its head, repeatedly."""
    for _ in range(8):
        head = _HEAD_RE.match(target)
        if head is None or head.group() in _RESERVED or head.group() not in aliases:
            return target
        target = aliases[head.group()] + target[head.end() :]
    return target


def _subject(target: str) -> AssertionSubject | None:
    store = _STORE_RE.fullmatch(target)
    if store:
        table, rest = store.group("table"), store.group("rest")
        if rest in ("", ".length") or _INDEX_RE.fullmatch(rest):
            return AssertionSubject(SubjectSurface.STORE, table=table)
        field = _INDEXED_FIELD_RE.match(rest)
        if field:
            return AssertionSubject(SubjectSurface.STORE, field=field.group("field"), table=table)
        return None
    whole_table = _TABLE_RE.fullmatch(target)
    if whole_table:
        return AssertionSubject(SubjectSurface.STORE, table=whole_table.group("table"))
    if target == "body.error":
        return AssertionSubject(SubjectSurface.ERROR_ENVELOPE)
    error_field = _ERROR_FIELD_RE.match(target)
    if error_field:
        return AssertionSubject(SubjectSurface.ERROR_ENVELOPE, field=error_field.group("field"))
    if target == "body":
        return AssertionSubject(SubjectSurface.RESPONSE)
    response_field = _RESPONSE_FIELD_RE.match(target)
    if response_field:
        return AssertionSubject(SubjectSurface.RESPONSE, field=response_field.group("field"))
    return None


def _matcher_class(matcher: str, negated: bool, shape: bool) -> MatcherClass:
    if shape:
        return MatcherClass.SHAPE
    if negated:
        return MatcherClass.EXISTENCE if matcher in _EXISTENCE_WHEN_NEGATED else MatcherClass.OTHER
    if matcher in _VALUE_MATCHERS:
        return MatcherClass.VALUE
    if matcher in _EXISTENCE_MATCHERS:
        return MatcherClass.EXISTENCE
    if matcher in _SHAPE_MATCHERS:
        return MatcherClass.SHAPE
    return MatcherClass.OTHER


def _aliases(text: str) -> list[tuple[int, str, str]]:
    """``(offset, name, normalised expression)`` for each alias the body declares."""
    found: list[tuple[int, str, str]] = []
    for m in _DECL_RE.finditer(text):
        found.append((m.start(), m.group("name"), _normalise(_strip_comment(m.group("expr")))[0]))
    for m in _DESTRUCTURE_RE.finditer(text):
        source = _normalise(_strip_comment(m.group("expr")))[0]
        for raw in m.group("names").split(","):
            name = raw.strip()
            if re.fullmatch(_IDENT, name):
                found.append((m.start(), name, f"{source}.{name}"))
    for m in _FOR_RE.finditer(text):
        close = _closing(text, m.end() - 1)
        header = _FOR_OF_RE.fullmatch(text[m.end() : close]) if close is not None else None
        if header:
            found.append(
                (m.start(), header.group("name"), f"{_normalise(header.group('expr'))[0]}[i]")
            )
    return sorted(found)


def read_slot_assertions(body: str) -> tuple[SlotAssertion, ...]:
    """Every ``expect(…)`` in a vitest slot body, in order, each with its subject or ``None``.

    Full-line comments are blanked first (line numbers kept), so a commented-out assertion is
    not read as one the body still makes.
    """
    text = "\n".join("" if line.lstrip().startswith("//") else line for line in body.split("\n"))
    aliases = _aliases(text)
    out: list[SlotAssertion] = []
    for m in _EXPECT_RE.finditer(text):
        open_index = m.end() - 1
        close = _closing(text, open_index)
        if close is None:
            continue
        target = text[open_index + 1 : close]
        negated = False
        matcher = ""
        matcher_at = close
        pos = close + 1
        while (step := _CHAIN_RE.match(text, pos)) is not None:
            pos = step.end()
            word = step.group("word")
            if word == "not":
                negated = not negated
            elif word not in ("resolves", "rejects"):
                matcher, matcher_at = word, step.start("word")
                break
        bound = {name: expr for offset, name, expr in aliases if offset < m.start()}
        normalised, shape = _normalise(target)
        resolved, resolved_shape = _normalise(_resolve(normalised, bound))
        out.append(
            SlotAssertion(
                target=" ".join(target.split()),
                resolved=resolved,
                first_line=text.count("\n", 0, m.start()) + 1,
                last_line=text.count("\n", 0, matcher_at) + 1,
                matcher=matcher,
                matcher_class=_matcher_class(matcher, negated, shape or resolved_shape),
                subject=_subject(resolved),
            )
        )
    return tuple(out)
