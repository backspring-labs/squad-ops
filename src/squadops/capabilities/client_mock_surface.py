"""A suite's mock of the frozen API client honours the client's declared surface — #668,
the data-fetch half.

The DOM anchors say WHERE a frontend suite looks; the client says WHAT its mock must
honour. fay-14 (``cyc_42eed09efbec``) spent its rounds on the second half: the dev's repair
mocked ``../api`` with a ``default`` export the frozen client does not have
(``art_7c768e464d3e``), and the qa role's final suite stubbed ``fetch`` beneath the client
with an error body shaped ``{error_code, message}`` while the client reads
``{"error": {code, message}}`` (``art_428bb2c5468c``) — so the message the suite waited
for could never reach the view. The client is frozen and its surface is knowable at plan
time; the appendix that shows it is guidance, this is the record.

Six rules, read off the suite's own bytes against a :class:`ClientSurface` declared by the
stack, so an app defect cannot produce any of them. Two families:

* the suite replaces the client module — its imports and its mock factory must name only
  what the client exports (``client_import_undeclared``, ``client_mock_exports_undeclared``),
  the factory must still provide a call (``client_mock_omits_calls``), and an assertion on
  the call must match its signature: a path first, without the prefix the client adds,
  and no more positional arguments than declared (``client_call_asserted_off_signature``);
* the suite stubs ``fetch`` beneath the client — a URL it asserts carries the client's
  prefix (``fetch_asserted_without_client_prefix``), and a non-2xx body it resolves
  carries the envelope key the client unwraps (``fetch_stub_error_body_off_envelope``).

Reporting-only in this line: the findings are banked on the evaluation artifact beside
the verdict; whether any becomes blocking is a separate call on the counts the rolls
produce. Pure functions over strings; no stack vocabulary lives here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from squadops.capabilities.app_invocation import NETWORK_SEAM_FETCH_STUB
from squadops.capabilities.client_surface import ClientSurface

RULE_IMPORT_UNDECLARED = "client_import_undeclared"
RULE_MOCK_EXPORTS_UNDECLARED = "client_mock_exports_undeclared"
RULE_MOCK_OMITS_CALLS = "client_mock_omits_calls"
RULE_CALL_OFF_SIGNATURE = "client_call_asserted_off_signature"
RULE_FETCH_URL_UNPREFIXED = "fetch_asserted_without_client_prefix"
RULE_FETCH_ERROR_OFF_ENVELOPE = "fetch_stub_error_body_off_envelope"

#: Keys a module-mock factory may carry that are interop markers, not exports.
_INTEROP_KEYS = frozenset({"__esModule"})
#: The global the stub replaces, by the names a suite reaches it through.
_FETCH_GLOBALS = ("fetch", "global.fetch", "globalThis.fetch", "window.fetch")
_FETCH_STUB_RE = re.compile(NETWORK_SEAM_FETCH_STUB)
_FETCH_ALIAS_RE = re.compile(
    r"""(?:global(?:This)?|window)\s*\.\s*fetch\s*=\s*(\w+)\s*[;\n]"""
    r"""|(?:vi|jest)\s*\.\s*stubGlobal\s*\(\s*['"`]fetch['"`]\s*,\s*(\w+)\s*\)"""
    r"""|(?:const|let|var)\s+(\w+)\s*=\s*(?:vi|jest)\s*\.\s*spyOn\s*\(\s*"""
    r"""(?:global(?:This)?|window)\s*,\s*['"`]fetch['"`]"""
)
_CALLED_WITH_RE = re.compile(
    r"""expect\(\s*([\w.]+(?:\([\w.]*\))?)\s*\)\s*\.((?:not\.)?)toHaveBeen(Nth|Last)?CalledWith\("""
)
_RESOLVED_VALUE_RE = re.compile(r"""\.mockResolvedValue(?:Once)?\(""")
_STRING_LITERAL_RE = re.compile(r"""^\s*(['"])((?:(?!\1).)*)\1\s*$|^\s*`([^`$]*)`\s*$""")


@dataclass(frozen=True)
class MockSurfaceFinding:
    """One rule the suite broke, with the detail the author is handed back."""

    rule: str
    detail: str
    line: int


# --- parsing helpers ---------------------------------------------------------------


def _line_of(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def _balanced(text: str, start: int, opener: str = "{", closer: str = "}") -> str | None:
    """The balanced ``opener … closer`` block starting at ``text[start]``, or ``None``.

    Skips string and template literals so a brace inside a message cannot unbalance it."""
    if start >= len(text) or text[start] != opener:
        return None
    depth = 0
    i = start
    quote: str | None = None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
        i += 1
    return None


def _split_top_level(inner: str) -> list[str]:
    """Comma-separated parts of an object or argument list, at depth zero only."""
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(inner):
        c = inner[i]
        if quote:
            buf.append(c)
            if c == "\\" and i + 1 < len(inner):
                buf.append(inner[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
            buf.append(c)
        elif c in "{([":
            depth += 1
            buf.append(c)
        elif c in "})]":
            depth -= 1
            buf.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    parts.append("".join(buf))
    return [p for p in parts if p.strip()]


_ENTRY_RE = re.compile(
    r"""^\s*(?:async\s+)?(?:get\s+|set\s+)?(\w+|['"][^'"]+['"])\s*(?::|\(|$)""", re.S
)


def _object_entries(literal: str) -> list[tuple[str, str]] | None:
    """``(key, value_text)`` per top-level entry of an object literal; a spread is
    ``("...", expr)``; ``None`` when the text is not an object literal."""
    if not literal.startswith("{") or not literal.endswith("}"):
        return None
    entries: list[tuple[str, str]] = []
    for part in _split_top_level(literal[1:-1]):
        stripped = part.strip()
        if stripped.startswith("..."):
            entries.append(("...", stripped[3:].strip()))
            continue
        m = _ENTRY_RE.match(stripped)
        if not m:
            continue
        key = m.group(1).strip("'\"")
        value = stripped[m.end() :].strip() if ":" in stripped[: m.end()] else stripped
        entries.append((key, value))
    return entries


def _first_object(text: str) -> str | None:
    idx = text.find("{")
    return _balanced(text, idx) if idx >= 0 else None


def _factory_object(tail: str) -> str | None:
    """The object a ``vi.mock`` factory returns: ``() => ({…})``, ``() => { … return {…} }``
    or ``function () { … return {…} }``; ``None`` when there is no factory to read."""
    m = re.match(r"\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>\s*", tail)
    if m:
        body = tail[m.end() :]
        if body.startswith("("):
            return _first_object(body)
        if body.startswith("{"):
            block = _balanced(body, 0)
            if block is None:
                return None
            ret = re.search(r"\breturn\s*\(?\s*\{", block)
            return _balanced(block, block.index("{", ret.start())) if ret else None
        return None
    m = re.match(r"\s*(?:async\s+)?function\s*\w*\s*\([^)]*\)\s*\{", tail)
    if m:
        block = _balanced(tail, m.end() - 1)
        if block is None:
            return None
        ret = re.search(r"\breturn\s*\(?\s*\{", block)
        return _balanced(block, block.index("{", ret.start())) if ret else None
    return None


def _string_literal(arg: str) -> str | None:
    m = _STRING_LITERAL_RE.match(arg)
    if not m:
        return None
    return m.group(2) if m.group(1) else m.group(3)


# --- what the suite does with the client -------------------------------------------


@dataclass(frozen=True)
class _ClientUse:
    imports: tuple[tuple[str, int], ...]
    """Names imported from the client, as ``(name, line)``; ``default`` for a default import."""
    mocked: bool
    factory_keys: tuple[str, ...] | None
    """The factory's top-level keys (``...`` for a spread); ``None`` when there is no factory
    (an automock preserves the surface) or it could not be read."""
    factory_line: int
    call_aliases: dict[str, str]
    """Identifier the suite asserts on → the client export it stands for."""


def _parse_imports(
    content: str, surface: ClientSurface, aliases: dict[str, str]
) -> list[tuple[str, int]]:
    """Every name the suite imports from the client, and the local aliases it binds them to.

    One import statement can bind several shapes at once — named, renamed, namespace and
    default — so each clause is read on its own rather than by matching the statement as a
    whole.
    """
    imports: list[tuple[str, int]] = []
    import_re = re.compile(
        r"""^\s*import\s+(.+?)\s+from\s+['"`](?:""" + surface.module_specifier + r""")['"`]""",
        re.M,
    )
    for m in import_re.finditer(content):
        line = _line_of(content, m.start())
        for piece in re.split(r",(?![^{]*})", m.group(1).strip()):
            piece = piece.strip()
            if not piece:
                continue
            if piece.startswith("{"):
                for name in piece.strip("{} ").split(","):
                    base, _, local = name.strip().partition(" as ")
                    if not base.strip():
                        continue
                    imports.append((base.strip(), line))
                    if local.strip():
                        aliases[local.strip()] = base.strip()
            elif piece.startswith("* as "):
                namespace = piece[5:].strip()
                for export in surface.call_exports:
                    aliases[f"{namespace}.{export.name}"] = export.name
            else:
                imports.append(("default", line))
    return imports


def _parse_module_mock(
    content: str, surface: ClientSurface, aliases: dict[str, str]
) -> tuple[bool, tuple[str, ...] | None, int]:
    """Whether the module is mocked, the factory's keys, and the line it sits on.

    ``None`` keys means mocked without a factory (auto-mock), which replaces nothing the
    check can judge — distinct from a factory that provides an empty object.
    """
    mock_re = re.compile(
        r"""(?:vi|jest)\s*\.\s*(?:do)?[mM]ock\(\s*['"`](?:"""
        + surface.module_specifier
        + r""")['"`]\s*(,)?"""
    )
    mocked = False
    for m in mock_re.finditer(content):
        mocked = True
        if not m.group(1):
            continue
        obj = _factory_object(content[m.end() :])
        entries = _object_entries(obj) if obj else None
        if entries is None:
            continue
        for key, value in entries:
            if key in surface.names and re.fullmatch(r"\w+", value or ""):
                aliases[value] = key
        return mocked, tuple(k for k, _ in entries), _line_of(content, m.start())
    return mocked, None, 0


def _mocked_call_aliases(content: str, surface: ClientSurface, aliases: dict[str, str]) -> None:
    """The other names a call is asserted through: the export itself, the `mocked()`
    wrappers around it, and any local bound to one of those."""
    for export in surface.call_exports:
        aliases[export.name] = export.name
        aliases[f"vi.mocked({export.name})"] = export.name
        aliases[f"jest.mocked({export.name})"] = export.name
    for m in re.finditer(
        r"""(?:const|let|var)\s+(\w+)\s*=\s*(?:vi|jest)\.mocked\(\s*([\w.]+)\s*\)""",
        content,
    ):
        target = aliases.get(m.group(2)) or (m.group(2) if m.group(2) in surface.names else None)
        if target:
            aliases[m.group(1)] = target


def _client_use(content: str, surface: ClientSurface) -> _ClientUse:
    """How this suite reaches the client: what it imports, whether it mocks the module, and
    every local name a call can be asserted through."""
    aliases: dict[str, str] = {}
    imports = _parse_imports(content, surface, aliases)
    mocked, factory_keys, factory_line = _parse_module_mock(content, surface, aliases)
    _mocked_call_aliases(content, surface, aliases)
    return _ClientUse(tuple(imports), mocked, factory_keys, factory_line, aliases)


def _fetch_subjects(content: str) -> set[str] | None:
    """The names a stubbed ``fetch`` is asserted through, or ``None`` when it is not stubbed."""
    if not _FETCH_STUB_RE.search(content):
        return None
    subjects = set(_FETCH_GLOBALS)
    for m in _FETCH_ALIAS_RE.finditer(content):
        subjects.add(next(g for g in m.groups() if g))
    return subjects


def _called_with(content: str) -> list[tuple[str, bool, list[str], int]]:
    """Every ``expect(subject).toHaveBeen…CalledWith(args)`` as
    ``(subject, negated, positional_args, line)`` — the Nth form's index dropped."""
    out: list[tuple[str, bool, list[str], int]] = []
    for m in _CALLED_WITH_RE.finditer(content):
        args_block = _balanced(content, m.end() - 1, "(", ")")
        if args_block is None:
            continue
        args = _split_top_level(args_block[1:-1])
        if m.group(3) == "Nth":
            args = args[1:]
        out.append((m.group(1), bool(m.group(2)), args, _line_of(content, m.start())))
    return out


def _resolved_responses(content: str) -> list[tuple[list[tuple[str, str]], int]]:
    """Every ``mockResolvedValue[Once]({…})`` whose literal is Response-shaped (carries
    ``ok`` or ``status``), as its entries and line — whatever mock it hangs off."""
    out: list[tuple[list[tuple[str, str]], int]] = []
    for m in _RESOLVED_VALUE_RE.finditer(content):
        block = _balanced(content, m.end() - 1, "(", ")")
        if block is None:
            continue
        literal = block[1:-1].strip()
        entries = _object_entries(literal)
        if not entries:
            continue
        keys = {k for k, _ in entries}
        if "ok" in keys or ("status" in keys and "json" in keys):
            out.append((entries, _line_of(content, m.start())))
    return out


# --- the rules ---------------------------------------------------------------------


def _import_findings(
    use: _ClientUse, surface: ClientSurface, declared: str
) -> list[MockSurfaceFinding]:
    """A name imported from the client that the client does not export (#668).

    The binding is ``undefined`` before any test runs, so every assertion through it is
    about the suite's own imagination — which is why this is the class that passes forever.
    """
    findings: list[MockSurfaceFinding] = []

    undeclared_imports = [
        (name, line)
        for name, line in use.imports
        if (name == "default" and surface.default_export is None)
        or (name != "default" and name not in surface.names)
    ]
    if undeclared_imports:
        names = ", ".join(
            "a default import" if n == "default" else f"`{n}`" for n, _ in undeclared_imports
        )
        findings.append(
            MockSurfaceFinding(
                RULE_IMPORT_UNDECLARED,
                f"imports {names} from `{surface.path}`, which exports only {declared}"
                + (" and no default" if surface.default_export is None else "")
                + " — the binding is `undefined` before any test runs.",
                undeclared_imports[0][1],
            )
        )
    return findings


def _mock_findings(
    use: _ClientUse, surface: ClientSurface, declared: str
) -> list[MockSurfaceFinding]:
    """A module mock that replaces the client with a surface it does not have."""
    findings: list[MockSurfaceFinding] = []
    if use.factory_keys is not None:
        keys = [k for k in use.factory_keys if k != "..." and k not in _INTEROP_KEYS]
        undeclared = [
            k
            for k in keys
            if k not in surface.names and not (k == "default" and surface.default_export)
        ]
        if undeclared:
            findings.append(
                MockSurfaceFinding(
                    RULE_MOCK_EXPORTS_UNDECLARED,
                    f"mocks `{surface.path}` with "
                    + ", ".join(f"`{k}`" for k in undeclared)
                    + f", which the client does not export (it exports {declared}"
                    + (" and no default" if surface.default_export is None else "")
                    + "); a view importing the real names gets `undefined`.",
                    use.factory_line,
                )
            )
        call_names = {e.name for e in surface.call_exports}
        if "..." not in use.factory_keys and not (call_names & set(keys)):
            findings.append(
                MockSurfaceFinding(
                    RULE_MOCK_OMITS_CALLS,
                    f"the mock of `{surface.path}` provides none of its calls ("
                    + ", ".join(f"`{n}`" for n in sorted(call_names))
                    + "); the module is replaced whole, so the view's call is `undefined`.",
                    use.factory_line,
                )
            )
    return findings


def _call_findings(
    content: str, use: _ClientUse, surface: ClientSurface
) -> list[MockSurfaceFinding]:
    """A call asserted with a shape the declared signature never takes, and a `fetch` stub
    asserted on a URL the client would have prefixed."""
    findings: list[MockSurfaceFinding] = []
    fetch_subjects = _fetch_subjects(content)
    prefix = surface.path_prefix
    prefix = surface.path_prefix
    for subject, negated, args, line in _called_with(content):
        if negated or not args:
            continue
        export_name = use.call_aliases.get(subject)
        if export_name is not None:
            export = surface.export(export_name)
            if export is None:
                continue
            first = _string_literal(args[0])
            problems: list[str] = []
            if first is not None and not first.startswith("/"):
                problems.append(
                    f"first argument `{first}` is not a path (`{export.param_names[0]}` is)"
                    if export.param_names
                    else f"first argument `{first}` is not a path"
                )
            elif (
                first is not None and prefix and (first == prefix or first.startswith(prefix + "/"))
            ):
                problems.append(
                    f"first argument `{first}` carries `{prefix}`, which the client adds itself"
                )
            if len(args) > len(export.param_names) and export.param_names:
                problems.append(f"{len(args)} positional arguments against `{export.signature}`")
            if problems:
                findings.append(
                    MockSurfaceFinding(
                        RULE_CALL_OFF_SIGNATURE,
                        f"asserts `{export_name}` was called with a shape it never takes: "
                        + "; ".join(problems)
                        + ".",
                        line,
                    )
                )
        elif fetch_subjects and subject in fetch_subjects and prefix:
            first = _string_literal(args[0])
            if first is None or not first.startswith("/"):
                continue
            if first == prefix or first.startswith(prefix + "/"):
                continue
            findings.append(
                MockSurfaceFinding(
                    RULE_FETCH_URL_UNPREFIXED,
                    f"asserts `fetch` was called with `{first}`; the client prefixes every "
                    f"call with `{prefix}`, so the stub beneath it sees `{prefix}{first}`.",
                    line,
                )
            )
    return findings


def _envelope_findings(content: str, surface: ClientSurface) -> list[MockSurfaceFinding]:
    """A non-2xx response stubbed with a body the client cannot read its error out of."""
    findings: list[MockSurfaceFinding] = []
    fetch_subjects = _fetch_subjects(content)
    envelope = surface.error_envelope_key
    if fetch_subjects and envelope:
        for entries, line in _resolved_responses(content):
            values = dict(entries)
            if values.get("ok", "").strip() != "false":
                continue
            body = _first_object(values.get("json", ""))
            body_entries = _object_entries(body) if body else None
            if not body_entries:
                continue
            keys = [k for k, _ in body_entries]
            if envelope in keys or "..." in keys:
                continue
            findings.append(
                MockSurfaceFinding(
                    RULE_FETCH_ERROR_OFF_ENVELOPE,
                    "resolves a non-2xx response whose body has "
                    + ", ".join(f"`{k}`" for k in keys)
                    + f" and no `{envelope}`; the client reads `{envelope}.code` and "
                    f"`{envelope}.message` from it, so the view sees neither.",
                    line,
                )
            )
    return findings


def mock_surface_findings(content: str, surface: ClientSurface) -> list[MockSurfaceFinding]:
    """The rules the suite breaks against the stack's declared client surface.

    One function per rule, composed here: a rule is added by writing it and listing it,
    and a failure names which rule moved. All rules run and findings accumulate — an
    author fixing one defect per revision would spend the whole budget on a suite that
    had three.
    """
    use = _client_use(content, surface)
    declared = ", ".join(f"`{e.signature}`" for e in surface.exports)
    return [
        *_import_findings(use, surface, declared),
        *_mock_findings(use, surface, declared),
        *_call_findings(content, use, surface),
        *_envelope_findings(content, surface),
    ]


def mock_surface_observations(content: str, surface: ClientSurface) -> dict[str, object]:
    """What the record banks beside the verdict, rules or not."""
    use = _client_use(content, surface)
    fetch_subjects = _fetch_subjects(content)
    calls = _called_with(content)
    return {
        "client_mocked": use.mocked,
        "mocked_exports": (
            sorted(k for k in use.factory_keys if k not in _INTEROP_KEYS)
            if use.factory_keys is not None
            else None
        ),
        "client_imports": sorted({n for n, _ in use.imports}),
        "fetch_stubbed": fetch_subjects is not None,
        "client_call_assertions": sum(1 for s, _, _, _ in calls if s in use.call_aliases),
        "fetch_assertions": sum(
            1 for s, _, _, _ in calls if fetch_subjects and s in fetch_subjects
        ),
        "fetch_error_responses": sum(
            1
            for entries, _ in _resolved_responses(content)
            if dict(entries).get("ok", "").strip() == "false"
        ),
    }
