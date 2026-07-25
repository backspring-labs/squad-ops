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


def no_fenced_blocks_failure(
    response_chars: int,
    expected_artifacts: list[str] | None,
) -> dict[str, Any]:
    """Build the ``emission_failure`` marker for a zero-extraction failure."""
    return {
        "reason": EMISSION_FAILURE_NO_FENCED_BLOCKS,
        "response_chars": response_chars,
        "expected_artifacts": [str(e) for e in (expected_artifacts or [])],
    }


def emission_retry_reason_line(marker: dict[str, Any]) -> str:
    """One factual sentence describing the marker, for the retry-feedback
    template's ``reason_line`` variable (same deterministic-instruction genre
    as ``emission_integrity_instruction`` above — data-derived line, section
    framing owned by the template asset)."""
    reason = marker.get("reason")
    if reason == EMISSION_FAILURE_NO_FENCED_BLOCKS:
        chars = marker.get("response_chars", 0)
        return (
            f"no fenced code block carrying a file path could be extracted "
            f"from the {chars}-character response."
        )
    return f"the response failed emission extraction ({reason})."
