"""#924/#928 — what an LLM call emitted must be inspectable after the fact.

Lived in ``test_test_runner.py`` until #928; it was never a test-runner concern, and
the misfiling is part of how the coverage gap below went unnoticed.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from squadops.capabilities.handlers.emission_log import classify_fences, log_emission_shape

pytestmark = [pytest.mark.domain_capabilities]

_REPO = Path(__file__).resolve().parents[3]
_ROOTS = (_REPO / "src", _REPO / "adapters")

#: No production file is exempt. The one entry this held — ``src/squadops/llm/router.py``
#: — was exempted because ``LLMRouter`` was a pass-through off the production path; #944
#: deleted the class, so the exemption went with it rather than outliving its subject as
#: a rule about a file that no longer exists.
_PASS_THROUGH: set[str] = set()


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


#: The one production module allowed to call the LLM port. Everything else goes through
#: ``_CycleTaskHandler._llm_call``.
_THE_SEAM = "src/squadops/capabilities/handlers/cycle/base.py"


def test_no_handler_calls_the_llm_port_directly():
    """Bug caught: a handler grows its own LLM seam, and every cross-cutting concern
    wrapped around the call goes dark there.

    This test used to say something weaker. #924 placed the emission capture in
    ``handlers/cycle/base.py`` on the assumption that handlers shared one LLM seam;
    they did not — seventeen call sites across twelve files, each with its own
    ``response.content`` read — so #928 made this a per-file *count* of calls against
    captures. That prevented an eighteenth dark site and blessed the seventeen copies,
    and it needed updating for every future concern added to the sequence. #1206 is
    what the next concern cost: generation recording had the same defect and no
    equivalent test, so ten of the seventeen recorded nothing and LangFuse held 26 of
    35 calls without saying so.

    #929 collapsed the sequence into one method, which turns the invariant into a much
    stronger and cheaper one: there is one seam, and a new concern added there covers
    every handler by construction.
    """
    offenders = []
    for path in _production_files():
        rel = str(path.relative_to(_REPO))
        calls, _ = _seam_counts(path)
        if calls and rel != _THE_SEAM:
            offenders.append(f"{rel}: {calls} direct LLM call(s)")

    assert offenders == [], (
        "an LLM call bypasses `_CycleTaskHandler._llm_call` — the emission capture, "
        "the fault hook and the generation record are wrapped around that one call, "
        "and a seam that skips it is dark to all three:\n  " + "\n  ".join(offenders)
    )


def test_the_one_seam_calls_the_port_exactly_once():
    """Bug caught: the shared method grows a second call — a retry, a fallback model —
    and the sequence around it silently applies to only one of them.

    The count is the assertion. "base.py contains a call" would stay green if a
    fallback path were added beside it with none of the five following steps.
    """
    calls, captures = _seam_counts(_REPO / _THE_SEAM)
    assert calls == 1, f"{_THE_SEAM} makes {calls} LLM calls; the sequence wraps one"
    assert captures == 1, f"{_THE_SEAM} logs {captures} emission shapes; expected one"


def test_the_capture_still_owns_its_own_module():
    """Bug caught: the capture is folded back into the handler base it is called from.

    It began there, and ``planning/`` and ``impl/`` could not import it without
    reaching into a sibling handler's base class — so the natural fix for a missing
    capture was a second copy. Only one module calls it today (#929), which makes
    re-homing it look free; it is not. A concern that has been duplicated once, for
    exactly this reason, keeps its own module.
    """
    module = _REPO / "src/squadops/capabilities/handlers/emission_log.py"
    assert module.exists(), "the emission-log module was removed or moved"

    importers = sorted(
        str(p.relative_to(_REPO))
        for p in (_REPO / "src/squadops/capabilities/handlers").rglob("*.py")
        if "emission_log import" in p.read_text(encoding="utf-8")
    )
    assert importers == [_THE_SEAM], (
        f"the capture is imported by {importers} — after #929 exactly one module calls "
        f"it, and a second importer means a second LLM seam appeared"
    )


def test_every_llm_call_records_a_generation():
    """Bug caught: an LLM call reaches the model and LangFuse never hears about it.

    #1206's structural twin, and the test whose absence is why generation recording
    repeated #928's defect one instrument over. Measured on the 2026-08-31 shakeout
    pair: 35 calls, 35 emission-shape lines, **26** LangFuse generations. The nine
    invisible ones included both self-eval second calls and every impl handler, two of
    them declared ``ReasoningLevel.HIGH`` — the most expensive thinking in the cycle.

    "A subset that does not announce itself is worse than an absent one":
    ``gens_per_task`` read exactly 1.00 across every cycle measured, which looks like a
    clean invariant and was the second call being dropped every time.

    Asserted as *one* opt-out rather than none. The manifest-authoring loop records the
    same generation through the same method after its validator rules, so the record can
    carry the verdict (#1172); recording at call time as well would double-count it.
    A second ``record=False`` anywhere is a seam going dark, which is the whole failure
    mode — so the count is the assertion, not the presence.
    """
    src = (_REPO / _THE_SEAM).read_text(encoding="utf-8")
    assert "self._record_generation(" in src, "the one seam no longer records"

    # Read as an argument, never as a word: prose about the opt-out is not an opt-out,
    # and this file and the seam's own docstring both discuss it by name.
    opt_outs = []
    for path in _production_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (
                    kw.arg == "record"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                ):
                    opt_outs.append(f"{path.relative_to(_REPO)}:{node.lineno}")

    assert len(opt_outs) == 1, (
        f"{len(opt_outs)} seams opt out of recording their generation ({sorted(opt_outs)}) "
        f"— exactly one is accounted for (the manifest loop, which records after its "
        f"validator rules); any other is a generation LangFuse will never see"
    )
    assert opt_outs[0].startswith("src/squadops/capabilities/handlers/_plan_authoring_service.py")


@pytest.mark.parametrize(
    "info_tag",
    ["typescript", "tsx", "ts", "dockerfile", "json", "yaml", "python", "css", "sh"],
)
def test_an_addressed_fence_is_addressed_whatever_its_language_tag(info_tag):
    """Bug caught: the instrument reports a healthy emission as broken (#932).

    The original counted literal prefixes — ` ```typescript: ` and ` ```python: ` —
    and swept every other tag into ``plain``, i.e. *unaddressed*, which is the exact
    failure mode it exists to detect. Live during window roll 6: dev emitted
    ` ```tsx:app/page.tsx ` and builder ` ```dockerfile:Dockerfile `, both correct,
    both reported bare. The wrong conclusion ("the UI tasks emitted bare fences") was
    written down before the vault showed the files had landed fine.

    Parametrized over tags the models are actually observed to use, because the
    enumeration is the bug — an instrument must report what happened, not assert what
    should have.
    """
    counts = classify_fences(f"```{info_tag}:some/path.ext\nbody\n```")
    assert counts == {"fill": 0, "path": 1, "plain": 0}


def test_a_closing_delimiter_is_not_counted_as_a_bare_fence():
    """Bug caught: closers inflate the bare-fence count.

    Every fence has a closing ``` with no info string. Counted naively that reads as
    an unaddressed emission sitting beside each addressed one — the old form papered
    over this by subtracting twice the addressed count, which silently went wrong the
    moment a tag it did not recognize appeared.
    """
    assert classify_fences("```tsx:a.tsx\nx\n```") == {"fill": 0, "path": 1, "plain": 0}
    assert classify_fences("```fill:slot-a\nx\n```") == {"fill": 1, "path": 0, "plain": 0}


def test_a_genuinely_unaddressed_fence_still_reports_as_plain():
    """The instrument must not become blind in the other direction.

    A bare ``` and a language tag with no path both fail to name a file, and #566's
    bare-fence recovery exists precisely because that happens. Widening "addressed"
    to mean "has an info string" would hide it.
    """
    assert classify_fences("```\nprose\n```")["plain"] == 1
    assert classify_fences("```json\n{}\n```")["plain"] == 1


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


class TestReasoningSplitSeparatesTheTwoFailures:
    """#924 named ``chars=0 completion_tokens=6866`` as the line confirming its
    diagnosis. It does not: that shape fits both "thought the budget away" and
    "emitted tokens the parser rejected", which have opposite fixes."""

    def test_budget_exhaustion_and_rejected_output_are_distinguishable(self, caplog):
        with caplog.at_level(logging.INFO):
            log_emission_shape("qa_test", "", 6866, 6800)
            log_emission_shape("qa_test", "", 6866, 0)
        exhausted, rejected = caplog.messages[-2], caplog.messages[-1]
        assert "reasoning_tokens=6800" in exhausted
        assert "reasoning_tokens=0" in rejected
        assert exhausted != rejected, "the two failure modes must not render identically"

    def test_absent_reasoning_figure_is_omitted_not_zero_filled(self, caplog):
        """A caller with no reasoning figure must not have one invented for it —
        reporting 0 would assert the model did not think, which is a claim."""
        with caplog.at_level(logging.INFO):
            log_emission_shape("qa_test", "content", 413)
        assert "reasoning_tokens" not in caplog.messages[-1]
        assert "reasoning_chars" not in caplog.messages[-1]
        assert "completion_tokens=413" in caplog.messages[-1]

    def test_the_text_length_stands_in_where_the_provider_reports_no_count(self, caplog):
        """#1195: Ollama reports no thinking token count, so on the arm that runs
        production #924's line rendered nothing — 35 emission-shape lines across both
        2026-08-31 shakeouts, zero splits. The text is there where the count is not."""
        with caplog.at_level(logging.INFO):
            log_emission_shape("qa_test", "", 6866, None, "x" * 6800)
        message = caplog.messages[-1]
        assert "reasoning_chars=6800" in message
        # Characters are not tokens: the two must never share a field name, or a reader
        # will divide one by the other and get a meaningless ratio.
        assert "reasoning_tokens" not in message

    def test_a_real_count_wins_over_the_text_length(self, caplog):
        """A provider that reports the count (Atlas) must not have it replaced by an
        approximation just because the text is also present."""
        with caplog.at_level(logging.INFO):
            log_emission_shape("qa_test", "", 6866, 6800, "x" * 99)
        message = caplog.messages[-1]
        assert "reasoning_tokens=6800" in message
        assert "reasoning_chars" not in message

    def test_an_empty_thinking_channel_is_reported_as_zero_length_not_omitted(self, caplog):
        """ "" and None differ: a model that thought and returned nothing is not a model
        that did not think. Omitting the empty case would collapse them again."""
        with caplog.at_level(logging.INFO):
            log_emission_shape("qa_test", "content", 413, None, "")
        assert "reasoning_chars=0" in caplog.messages[-1]


def test_every_emission_call_site_reports_the_reasoning_split():
    """The call site passes BOTH reasoning figures.

    A seam that logs only ``completion_tokens`` is the one where #924's ambiguity
    survives — and it would be silently absent rather than wrong, which is why this
    is asserted structurally rather than left to review.

    Both halves are required (#1195). ``reasoning_tokens`` alone renders nothing on
    Ollama, which reports no thinking count, so a call site passing only the count
    would read green here and log nothing on the arm that runs production — exactly
    the failure this test exists to prevent, one field further in.

    This scanned eighteen call sites until #929; it scans one now, and the reason the
    test survives the collapse rather than being deleted with them is that the failure
    it names is a *field list*, not a count. One site passing one figure is the same
    defect at 1/1 that it was at 17/18 — and cheaper to reintroduce, since there is no
    neighbouring call to copy the full argument list from.
    """
    handlers = _REPO / "src/squadops/capabilities/handlers"
    missing = []
    total = 0
    for path in handlers.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            # A *call*, read from the tree — the definition's own parameter list is not
            # a call site, and a regex over the name cannot tell them apart.
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "log_emission_shape"
            ):
                continue
            total += 1
            source = ast.get_source_segment(text, node) or ""
            absent = [f for f in ("reasoning_tokens", "reasoning_text") if f not in source]
            if absent:
                missing.append(
                    f"{path.relative_to(handlers)}:{node.lineno} (no {', '.join(absent)})"
                )
    assert total == 1, f"expected the one shared call site, found {total} — did the scan break?"
    assert not missing, "call sites not reporting the reasoning split:\n  " + "\n  ".join(missing)
