"""Syntax gate for repair-path Python emissions (pf-31 Fix D).

pf-31 repair-03 emitted a truncated ``backend/tests/test_runs.py`` (SyntaxError
mid-function) — the repair itself re-imported the pytest collection-crash class
it was dispatched to fix, and the broken file superseded the last good version.
The gate parses each repair-emitted ``.py`` artifact and DROPS syntactically
invalid ones before any landing point: the previously stored version (the last
known parseable one) stays current for RC3 accumulation and the retest, and the
next attempt is told exactly what was discarded (the 3.4b carry transport).

Related, not a substitute: the fenced-parser EOF-recovery (#528) salvages an
unterminated fence; a truncated function body is invalid however the fence ends.

Pure functions — the caller owns storage, events, and the carry.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def _python_artifact_name(art: Any) -> str | None:
    if not isinstance(art, dict):
        return None
    name = art.get("name") if art.get("name") is not None else art.get("path")
    if isinstance(name, str) and name.endswith(".py"):
        return name
    return None


def syntax_gate_python_artifacts(
    artifacts: list[Any],
) -> tuple[list[Any], list[tuple[dict, str]]]:
    """Split *artifacts* into (kept, rejected) by Python parseability.

    Non-Python and non-dict entries always pass through unchanged. A ``.py``
    artifact whose content fails ``ast.parse`` is rejected with a one-line
    error description (type, line, message).
    """
    kept: list[Any] = []
    rejected: list[tuple[dict, str]] = []
    for art in artifacts:
        name = _python_artifact_name(art)
        if name is None:
            kept.append(art)
            continue
        content = art.get("content")
        if not isinstance(content, str):
            kept.append(art)
            continue
        try:
            ast.parse(content, filename=name)
        except SyntaxError as exc:
            rejected.append((art, f"SyntaxError at line {exc.lineno}: {exc.msg}"))
            continue
        kept.append(art)
    return kept, rejected


def emission_integrity_instruction(name: str, error: str) -> str:
    """Authoritative next-attempt instruction for a discarded invalid emission.

    Travels the same carry → ``failure_evidence`` → prompt-block transport as
    the 3.4b frozen-restore instructions."""
    return (
        f"your previously emitted `{name}` was syntactically invalid ({error}) and was "
        "DISCARDED — the prior version of the file is still in effect. Re-emit the "
        "COMPLETE file, and keep it small enough to finish: do not start more files "
        "than you can fully emit."
    )


# ---------------------------------------------------------------------------
# Emission-failure marker (#566): machine-readable classification of a
# zero-extraction handler failure, emitted in the handler's failure outputs and
# consumed by the executor's retry path (aimed-retry feedback) and by the
# correction loop's failure-locus classifier. The marker is DATA — every
# instruction the model reads renders from the managed template asset.

EMISSION_FAILURE_KEY = "emission_failure"
EMISSION_FAILURE_NO_FENCED_BLOCKS = "no_fenced_blocks"

# #998: what KIND of nothing. Three zero-extraction shapes with three different remedies,
# previously indistinguishable in the evidence — a correction decision that cannot tell
# them apart guesses ("safety filter, context overload" was the banked guess for a run
# whose model had spent its whole completion budget thinking and closed no content).
#
# - ``cap_exhausted``: the model generated its full completion budget and produced no
#   content at all — thought budget exhausted before content (V7 roll 1: 8,192 tokens,
#   0 characters, 12.7 minutes). Remedy lives at the budget / prompt shape.
# - ``empty``: fewer tokens than the budget and no content — the model returned nothing
#   (a transport drop, a refusal, a model that stopped). Remedy: retry, investigate.
# - ``unextractable``: content came back but nothing in it was a path-addressed fence.
#   Remedy: the emission format (the #987/#528 class), not the budget.
SIGNATURE_CAP_EXHAUSTED = "cap_exhausted"
SIGNATURE_EMPTY = "empty"
SIGNATURE_UNEXTRACTABLE = "unextractable"


def classify_empty_emission(
    response_chars: int, completion_tokens: int | None, completion_cap: int | None
) -> str:
    """Name the zero-extraction shape from the facts the LLM call already reports (#998).

    ``completion_tokens >= completion_cap`` is the cap signal — the provider reports no
    stop reason through this port, so token count against the requested budget is the
    observable. Either value unknown means the cap cannot be asserted, and the shape
    falls to what the character count alone supports.
    """
    if response_chars > 0:
        return SIGNATURE_UNEXTRACTABLE
    if (
        completion_tokens is not None
        and completion_cap is not None
        and completion_cap > 0
        and completion_tokens >= completion_cap
    ):
        return SIGNATURE_CAP_EXHAUSTED
    return SIGNATURE_EMPTY


def no_fenced_blocks_failure(
    response_chars: int,
    expected_artifacts: list[str] | None,
    *,
    completion_tokens: int | None = None,
    completion_cap: int | None = None,
) -> dict[str, Any]:
    """Build the ``emission_failure`` marker for a zero-extraction failure.

    Carries the token facts and the #998 signature so the evidence says *which* nothing
    this was; a producer that cannot report tokens still emits a truthful marker with
    the signature the character count alone supports.
    """
    return {
        "reason": EMISSION_FAILURE_NO_FENCED_BLOCKS,
        "response_chars": response_chars,
        "expected_artifacts": [str(e) for e in (expected_artifacts or [])],
        "completion_tokens": completion_tokens,
        "completion_cap": completion_cap,
        "signature": classify_empty_emission(response_chars, completion_tokens, completion_cap),
    }


EMISSION_STATS_KEY = "emission_stats"

# The #431 gap rule: extraction loss is *suspected* when a substantial response
# retained almost nothing through extraction. Both bounds are deliberate:
# responses under the floor legitimately extract small (a one-line config fix
# wrapped in prose), and healthy responses retain well above the ceiling —
# prose around fences typically leaves 40–80% retention, while the production
# exhibit (cyc_8830cfc78a1e: ~7k generated tokens → ~800 stored bytes) sat
# near 3%. The flag is a DIAGNOSIS input, never a gate: it tells the analyzer
# the evidence itself is suspect, so a parser loss is not diagnosed as a
# work-product failure and repaired by regenerating into the same loss.
_EXTRACTION_LOSS_MIN_RESPONSE_CHARS = 2000
_EXTRACTION_LOSS_MAX_RETENTION = 0.15


def emission_stats(response_chars: int, artifacts: list[Any]) -> dict[str, Any]:
    """Per-attempt generated-vs-stored accounting (#431).

    Recorded on every build/repair emission — success and failure alike — so a
    failed attempt's evidence can compare what the model produced against what
    survived extraction. ``extracted_chars`` counts artifact content only
    (the stored work product), never metadata.
    """
    extracted = sum(
        len(a.get("content", ""))
        for a in artifacts
        if isinstance(a, dict) and isinstance(a.get("content"), str)
    )
    return {
        "response_chars": int(response_chars),
        "extracted_chars": extracted,
        "artifact_count": sum(1 for a in artifacts if isinstance(a, dict)),
    }


def extraction_loss_suspected(stats: dict[str, Any]) -> bool:
    """The #431 gap rule over an ``emission_stats`` record."""
    try:
        response_chars = int(stats.get("response_chars", 0))
        extracted_chars = int(stats.get("extracted_chars", 0))
    except (TypeError, ValueError):
        return False
    if response_chars < _EXTRACTION_LOSS_MIN_RESPONSE_CHARS:
        return False
    return extracted_chars < response_chars * _EXTRACTION_LOSS_MAX_RETENTION


def emission_retry_reason_line(marker: dict[str, Any]) -> str:
    """One factual sentence describing the marker, for the retry-feedback
    template's ``reason_line`` variable (same deterministic-instruction genre
    as ``emission_integrity_instruction`` above — data-derived line, section
    framing owned by the template asset)."""
    reason = marker.get("reason")
    if reason == EMISSION_FAILURE_NO_FENCED_BLOCKS:
        chars = marker.get("response_chars", 0)
        signature = marker.get("signature")
        if signature == SIGNATURE_CAP_EXHAUSTED:
            tokens = marker.get("completion_tokens")
            cap = marker.get("completion_cap")
            return (
                f"the model generated {tokens} tokens — its full {cap}-token completion "
                f"budget — and closed no content: the budget was spent before any file was "
                f"written. Emit the file first and keep any reasoning short."
            )
        if signature == SIGNATURE_EMPTY:
            return "the response was empty — no content was returned at all."
        return (
            f"no fenced code block carrying a file path could be extracted "
            f"from the {chars}-character response."
        )
    return f"the response failed emission extraction ({reason})."


# ---------------------------------------------------------------------------
# Intra-package import resolution (#591)
# ---------------------------------------------------------------------------
#
# The syntax gate above proves each file parses ALONE. pf-37 showed that is not
# enough: correction-00 emitted a coherent PAIR — its own ``backend/models.py``
# plus a ``backend/routes.py`` written against it — SIP-0100 correctly restored
# the frozen ``models.py``, and the surviving ``routes.py`` imported seven names
# (``RunCreate``, ``RunResponse``, …) that the frozen module never defined.
# Every typed check passed (they read one file at a time; the import statement is
# syntactically perfect) and the patch was ACCEPTED. The suite then failed to
# collect at all, and the correction budget went to re-rolling a test file
# against source that could never import.
#
# The defect was manufactured by enforcement, not by the model: each half was
# individually valid and nothing checked the pair. This resolves imports across
# the assembled workspace, which is the only place the mismatch is visible.


def _names_bound_by(node: ast.stmt) -> set[str] | None:
    """Names one module-level statement binds, or None when undecidable.

    None propagates: a star-import, a module-level ``__getattr__`` (PEP 562), or
    a conditional definition can bind names a flat walk cannot see.
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None if node.name == "__getattr__" else {node.name}
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    if isinstance(node, ast.AnnAssign):
        return {node.target.id} if isinstance(node.target, ast.Name) else set()
    if isinstance(node, ast.Import):
        return {a.asname or a.name.split(".")[0] for a in node.names}
    if isinstance(node, ast.ImportFrom):
        if any(a.name == "*" for a in node.names):
            return None
        return {a.asname or a.name for a in node.names}
    if isinstance(node, (ast.If, ast.Try)):
        # TYPE_CHECKING blocks, optional-dependency fallbacks.
        return None
    return set()


def _module_level_names(tree: ast.Module) -> set[str] | None:
    """Names a module binds at import time, or None when it can't be decided.

    None means "do not judge this module" — a false rejection of a good patch is
    worse than a missed one.
    """
    names: set[str] = set()
    for node in tree.body:
        bound = _names_bound_by(node)
        if bound is None:
            return None
        names |= bound
    return names


def _resolve_module_path(
    workspace_root: Path, source_rel: str, node: ast.ImportFrom
) -> Path | None:
    """Workspace path for an intra-package ``from ... import`` target, else None.

    Returns None for anything not resolvable *within the workspace* — stdlib,
    third-party, and absolute imports rooted outside it are none of this check's
    business.
    """
    source_dir = (workspace_root / source_rel).parent
    if node.level:
        base = source_dir
        for _ in range(node.level - 1):
            base = base.parent
        parts = (node.module or "").split(".") if node.module else []
    else:
        if not node.module:
            return None
        parts = node.module.split(".")
        base = workspace_root
        # Absolute, but rooted at a package that lives in this workspace
        # (``from backend.models import X`` beside ``backend/``).
        if not (workspace_root / parts[0]).is_dir():
            return None
    target = base
    for part in parts:
        target = target / part
    for candidate in (target.with_suffix(".py"), target / "__init__.py"):
        try:
            if candidate.is_file() and candidate.resolve().is_relative_to(workspace_root.resolve()):
                return candidate
        except (OSError, ValueError):
            continue
    return None


def unresolved_imports(workspace_root: Path | str) -> list[tuple[str, str, tuple[str, ...]]]:
    """Intra-package imports the workspace cannot satisfy (#591).

    Returns ``(source_file, module, missing_names)`` per offending statement,
    sorted for stable reporting. Empty means every intra-package import resolves.

    Deliberately conservative — it only reports a name when the target module is
    present, parses, and demonstrably does not bind it. Unreadable or
    undecidable modules are skipped, and imports pointing outside the workspace
    are ignored entirely, so third-party and stdlib imports never appear here.
    """
    workspace_root = Path(workspace_root)
    findings: list[tuple[str, str, tuple[str, ...]]] = []
    parsed: dict[Path, set[str] | None] = {}

    for source in sorted(workspace_root.rglob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
            continue  # the syntax gate owns unparseable emissions
        source_rel = source.relative_to(workspace_root).as_posix()

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if any(alias.name == "*" for alias in node.names):
                continue
            target = _resolve_module_path(workspace_root, source_rel, node)
            if target is None:
                continue
            if target not in parsed:
                try:
                    parsed[target] = _module_level_names(
                        ast.parse(target.read_text(encoding="utf-8"))
                    )
                except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
                    parsed[target] = None
            defined = parsed[target]
            if defined is None:
                continue
            missing = tuple(sorted(a.name for a in node.names if a.name not in defined))
            if missing:
                label = ("." * node.level) + (node.module or "")
                findings.append((source_rel, label, missing))
    return sorted(set(findings))


def unresolved_import_summary(findings: list[tuple[str, str, tuple[str, ...]]]) -> str:
    """One-line, operator-readable rendering of :func:`unresolved_imports`."""
    return "; ".join(
        f"{src} imports {', '.join(names)} from {module} (not defined there)"
        for src, module, names in findings
    )
