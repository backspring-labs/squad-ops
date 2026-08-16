"""#924/#928 — what an LLM call emitted must be inspectable after the fact.

Lived in ``test_test_runner.py`` until #928; it was never a test-runner concern, and
the misfiling is part of how the coverage gap below went unnoticed.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from squadops.capabilities.handlers.emission_log import log_emission_shape

pytestmark = [pytest.mark.domain_capabilities]

_REPO = Path(__file__).resolve().parents[3]
_ROOTS = (_REPO / "src", _REPO / "adapters")

#: ``LLMRouter.chat_stream_with_usage`` is a pure pass-through to the provider and is
#: NOT on the production path — the agent entrypoint injects the provider adapter
#: directly (``bootstrap/system.py`` ← ``adapters/llm/factory.py``). Capturing there
#: would log nothing today and double-log every emission if the router were ever
#: wired, since the handler seams below already capture. Exempt deliberately, with
#: the reason recorded, rather than silently skipped.
_PASS_THROUGH = {"src/squadops/llm/router.py"}


def _seam_counts(path: Path) -> tuple[int, int]:
    """(LLM calls, emission captures) in one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = sum(
        1
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "chat_stream_with_usage"
    )
    captures = sum(
        1
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "log_emission_shape"
    )
    return calls, captures


def _production_files() -> list[Path]:
    return sorted(p for root in _ROOTS for p in root.rglob("*.py"))


def test_every_llm_seam_captures_what_it_emitted():
    """Bug caught: a handler calls the model through its own seam and nothing records
    the result — the #928 defect, and the reason window roll 6 nearly produced nothing.

    #924 placed the capture in ``handlers/cycle/base.py`` on the assumption that
    handlers share one LLM seam. They do not. Thirteen production call sites existed
    across nine files, each with its own ``chat_stream_with_usage`` and its own
    ``response.content`` read; the instrument covered exactly one, and **not** the qa
    author's — the single emission the SIP-0104 window was blocked on. Live proof: a
    completed ``data.research_context`` call (27b, 4,829 completion tokens) produced no
    shape line at all.

    Counted per file rather than checked as a boolean, because the interesting seams
    come in pairs: ``develop`` and ``qa_test`` each make a *second* self-eval call
    whose emission can overwrite the first's artifacts. Instrumenting only the primary
    call would leave the rewrite path dark while this test read green.
    """
    gaps = []
    for path in _production_files():
        rel = str(path.relative_to(_REPO))
        if rel in _PASS_THROUGH:
            continue
        calls, captures = _seam_counts(path)
        if calls and captures < calls:
            gaps.append(f"{rel}: {calls} LLM call(s), {captures} capture(s)")

    assert gaps == [], (
        "an LLM emission is unrecorded — its failures can then only be diagnosed by "
        "guessing, which is what cost this window rolls 3 and 5:\n  " + "\n  ".join(gaps)
    )


def test_the_capture_is_reachable_from_every_package_that_needs_it():
    """Bug caught: the helper is re-homed somewhere only one package can import.

    It began in ``handlers/cycle/base.py``, which ``planning/`` and ``impl/`` cannot
    import without reaching into a sibling handler's base class — so the natural fix
    for a missing capture was to write a second copy. Owning the concern in its own
    module is what makes the coverage test above satisfiable without duplication.
    """
    module = _REPO / "src/squadops/capabilities/handlers/emission_log.py"
    assert module.exists(), "the emission-log module was removed or moved"

    importers = {
        str(p.relative_to(_REPO)).split("/")[4]
        for p in (_REPO / "src/squadops/capabilities/handlers").rglob("*.py")
        if "emission_log import" in p.read_text(encoding="utf-8")
    }
    # cycle/, planning/, impl/ and the top-level authoring services all depend on it.
    assert {"cycle", "planning", "impl"} <= importers, (
        f"only {sorted(importers)} import the capture — a package that cannot reach it "
        f"is a package that will grow its own copy"
    )


