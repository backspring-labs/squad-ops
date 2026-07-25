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
from dataclasses import dataclass

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
    status_code: int | None
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


def _decorator_kwargs(dec: ast.Call) -> tuple[int | None, str | None]:
    """``(status_code, response_model)`` as declared on the decorator."""
    status: int | None = None
    response_model: str | None = None
    for kw in dec.keywords:
        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
            status = kw.value.value if isinstance(kw.value.value, int) else None
        elif kw.arg == "response_model":
            response_model = ast.unparse(kw.value)
    return status, response_model


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
        status_code=status,
        response_model=response_model,
        func_name=node.name,
        arg_names=tuple(a.arg for a in node.args.args),
        end_lineno=dec.end_lineno,
        end_col_offset=dec.end_col_offset,
    )


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
    seed_routes = {_route_key(r.method, r.path): r for r in _routes(seed_source)}
    if not seed_routes:
        return emitted_source, []

    emitted = _routes(emitted_source)
    divergences: list[DecoratorDivergence] = []
    # (line, col) -> text to insert. Collected first, applied bottom-up so earlier splices
    # cannot shift the offsets of later ones.
    splices: list[tuple[int, int, str]] = []

    for got in emitted:
        want = seed_routes.get(_route_key(got.method, got.path))
        if want is None:
            continue

        if want.status_code is not None and got.status_code != want.status_code:
            divergences.append(
                DecoratorDivergence(
                    method=got.method.upper(),
                    path=got.path,
                    detail=(
                        f"status_code={want.status_code} declared by the scaffold, "
                        f"emitted as {got.status_code if got.status_code is not None else 'absent'}"
                    ),
                    restored=True,
                )
            )
            splices.append(
                (got.end_lineno, got.end_col_offset, f", status_code={want.status_code}")
            )

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

    if not splices:
        return emitted_source, divergences

    lines = emitted_source.splitlines(keepends=True)
    for lineno, col, text in sorted(splices, reverse=True):
        idx = lineno - 1
        if idx < 0 or idx >= len(lines):
            continue
        line = lines[idx]
        # end_col_offset points just past the decorator call's ``)``; insert before it.
        cut = col - 1
        if cut < 0 or cut > len(line) or line[cut : cut + 1] != ")":
            continue  # offsets did not land where expected — leave the line untouched
        lines[idx] = line[:cut] + text + line[cut:]

    return "".join(lines), divergences


def divergence_summary(divergences: list[DecoratorDivergence]) -> str:
    """One-line, log-safe rendering; restored items first so the log leads with what changed."""
    if not divergences:
        return ""
    ordered = sorted(divergences, key=lambda d: (not d.restored, d.method, d.path))
    return "; ".join(
        f"{'restored' if d.restored else 'observed'} {d.method} {d.path}: {d.detail}"
        for d in ordered
    )
