"""Render typed acceptance criteria as authoritative, human-legible expectation lines.

pf-31 Fix A (docs/plans/pf31-correction-convergence-fixes.md): the resolved
TypedChecks reach the repair envelope but rendered as dict-repr soup below the
plan's contradicting prose — every pf-31 repair followed the prose's
``{run_id}`` over the contract's ``{id}``. These formatters turn the typed
entries into one exact line per check so prompts can lead with them as an
authoritative block. Pure data-in/lines-out — all prompt heading/instruction
text lives in the request-template assets.
"""

from __future__ import annotations

from typing import Any

_RESERVED_KEYS = {"check", "severity", "description", "id"}


def _check_and_params(entry: Any) -> tuple[str, dict] | None:
    """Normalize the three shapes a typed criterion travels in.

    In-process: a ``TypedCheck`` dataclass (``check``/``params`` attributes).
    On the wire: either the resolved form ``{"check": ..., "params": {...}}``
    or the plan-authored flat form ``{"check": ..., <param keys inline>}``.
    Returns None for prose strings and anything else non-typed.
    """
    check = getattr(entry, "check", None)
    params = getattr(entry, "params", None)
    if isinstance(check, str) and isinstance(params, dict):
        return check, params
    if isinstance(entry, dict) and isinstance(entry.get("check"), str):
        raw_params = entry.get("params")
        if isinstance(raw_params, dict):
            return entry["check"], raw_params
        return entry["check"], {k: v for k, v in entry.items() if k not in _RESERVED_KEYS}
    return None


def is_typed_criterion(entry: Any) -> bool:
    return _check_and_params(entry) is not None


def prose_criteria(acceptance_criteria: list[Any] | None) -> list[str]:
    """The non-typed (narrative) entries, as strings, in original order."""
    return [
        str(entry)
        for entry in (acceptance_criteria or [])
        if not is_typed_criterion(entry) and str(entry).strip()
    ]


def _fmt_methods_paths(raw: Any) -> str:
    parts: list[str] = []
    for item in raw or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            parts.append(f"`{item[0]} {item[1]}`")
        else:
            parts.append(f"`{item}`")
    return ", ".join(parts)


def expectation_line(entry: Any) -> str | None:
    """One exact, imperative line for a typed criterion; None for prose."""
    normalized = _check_and_params(entry)
    if normalized is None:
        return None
    check, params = normalized
    file = params.get("file", "")
    where = f" in `{file}`" if file else ""

    if check == "endpoint_defined":
        return (
            f"`{file}` must define exactly these routes (method, absolute path, and "
            f"path-parameter names are all literal): {_fmt_methods_paths(params.get('methods_paths'))}"
        )
    if check == "import_present":
        module = params.get("module", "")
        symbol = params.get("symbol")
        if symbol:
            return f"`{file}` must contain the direct import `from {module} import {symbol}`"
        return f"`{file}` must import module `{module}`"
    if check == "field_present":
        fields = ", ".join(f"`{f}`" for f in params.get("fields", []))
        return f"class `{params.get('class_name', '?')}`{where} must define fields: {fields}"
    if check == "function_defined":
        return (
            f"`{file}` must define at least {params.get('min_count', 1)} functions "
            f"named `{params.get('name_prefix', '')}*`"
        )
    if check == "command_exit_zero":
        argv = params.get("argv") or []
        return f"the command `{' '.join(str(a) for a in argv)}` must exit 0"
    if check == "harness_boundary":
        entries = ", ".join(f"`{m}`" for m in params.get("entry_modules", []))
        return (
            f"`{file}` must build its `{params.get('client_ctor', 'TestClient')}` "
            f"against one of: {entries} (no ad-hoc app construction)"
        )
    # Unknown/new check type: still surface it exactly rather than dropping it.
    kv = ", ".join(f"{k}={v!r}" for k, v in sorted(params.items()) if k != "file")
    return f"{check}{where}: {kv}" if kv else f"{check}{where}"


def expectation_lines(acceptance_criteria: list[Any] | None) -> list[str]:
    """Authoritative lines for every typed criterion, in original order."""
    lines: list[str] = []
    for entry in acceptance_criteria or []:
        line = expectation_line(entry)
        if line:
            lines.append(line)
    return lines
