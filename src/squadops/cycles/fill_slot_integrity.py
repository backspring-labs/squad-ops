"""Fill-slot decorator integrity — enforcing what the scaffold *says* it owns.

SIP-0100 enforces scaffold ownership at **file** granularity: a frozen path is restored
wholesale. A fill slot has no such enforcement, because the producer legitimately rewrites
the file — it is the slot's whole point. But a fill slot is not uniformly producer-owned.
The emitted stub says so in its own header:

    "API route stubs — scaffold-owned signatures, fill-only bodies."

That is **instruction, not enforcement**, and pf-40 measured the difference. The scaffold
seeded::

    @router.post("/runs", response_model=RunEvent, status_code=201)

and the dev agent's emission replaced it with::

    @router.post("/runs")

dropping the status code (and the response models, and the scaffold's function and
parameter names). ``POST /runs`` then answered 200 while the contract's probe demanded 201
— the identical failure that rejected pf-39, on a deploy that had just fixed the scaffold
to emit 201 in the first place. Emitting the right skeleton is necessary and not
sufficient: something has to hold it there.

Scope — deliberately narrow, because the safe surface is smaller than the owned one:

* **Restored:** ``status_code``. It is body-independent. Injecting it cannot break the
  producer's implementation, because nothing in a function body depends on the success
  code its decorator declares.
* **Reported, not rewritten:** everything else — path, method, ``response_model``,
  function name, parameter names. Restoring those is *not* safe from here. The producer
  renamed ``payload`` to ``data`` and used it throughout its body; restoring the scaffold
  signature would leave the body referencing a name that no longer exists. Rewriting
  ``response_model`` can turn a working handler into a 500 if the body returns a shape the
  model rejects. Those divergences are surfaced as evidence so the class stays visible, and
  the typed criteria (``endpoint_defined``) already fail a wrong path or method.

Matching is by ``(method, path-with-parameters-normalized)``, so a producer that renamed a
path parameter still matches its scaffold counterpart and still gets its status code back.
A route the scaffold never declared, or one the producer dropped, is left alone — that is
``endpoint_defined``'s job, not this module's.

Pure: ``(seed_source, emitted_source) -> (corrected_source, divergences)``. No I/O, no
ports. The caller decides what to do with the divergences.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace

_ROUTER_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})
_PARAM = re.compile(r"\{[^}]*\}")


@dataclass(frozen=True)
class DecoratorDivergence:
    """One scaffold-owned decorator detail the producer changed.

    ``restored`` distinguishes what this module put back from what it only observed —
    the evidence record needs both, and conflating them would overstate enforcement.
    """

    method: str
    path: str
    detail: str
    restored: bool


@dataclass(frozen=True)
class _Route:
    method: str
    path: str
    status_kw: _StatusKw | None
    response_model: str | None
    func_name: str
    arg_names: tuple[str, ...]
    # byte offsets of the decorator call's closing paren, for splicing
    end_lineno: int
    end_col_offset: int


def _route_key(method: str, path: str) -> tuple[str, str]:
    """Method + path with parameter *names* erased, so a renamed path parameter still
    matches its scaffold counterpart (the pf-31 ``{id}``/``{run_id}`` class renames these
    routinely, and a status code should survive that)."""
    return method.upper(), _PARAM.sub("{}", path)


def _routes(source: str) -> list[_Route]:
    """Every ``@router.<method>("<path>", ...)``-decorated function in ``source``.

    Returns an empty list for unparseable source — a syntactically broken emission is the
    test runner's failure to report, not this module's, and raising here would convert a
    visible test failure into an opaque enforcement crash.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    out: list[_Route] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for dec in node.decorator_list:
            route = _route_from_decorator(dec, node)
            if route is not None:
                out.append(route)
    return out


def _route_decorator_path(dec: ast.expr) -> str | None:
    """The literal path of a ``@router.<method>("...")`` decorator, or None when ``dec`` is
    not one (a bare ``@staticmethod``, a non-router call, a computed path)."""
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return None
    if dec.func.attr not in _ROUTER_METHODS:
        return None
    if not dec.args or not isinstance(dec.args[0], ast.Constant):
        return None
    path = dec.args[0].value
    return path if isinstance(path, str) else None