def test_the_three_diagnoses_are_distinguishable(caplog):
    """Bug caught: a failed emission leaves no trace, so its cause must be guessed.

    These three shapes have opposite fixes and were indistinguishable from outside:
    emitted fills, emitted nothing while billing a full budget, emitted the wrong
    fence kind.
    """
    with caplog.at_level(logging.INFO):
        log_emission_shape("qa", "```fill:slot-a\nexpect(1).toBe(1)\n```", 413)
        log_emission_shape("qa", "", 6866)
        log_emission_shape("qa", "```typescript:__tests__/x.test.ts\nx\n```", 900)

    filled, empty, wrong_fence = (r.getMessage() for r in caplog.records[-3:])

    assert "'fill': 1" in filled
    # the signature of a reasoning channel eating the budget: billed, emitted nothing
    assert "chars=0" in empty and "completion_tokens=6866" in empty
    assert "'path': 1" in wrong_fence and "'fill': 0" in wrong_fence


def test_a_head_sample_is_recorded_and_bounded(caplog):
    """A shape with no sample cannot distinguish "wrong fence" from "prose apology".
    Bounded because this runs on every call and must never persist a whole completion
    or its prompt material."""
    with caplog.at_level(logging.INFO):
        log_emission_shape("qa", "I cannot complete this task because " + "x" * 5000, 12)

    message = caplog.records[-1].getMessage()
    assert "I cannot complete this task" in message
    assert len(message) < 600


def test_a_missing_completion_logs_nothing_rather_than_a_false_zero(caplog):
    """`None` means the call did not return content — distinct from an empty string,
    which means it returned nothing. Logging `chars=0` for both would erase the
    difference between a transport failure and an empty emission."""
    with caplog.at_level(logging.INFO):
        log_emission_shape("qa", None, None)

    assert not [r for r in caplog.records if "emission shape" in r.getMessage()]


def test_the_shape_capture_is_wired_outside_the_observability_gate():
    """Bug caught: the capture is called from inside ``if llm_obs and ...``.

    It would then go silent in exactly the deployments without observability
    configured — the ones where an unexplained emission is hardest to diagnose. This
    placement was live while #924 was written.
    """
    source = (_REPO / "src/squadops/capabilities/handlers/cycle/base.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    call_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "log_emission_shape"
    ]
    assert call_lines, "the emission-shape capture is defined but never called"

    gated: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        if "llm_obs" not in names:
            continue
        for stmt in node.body:
            gated.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))

    inside = sorted(set(call_lines) & gated)
    assert not inside, (
        f"the capture is inside the observability gate at {inside} — it would go "
        f"silent wherever llm_observability is not configured"
    )


def test_the_fill_seam_capture_is_wired_at_the_parse_site():
    """Bug caught: the one distinction that cannot be recovered afterwards.

    P3 renders a REJECTED fill as the same failing state as a MISSING one, so
    "emitted nothing", "emitted fills that were refused", and "emitted a file instead
    of fills" all present identically as unfilled slots. Window roll 5's cause could
    not be determined from its stored artifacts for exactly that reason.

    Pinned at the parse site specifically: a capture placed after the merge would
    report the merged result, which is the thing that already loses the difference.
    """
    source = (_REPO / "src/squadops/capabilities/handlers/cycle/qa_test.py").read_text(
        encoding="utf-8"
    )
    assert "emission parse:" in source, "the fill-seam capture is gone"

    tree = ast.parse(source)
    parse_calls = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "parse_fill_emission"
    ]
    log_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "info"
        and any(
            isinstance(a, ast.Constant) and "emission parse:" in str(a.value) for a in node.args
        )
    ]
    assert parse_calls and log_lines, "parse site or capture missing"
    assert min(log_lines) > min(parse_calls), (
        "the capture must follow the parse — before it, there is nothing to report"
    )
