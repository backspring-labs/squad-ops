"""A task a restarted runtime asks for again is answered, not run twice (#1929).

What bugs would these catch? A retry by the same runtime answered from the store, so a failed
task is "retried" with its own failure and never runs again. A restarted runtime's re-dispatch
run in full: duplicate model time, and the next task queued behind it. An agent's store growing
without bound, when a reply can carry whole files.
"""

from __future__ import annotations

from squadops.comms.task_replay import FinishedTasks


def test_a_restarted_runtime_is_answered_and_each_runtimes_retry_runs_fresh():
    finished = FinishedTasks()
    finished.record("task-x", "reply-1", "boot-a")

    asked = [
        finished.replay_for("task-x", "boot-a"),  # the same runtime's retry
        finished.replay_for("task-x", "boot-b"),  # a restarted runtime asking again
        finished.replay_for("task-x", "boot-b"),  # that runtime's own retry, after the replay
        finished.replay_for("task-y", "boot-b"),  # a task never finished here
    ]

    assert asked == [None, "reply-1", None, None]


def test_a_dispatch_without_a_boot_is_never_answered_from_the_store():
    """A runtime from before the stamp sends no boot: it runs, as it always did."""
    finished = FinishedTasks()
    finished.record("task-x", "reply-1", "boot-a")

    assert finished.replay_for("task-x", None) is None


def test_only_the_last_few_finished_tasks_are_kept():
    finished = FinishedTasks(keep=2)
    for task_id in ("task-a", "task-b", "task-c"):
        finished.record(task_id, f"reply-{task_id}", "boot-a")

    assert finished.replay_for("task-a", "boot-b") is None
    assert finished.replay_for("task-c", "boot-b") == "reply-task-c"