@dataclass(frozen=True)
class _StatusKw:
    """A ``status_code=`` keyword as it actually appears on the decorator.

    ``value`` is the literal int, or None when the producer wrote an expression
    (``status.HTTP_201_CREATED``). The distinction between *that* and no keyword at all is
    the whole point of this type: pf-44 collapsed them, decided a present-but-symbolic
    status code was absent, appended its own, and produced
    ``status_code=status.HTTP_201_CREATED, status_code=201`` — a duplicate keyword, a
    SyntaxError, an unimportable module, and a test suite that could not even be collected.
    """

    value: int | None
    text: str
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int


def _decorator_kwargs(dec: ast.Call) -> tuple[_StatusKw | None, str | None]:
    """``(status_code keyword or None, response_model)`` as declared on the decorator."""
    status: _StatusKw | None = None
    response_model: str | None = None
    for kw in dec.keywords:
        if kw.arg == "status_code":
            if kw.end_lineno is None or kw.end_col_offset is None:  # pragma: no cover
                continue
            literal = (
                kw.value.value
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int)
                else None
            )
            status = _StatusKw(
                value=literal,
                text=ast.unparse(kw.value),
                lineno=kw.lineno,
                col_offset=kw.col_offset,
                end_lineno=kw.end_lineno,
                end_col_offset=kw.end_col_offset,
            )
        elif kw.arg == "response_model":
            response_model = ast.unparse(kw.value)
    return status, response_model


def _reconcile_status_code(
    got: _Route,
    declared: int,
    divergences: list[DecoratorDivergence],
    splices: list[tuple[int, int, int, int, str]],
) -> None:
    """Decide what to do about one route's status code. Three cases, one of them safe to
    append and only one.

    Appending is correct **only** when the keyword is absent. pf-44 appended onto a
    decorator that already carried ``status_code=status.HTTP_201_CREATED`` — because a
    symbolic value parsed as "no literal" and the old code could not tell that apart from
    "no keyword" — and produced a duplicate keyword argument. That is a SyntaxError, so
    ``backend/routes.py`` would not import, so pytest aborted during collection with exit
    4, so every check downstream failed and every repair regenerated the same corruption.
    An enforcement mechanism that turns correct code into unparseable code is worse than
    no enforcement at all.

    A present-but-wrong *literal* is replaced in place rather than appended (same
    body-independence argument as the original restore, and appending there would have
    produced the identical duplicate). A present *expression* is left completely alone and
    only reported: it cannot be evaluated from here, ``status.HTTP_201_CREATED`` is the
    idiomatic spelling of exactly what the scaffold asked for, and the behavioral probe
    already checks the status the app actually returns.
    """
    kw = got.status_kw

    if kw is None:
        divergences.append(
            DecoratorDivergence(
                method=got.method.upper(),
                path=got.path,
                detail=f"status_code={declared} declared by the scaffold, emitted as absent",
                restored=True,
            )
        )
        # insert before the decorator call's closing paren (zero-width span)
        splices.append(
            (
                got.end_lineno,
                got.end_col_offset - 1,
                got.end_lineno,
                got.end_col_offset - 1,
                f", status_code={declared}",
            )
        )
        return

    if kw.value == declared:
        return  # already exactly what the scaffold declared

    if kw.value is not None:
        divergences.append(
            DecoratorDivergence(
                method=got.method.upper(),
                path=got.path,
                detail=(f"status_code={declared} declared by the scaffold, emitted as {kw.value}"),
                restored=True,
            )
        )
        splices.append(
            (
                kw.lineno,
                kw.col_offset,
                kw.end_lineno,
                kw.end_col_offset,
                f"status_code={declared}",
            )
        )
        return

    if re.search(rf"(?<!\d){declared}(?!\d)", kw.text):
        # ``status.HTTP_201_CREATED`` spells the declared code in its own name — the
        # idiomatic form of exactly what the scaffold asked for. Reporting it as a
        # divergence would put a "problem" row on correct code, and divergence evidence
        # feeds repair context: an invitation to churn on a non-issue. Silence is honest
        # here. Expressions that do NOT name the declared code (``status.HTTP_200_OK``
        # against a declared 201, ``HTTPStatus.CREATED`` — no digits) are still reported.
        return

    divergences.append(
        DecoratorDivergence(
            method=got.method.upper(),
            path=got.path,
            detail=(
                f"status_code={declared} declared by the scaffold, emitted as the expression "
                f"{kw.text!r} — left as written; a non-literal cannot be reconciled from here "
                f"and the behavioral probe checks the status actually returned"
            ),
            restored=False,
        )
    )


