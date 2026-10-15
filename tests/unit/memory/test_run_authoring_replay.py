"""The replay's host runner (SIP-0110 §0.11–§0.12; slice 2, #2106): what it decides before any case
runs.

What bugs would these catch? A lesson handed to a case whose cutoff its evidence postdates (the
two-units-at-once case, §0.15 temporal validity); a named experiment rerun with a lesson edited,
reported as if it were the frozen one (§0.12 experiment manifest); a rubric's version named while
another version's text reads the outputs (#2313).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from squadops.memory.replay import CitedEvidence, ReplayLesson

pytestmark = [pytest.mark.domain_memory]

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "run_authoring_replay.py"
_spec = importlib.util.spec_from_file_location("run_authoring_replay", _SCRIPT)
runner = importlib.util.module_from_spec(_spec)
sys.modules["run_authoring_replay"] = runner
_spec.loader.exec_module(runner)

T = datetime(2026, 10, 8, 3, 0, tzinfo=UTC)


def _envelope(envelope_id: str, captured: datetime, cycle: str) -> dict:
    return {
        "envelope_id": envelope_id,
        "task_type": "strategy.propose_increment",
        "seam": "proposal_writing",
        "messages_sha256": envelope_id,
        "captured_at": captured.isoformat(),
        "cycle_id": cycle,
        "chat_kwargs": {"model": "qwen3.8:27b"},
    }


def _args(**change) -> Namespace:
    return Namespace(
        **{
            "experiment": "e1",
            "static_guidance": None,
            "generations": 2,
            "seed": 7,
            "rubric": "r@1",
            "framework_git_sha": "99d4a11e",
            **change,
        }
    )


def test_each_case_is_handed_only_lessons_its_cutoff_could_have_seen():
    """Two units at once: the lesson's source failed again between the two targets' captures. It
    reaches the later target only; the earlier one's exclusion is recorded with its reason."""
    lesson = ReplayLesson(
        "pat_a@1",
        "Name the element.",
        (
            CitedEvidence("o1", T - timedelta(hours=2), "cyc_source"),
            CitedEvidence("o2", T + timedelta(minutes=30), "cyc_source"),
        ),
    )
    early = _envelope("env_early", T + timedelta(minutes=10), "cyc_a")
    late = _envelope("env_late", T + timedelta(hours=1), "cyc_b")

    frozen, case_lessons = runner.plan(_args(), [early, late], [lesson])

    assert case_lessons == {
        "env_early": [],
        "env_late": [{"revision_id": "pat_a@1", "claim": "counterfactual"}],
    }
    [excluded] = frozen["excluded"]
    assert (
        excluded["envelope_id"] == "env_early" and "after the target's cutoff" in excluded["reason"]
    )
    assert frozen["arms"] == ["baseline", "scoped_memory"]


def test_a_frozen_experiment_refuses_a_changed_rerun_and_accepts_the_same_one(tmp_path):
    lesson = ReplayLesson("pat_a@1", "Name it.", (CitedEvidence("o1", T - timedelta(hours=1)),))
    envelopes = [_envelope("env_1", T, "cyc_a")]
    frozen, _ = runner.plan(_args(), envelopes, [lesson])
    runner._freeze(tmp_path, frozen)

    again, _ = runner.plan(_args(), envelopes, [lesson])
    runner._freeze(tmp_path, again)  # the same experiment, a later clock: accepted
    edited, _ = runner.plan(
        _args(), envelopes, [ReplayLesson("pat_a@1", "Name it, edited.", lesson.cited)]
    )

    with pytest.raises(SystemExit, match="frozen and differs"):
        runner._freeze(tmp_path, edited)
    assert json.loads((tmp_path / "manifest.json").read_text())["lessons"] == frozen["lessons"]


def _text_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def test_a_held_rubric_is_pinned_by_the_text_its_version_names():
    """#2274 edited the rubric from @2 to @3 in place, so an experiment naming @2 was read by @3's
    text. Each version names its own file's text, and @2's is kept for the results scored with it."""
    envelopes = [_envelope("env_1", T, "cyc_a")]
    rubrics = _SCRIPT.parent / "replay_rubrics"

    pinned = {
        version: runner.plan(
            _args(rubric=f"lesson.criterion_already_satisfied@{version}"), envelopes, []
        )[0]["rubric_sha256"]
        for version in ("2", "3")
    }

    assert pinned == {
        "2": _text_sha(rubrics / "criterion_already_satisfied@2.md"),
        "3": _text_sha(rubrics / "criterion_already_satisfied.md"),
    }


@pytest.mark.parametrize("version", ["1", "4"])
def test_a_held_rubric_named_at_a_version_no_file_holds_is_refused(version):
    with pytest.raises(SystemExit, match="holds lesson.criterion_already_satisfied at @2, @3;"):
        runner.plan(
            _args(rubric=f"lesson.criterion_already_satisfied@{version}"),
            [_envelope("env_1", T, "cyc_a")],
            [],
        )


def test_a_rubric_edited_under_its_version_is_a_different_experiment(tmp_path, monkeypatch):
    """The label can't show an in-place edit and the text's hash can, so a frozen experiment refuses
    a rerun whose rubric changed under the same version. A label no file holds records no text."""
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    monkeypatch.setattr(runner, "_RUBRICS", rubrics)
    envelopes = [_envelope("env_1", T, "cyc_a")]
    unheld, _ = runner.plan(_args(rubric="validity@exploratory"), envelopes, [])
    (rubrics / "r.md").write_text("# Rubric `r@1`\n\nRead it.\n", encoding="utf-8")
    runner._freeze(tmp_path, runner.plan(_args(), envelopes, [])[0])
    (rubrics / "r.md").write_text("# Rubric `r@1`\n\nRead it differently.\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="frozen and differs"):
        runner._freeze(tmp_path, runner.plan(_args(), envelopes, [])[0])
    assert unheld["rubric_sha256"] is None
