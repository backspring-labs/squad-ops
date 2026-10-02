"""The convergence replay's corpus (#1764): which stored rounds a replay can start from.

Bug classes guarded: a failure joined to another round's diagnosis (before #1697 a refunded round
re-took its index, so an index join pairs a failure with the wrong decision), a round whose
analysis or decision is missing counted as replayable, and a tree rebuilt from files the failed
task wrote after its round began.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "convergence_replay" / "corpus.py"
_SPEC = importlib.util.spec_from_file_location("convergence_replay_corpus", _PATH)
corpus = importlib.util.module_from_spec(_SPEC)
sys.modules["convergence_replay_corpus"] = corpus
_SPEC.loader.exec_module(corpus)

T0 = datetime(2026, 9, 28, 19, 0, tzinfo=UTC)


def _art(task_id: str, minute: int, artifact_id: str | None = None) -> corpus.ArtifactMeta:
    return corpus.ArtifactMeta(
        artifact_id=artifact_id or f"art_{task_id[-6:]}_{minute}",
        filename="x.md",
        task_id=task_id,
        producing_task_type=task_id.rsplit("-", 1)[-1],
        created_at=T0 + timedelta(minutes=minute),
        path="/dev/null",
    )


def _failure(task_id: str, index: int = 0) -> corpus.RoundFailure:
    return corpus.RoundFailure(
        task_id, index, ("tests_pass",), "own_artifact", "executed_and_failed"
    )


def test_rounds_pair_their_halves_and_order_by_their_analysis():
    """1.9 ids (-s00-, -s01-) and pre-#1697 ids (no sequence) both pair; a prefix with only one
    half — a round a crash or the budget cut short — is not a round."""
    arts = [
        _art("corr-run_ac3a75c2-00-s01-data.analyze_failure", 28),
        _art("corr-run_ac3a75c2-00-s01-governance.correction_decision", 29),
        _art("corr-run_ac3a75c2-00-s00-governance.correction_decision", 21),
        _art("corr-run_ac3a75c2-00-s00-data.analyze_failure", 20),
        _art("corr-run_ac3a75c2-01-data.analyze_failure", 40),  # no decision: cut short
        _art("repair-run_ac3a75c2-00-s00-qa.test_repair", 22),  # not a diagnosis
    ]

    rounds = corpus.correction_rounds(arts)

    assert [(r.attempt, r.seq) for r in rounds] == [(0, 0), (0, 1)]
    assert rounds[0].decision.task_id.endswith("-s00-governance.correction_decision")


def test_failures_join_rounds_in_order_and_a_count_mismatch_is_refused():
    rounds = corpus.correction_rounds(
        [
            _art("corr-run_ac3a75c2-00-data.analyze_failure", 20),
            _art("corr-run_ac3a75c2-00-governance.correction_decision", 21),
            _art("corr-run_ac3a75c2-00-data.analyze_failure", 30, "art_again_30"),
        ]
    )
    failures = [
        _failure("task-run_ac3a75c2-m005-qa.test"),
        _failure("task-run_ac3a75c2-m006-qa.test"),
    ]

    joined = corpus.join_failures_to_rounds(failures[:1], rounds)
    refused = corpus.join_failures_to_rounds(failures, rounds)

    assert [(f.task_id, r.attempt) for f, r in joined] == [("task-run_ac3a75c2-m005-qa.test", 0)]
    assert refused == "2 recorded failures against 1 correction rounds"


def test_the_failed_files_and_the_checkpoint_precede_the_round():
    """A file the task wrote after its round began is a repair's, not the failure's; a checkpoint
    written after it is the repaired tree's. Neither may enter the failure's tree."""
    task = "task-run_ac3a75c2-m005-qa.test"
    before = T0 + timedelta(minutes=20)
    arts = [_art(task, 10, "art_early"), _art(task, 25, "art_late"), _art("task-other", 5)]
    checkpoints = [
        (3, T0 + timedelta(minutes=5)),
        (4, T0 + timedelta(minutes=15)),
        (5, T0 + timedelta(minutes=30)),
    ]

    assert corpus.failed_task_artifacts(arts, task, before) == ("art_early",)
    assert corpus.preceding_checkpoint(checkpoints, before) == 4
    assert corpus.preceding_checkpoint(checkpoints[2:], before) is None