def _route_from_decorator(
    dec: ast.expr, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> _Route | None:
    path = _route_decorator_path(dec)
    if path is None:
        return None
    assert isinstance(dec, ast.Call)  # guaranteed by _route_decorator_path
    if dec.end_lineno is None or dec.end_col_offset is None:
        return None
    status, response_model = _decorator_kwargs(dec)
    return _Route(
        method=dec.func.attr,  # type: ignore[union-attr]  # Attribute, per the guard above
        path=path,
        status_kw=status,
        response_model=response_model,
        func_name=node.name,
        arg_names=tuple(a.arg for a in node.args.args),
        end_lineno=dec.end_lineno,
        end_col_offset=dec.end_col_offset,
    )


def _router_assignment(source: str) -> tuple[str, int, int] | None:
    """The module-level ``router = APIRouter(...)`` statement as ``(text, start, end)``
    1-indexed inclusive line span, or None when absent/unparseable.

    Body-independent like ``status_code``: the router object's prefix changes where routes
    register, never what a handler body references. So it is safe to restore.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "router":
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name != "APIRouter" or node.end_lineno is None:
            continue
        lines = source.splitlines()
        text = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        return text, node.lineno, node.end_lineno
    return None


def _restore_router_assignment(
    seed_source: str, emitted_source: str
) -> tuple[str, list[DecoratorDivergence]]:
    """Put back the scaffold's ``router = APIRouter(...)`` when the producer changed it.

    pf-41: the scaffold seeded ``router = APIRouter()`` and the dev agent emitted
    ``router = APIRouter(prefix="/api")``. Every route then registered under a second
    ``/api``, the contract probe asked for ``POST /runs``, and a perfectly healthy app
    answered 404 to its own contract.

    The mistake is a reasonable one: the scaffold's frontend calls ``/api/...`` and the
    agent made the backend match. It could not see that the proxy strips that prefix
    before the request arrives — that rewrite lives in ``vite.config.js``, a frozen file
    the agent never reads. So the fact is knowable, authoritative, and was simply never
    in front of it.

    Restoring is safe for the same reason ``status_code`` is: the router's prefix decides
    where routes register, never what a handler body references.
    """
    want = _router_assignment(seed_source)
    got = _router_assignment(emitted_source)
    if want is None or got is None or want[0].strip() == got[0].strip():
        return emitted_source, []

    lines = emitted_source.splitlines(keepends=True)
    start, end = got[1] - 1, got[2]
    if start < 0 or end > len(lines):
        return emitted_source, []
    newline = "\n" if not lines[end - 1].endswith("\n") else ""
    lines[start:end] = [want[0] + newline]
    return "".join(lines), [
        DecoratorDivergence(
            method="-",
            path="(router)",
            detail=(
                f"scaffold declares `{want[0].strip()}`, emitted as `{got[0].strip()}` — "
                "a router prefix re-homes every route and the app 404s its own contract"
            ),
            restored=True,
        )
    ]


def restore_declared_status_codes(
    seed_source: str, emitted_source: str
) -> tuple[str, list[DecoratorDivergence]]:
    """Put back every ``status_code`` the scaffold declared and the producer dropped.

    Args:
        seed_source: the scaffold's original bytes for this fill slot (the bound record's
            authority — never re-derived).
        emitted_source: what the producer emitted for the same path.

    Returns:
        ``(corrected_source, divergences)``. ``corrected_source`` is ``emitted_source``
        unchanged when nothing needed restoring, so a compliant producer is byte-identical
        through this function.
    """
    corrected, divergences = _restore_router_assignment(seed_source, emitted_source)
    emitted_source = corrected

    seed_routes = {_route_key(r.method, r.path): r for r in _routes(seed_source)}
    if not seed_routes:
        return emitted_source, divergences

    emitted = _routes(emitted_source)
    # (line, col) -> text to insert. Collected first, applied bottom-up so earlier splices
    # cannot shift the offsets of later ones.
    splices: list[tuple[int, int, int, int, str]] = []

    for got in emitted:
        want = seed_routes.get(_route_key(got.method, got.path))
        if want is None:
            continue

        declared = want.status_kw.value if want.status_kw else None
        if declared is not None:
            _reconcile_status_code(got, declared, divergences, splices)

        # Reported only — see the module docstring for why these are not rewritten.
        if want.response_model and got.response_model != want.response_model:
            divergences.append(
                DecoratorDivergence(
                    method=got.method.upper(),
                    path=got.path,
                    detail=(
                        f"response_model={want.response_model} declared by the scaffold, "
                        f"emitted as {got.response_model or 'absent'}"
                    ),
                    restored=False,
                )
            )
        if want.func_name != got.func_name:
            divergences.append(
                DecoratorDivergence(
                    method=got.method.upper(),
                    path=got.path,
                    detail=(
                        f"scaffold-owned handler name {want.func_name!r} emitted as "
                        f"{got.func_name!r}"
                    ),
                    restored=False,
                )
            )
        if want.arg_names != got.arg_names:
            divergences.append(
                DecoratorDivergence(
                    method=got.method.upper(),
                    path=got.path,
                    detail=(
                        f"scaffold-owned parameters {list(want.arg_names)} emitted as "
                        f"{list(got.arg_names)}"
                    ),
                    restored=False,
                )
            )

    corrected = _apply_splices(emitted_source, splices)
    if corrected != emitted_source:
        # The invariant, enforced by construction rather than by enumerating decorator
        # shapes: this module never hands back source that parses worse than what it
        # received. pf-44 proved a restorer that can corrupt is worse than none — if a
        # splice produced unparseable output, abandon the whole restore, return the
        # producer's bytes untouched, and downgrade the divergence records so the
        # evidence never claims a restoration that did not survive.
        try:
            ast.parse(corrected)
        except SyntaxError:
            return emitted_source, [
                replace(
                    d,
                    restored=False,
                    detail=d.detail + " (restore abandoned: result would not parse)",
                )
                if d.restored
                else d
                for d in divergences
            ]
    return corrected, divergences


def _apply_splices(source: str, splices: list[tuple[int, int, int, int, str]]) -> str:
    """Apply edits bottom-up so an earlier one cannot shift a later one's offsets.

    A zero-width span is an insertion; a non-empty one replaces the text it covers. Every
    guard below leaves the line untouched rather than guessing — this module's whole job is
    to hand back source that still parses, so a splice that does not land exactly where the
    AST said it would is abandoned, not forced.
    """
    if not splices:
        return source

    lines = source.splitlines(keepends=True)
    for lineno, col, end_lineno, end_col, text in sorted(splices, reverse=True):
        idx = lineno - 1
        if idx < 0 or idx >= len(lines) or lineno != end_lineno:
            continue  # multi-line spans are not reconciled from here
        line = lines[idx]
        if col < 0 or end_col > len(line) or col > end_col:
            continue  # offsets did not land where expected
        if col == end_col:
            if line[col : col + 1] != ")":
                continue  # an insertion must land just before the decorator's closing paren
            text = _separator_adjusted(lines, idx, col, text)
        lines[idx] = line[:col] + text + line[end_col:]

    return "".join(lines)


def _separator_adjusted(lines: list[str], idx: int, col: int, text: str) -> str:
    """Drop the leading ``", "`` from an insertion whose context already provides it.

    The insertion text is built for the common shape — a single-line decorator whose last
    argument has no trailing comma — where ``", status_code=201"`` is exactly right. A
    multi-line decorator formatted Black-style ends its last argument with a trailing
    comma before the closing paren's own line::

        @router.post(
            "/runs",
            response_model=RunEvent,
        )

    Inserting the comma-prefixed text there produced ``RunEvent,`` followed by
    ``, status_code=201)`` — a double comma, a SyntaxError, and an unimportable module:
    the exact corruption class this module exists to never emit, through a decorator
    shape the original tests simply never swept. The last non-whitespace character before
    the insertion point decides: after ``,`` or ``(`` the separator is already there (or
    not needed); after anything else the prefix stands.
    """
    before = lines[idx][:col].rstrip()
    j = idx
    while not before and j > 0:
        j -= 1
        before = lines[j].rstrip()
    if before.endswith(",") or before.endswith("("):
        return text.removeprefix(", ")
    return text


def divergence_summary(divergences: list[DecoratorDivergence]) -> str:
    """One-line, log-safe rendering; restored items first so the log leads with what changed."""
    if not divergences:
        return ""
    ordered = sorted(divergences, key=lambda d: (not d.restored, d.method, d.path))
    return "; ".join(
        f"{'restored' if d.restored else 'observed'} {d.method} {d.path}: {d.detail}"
        for d in ordered
    )
