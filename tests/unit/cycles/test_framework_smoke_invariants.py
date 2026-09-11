"""The framework-smoke invariants, checked against a real cycle's stored state (#176).

The crux of #176 is that a smoke harness must **assert on framework invariants, not on
the run reaching `completed`**. Small models exercise the plumbing reliably and cannot
clear content-quality gates, so a status-keyed harness is a false-negative generator on
exactly the squads cheap enough to gate merges with.

The corpus is `tests/fixtures/framework_smoke/cyc_02682aa4efa2/artifact_refs.json` — the
14 artifact references a real cycle stored (lite/7b, builder-assemble, play_game,
2026-06-14), copied verbatim from the vault. That run ended **FAILED**, because a 7b
builder emitted 194 completion tokens and the output validator correctly rejected it, and
**every framework invariant held anyway**. It is the case the harness must call PASS, and
the one a status check calls FAIL.

Validated against real emissions rather than invented fixtures on purpose: the first run
of `artifacts_persisted` against this corpus **failed it**, because the plan delta and the
run report are stored by the runner and carry no producing task id. A rule written from
imagination would have shipped calling a healthy cycle broken — the same false negative
#176 exists to prevent, one level down.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_orchestration]

_REPO = Path(__file__).resolve().parents[3]
_CORPUS = _REPO / "tests/fixtures/framework_smoke/cyc_02682aa4efa2/artifact_refs.json"


def _harness():
    """Import ``scripts/dev/framework_smoke.py`` by path — it is a script, not a package.

    Registered in ``sys.modules`` before execution: ``@dataclass`` resolves its field
    annotations through ``sys.modules[cls.__module__]``, so a module executed without one
    raises there rather than anywhere near the decorator.
    """
    spec = importlib.util.spec_from_file_location(
        "framework_smoke", _REPO / "scripts/dev/framework_smoke.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def smoke():
    return _harness()


@pytest.fixture(scope="module")
def corpus():
    return json.loads(_CORPUS.read_text())


class TestTheRealCycleTheIssueDocuments:
    def test_the_corpus_is_the_cycle_176_describes(self, corpus):
        """Bug caught: the corpus is replaced by something that proves less.

        Its value is entirely that it is a FAILED run with healthy plumbing. Swap in a
        clean green cycle and every assertion below still passes while testing nothing —
        the harness would agree with a status check, which is the thing it must not do.
        """
        assert len(corpus) == 14
        assert {ref["cycle_id"] for ref in corpus} == {"cyc_02682aa4efa2"}
        produced = {(ref.get("metadata") or {}).get("producing_task_type") for ref in corpus}
        # The correction loop ran, which is what makes this a failed run.
        assert "data.analyze_failure" in produced
        assert "governance.correction_decision" in produced

    def test_every_invariant_holds_on_a_run_that_ended_failed(self, smoke, corpus):
        """The whole point, in one assertion. #176's table, machine-checked."""
        results = smoke.check_all(corpus)
        failed = [str(r) for r in results if not r.held]
        assert failed == [], (
            "an invariant the real cycle satisfied now reads as broken:\n  " + "\n  ".join(failed)
        )

    def test_each_invariant_says_what_it_saw(self, smoke, corpus):
        """A failing invariant that cannot say what it found sends a reader back to
        eyeballing the run, which is what #176 replaces."""
        for result in smoke.check_all(corpus):
            assert result.detail.strip(), f"{result.name} reports nothing"
            assert result.name.strip()


class TestEachInvariantCanFail:
    """A check that cannot fail is not a check. Every one is driven to red on the same
    corpus with one thing removed, because a harness validated only on a passing case is
    a harness that passes on anything."""

    def test_a_missing_framing_stage_is_caught_and_named(self, smoke, corpus):
        without_qa = [
            r
            for r in corpus
            if (r.get("metadata") or {}).get("producing_task_type") != "qa.validate"
        ]
        result = smoke.multi_role_framing(without_qa)
        assert not result.held
        assert "qa.validate" in result.detail, "a missing stage must be named, not counted"

    def test_a_dev_stage_that_emitted_no_source_is_caught(self, smoke, corpus):
        """The #998 contentless shape: the task ran and delivered a warnings document.
        Counting tasks reads that as success; counting SOURCE does not."""
        prose_only = [
            {**r, "artifact_type": "document"}
            if (r.get("metadata") or {}).get("producing_task_type") == "development.develop"
            else r
            for r in corpus
        ]
        assert not smoke.develop_to_assemble_handoff(prose_only).held

    def test_a_correction_that_banked_no_plan_delta_is_caught(self, smoke, corpus):
        """#870: a decision whose reasoning was never stored makes the next round
        re-derive the failure blind."""
        no_delta = [r for r in corpus if r.get("artifact_type") != "plan_delta"]
        result = smoke.correction_loop_fired(no_delta)
        assert not result.held
        assert "0 plan delta" in result.detail

    def test_an_artifact_with_no_producing_task_is_caught(self, smoke, corpus):
        """#1264: an artifact that cannot be attributed cannot be superseded, and a
        repair's files cannot be told from the failed attempt's."""
        orphaned = [
            {**r, "metadata": {"role": "dev"}} if r["artifact_id"].startswith("art_b") else r
            for r in corpus
        ]
        result = smoke.artifacts_persisted(orphaned)
        assert not result.held
        assert "name no producing task" in result.detail


class TestTheCarveOutsAreArgued:
    def test_runner_owned_artifacts_are_exempt_by_identity_not_by_silence(self, smoke, corpus):
        """Bug caught: the provenance rule is relaxed to "some artifacts may be orphaned".

        The plan delta and the run report have no producing task because the *runner*
        stored them. Exempting them by identity keeps the rule sharp for everything else;
        exempting them by lowering the bar would let a genuinely unattributed task
        artifact through — and this corpus is what found the carve-out in the first place.
        """
        runner_owned = [r for r in corpus if smoke._is_runner_owned(r)]
        assert {r.get("filename") for r in runner_owned} == {"plan_delta_0.json", "run_report.md"}
        assert all(not (r.get("metadata") or {}).get("task_id") for r in runner_owned)

    def test_a_run_that_never_failed_has_no_correction_loop_to_fire(self, smoke, corpus):
        """Reported as not-exercised, not failed. A clean run has nothing to correct, and
        calling that a broken framework is the false negative this harness exists to
        avoid."""
        clean = [
            r
            for r in corpus
            if (r.get("metadata") or {}).get("producing_task_type")
            not in ("data.analyze_failure", "governance.correction_decision")
            and r.get("artifact_type") != "plan_delta"
        ]
        result = smoke.correction_loop_fired(clean)
        assert result.held
        assert "not exercised" in result.detail

    def test_terminal_status_is_not_among_the_invariants(self, smoke, corpus):
        """#176's key design decision, asserted rather than trusted to a comment.

        Nothing in `check_all` may consult a run's terminal status — the reference cycle
        ended FAILED and must read as a healthy framework.
        """
        names = " ".join(r.name for r in smoke.check_all(corpus)).lower()
        for forbidden in ("completed", "terminal", "status"):
            assert forbidden not in names, (
                f"an invariant is keyed on {forbidden!r} — that is the false-negative "
                f"generator #176 was filed to remove"
            )
